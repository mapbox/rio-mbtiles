"""mbtiles CLI"""

import functools
import logging
import math
import os
import sqlite3
import sys

import click
from cligj.features import iter_features
import mercantile
import rasterio
from rasterio.enums import Resampling
from rasterio.rio.options import creation_options, output_opt, _cb_key_val
from rasterio.warp import transform, transform_geom
import shapely.affinity
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
import shapely.wkt
import supermercado.burntiles
from tqdm import tqdm

from mbtiles import __version__ as mbtiles_version


DEFAULT_NUM_WORKERS = None
RESAMPLING_METHODS = [method.name for method in Resampling]
TILES_CRS = "EPSG:3857"

log = logging.getLogger(__name__)


def resolve_inout(
    input=None, output=None, files=None, overwrite=False, append=False, num_inputs=None
):
    """Resolves inputs and outputs from standard args and options.

    Parameters
    ----------
    input : str
        A single input filename, optional.
    output : str
        A single output filename, optional.
    files : str
        A sequence of filenames in which the last is the output filename.
    overwrite : bool
        Whether to force overwriting the output file.
    append : bool
        Whether to append to the output file.
    num_inputs : int
        Raise exceptions if the number of resolved input files is higher
        or lower than this number.

    Returns
    -------
    tuple (str, list of str)
        The resolved output filename and input filenames as a tuple of
        length 2.

    If provided, the output file may be overwritten. An output
    file extracted from files will not be overwritten unless
    overwrite is True.

    Raises
    ------
    click.BadParameter

    """
    resolved_output = output or (files[-1] if files else None)
    resolved_inputs = (
        [input]
        if input
        else [] + list(files[: -1 if not output else None])
        if files
        else []
    )

    if num_inputs is not None:
        if len(resolved_inputs) < num_inputs:
            raise click.BadParameter("Insufficient inputs")
        elif len(resolved_inputs) > num_inputs:
            raise click.BadParameter("Too many inputs")

    return resolved_output, resolved_inputs


def extract_features(ctx, param, value):
    if value is not None:
        with click.open_file(value, encoding="utf-8") as src:
            return list(iter_features(iter(src)))
    else:
        return None


@click.command(short_help="Export a dataset to MBTiles.")
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(resolve_path=True),
    required=True,
    metavar="INPUT [OUTPUT]",
)
@output_opt
@click.option(
    "--append/--overwrite",
    default=True,
    is_flag=True,
    help="Append tiles to an existing file or overwrite.",
)
@click.option("--title", help="MBTiles dataset title.")
@click.option("--description", help="MBTiles dataset description.")
@click.option(
    "--overlay",
    "layer_type",
    flag_value="overlay",
    default=True,
    help="Export as an overlay (the default).",
)
@click.option(
    "--baselayer", "layer_type", flag_value="baselayer", help="Export as a base layer."
)
@click.option(
    "-f",
    "--format",
    "img_format",
    type=click.Choice(["JPEG", "PNG", "WEBP"]),
    default="JPEG",
    help="Tile image format.",
)
@click.option(
    "--tile-size",
    default=256,
    show_default=True,
    type=int,
    help="Width and height of individual square tiles to create.",
)
@click.option(
    "--zoom-levels",
    default=None,
    metavar="MIN..MAX",
    help="A min...max range of export zoom levels. "
    "The default zoom level "
    "is the one at which the dataset is contained within "
    "a single tile.",
)
@click.option(
    "--image-dump",
    metavar="PATH",
    help="A directory into which image tiles will be optionally " "dumped.",
)
@click.option(
    "-j",
    "num_workers",
    type=int,
    default=DEFAULT_NUM_WORKERS,
    help="Number of workers (default: number of computer's processors).",
)
@click.option(
    "--src-nodata",
    default=None,
    show_default=True,
    type=float,
    help="Manually override source nodata",
)
@click.option(
    "--dst-nodata",
    default=None,
    show_default=True,
    type=float,
    help="Manually override destination nodata",
)
@click.option(
    "--resampling",
    type=click.Choice(RESAMPLING_METHODS),
    default="nearest",
    show_default=True,
    help="Resampling method to use.",
)
@click.version_option(version=mbtiles_version, message="%(version)s")
@click.option(
    "--rgba", default=False, is_flag=True, help="Select RGBA output. For PNG or WEBP only."
)
@click.option(
    "--implementation",
    "implementation",
    type=click.Choice(["cf", "mp"]),
    default=None,
    help="Concurrency implementation. Use concurrent.futures (cf) or multiprocessing (mp).",
)
@click.option(
    "--progress-bar", "-#", default=False, is_flag=True, help="Display progress bar."
)
@click.option("--covers", help="Restrict mbtiles output to cover a quadkey")
@click.option(
    "--cutline",
    type=click.Path(exists=True),
    callback=extract_features,
    default=None,
    help="Path to a GeoJSON FeatureCollection to be used as a cutline. Only source pixels within the cutline features will be exported.",
)
@click.option(
    "--oo",
    "open_options",
    metavar="NAME=VALUE",
    multiple=True,
    callback=_cb_key_val,
    help="Format driver-specific options to be used when accessing the input dataset. See the GDAL format driver documentation for more information.",
)
@creation_options
@click.option(
    "--wo",
    "warp_options",
    metavar="NAME=VALUE",
    multiple=True,
    callback=_cb_key_val,
    help="See the GDAL warp options documentation for more information.",
)
@click.option(
    "--exclude-empty-tiles/--include-empty-tiles",
    default=True,
    is_flag=True,
    help="Whether to exclude or include empty tiles from the output.",
)
@click.pass_context
def mbtiles(
    ctx,
    files,
    output,
    append,
    title,
    description,
    layer_type,
    img_format,
    tile_size,
    zoom_levels,
    image_dump,
    num_workers,
    src_nodata,
    dst_nodata,
    resampling,
    rgba,
    implementation,
    progress_bar,
    covers,
    cutline,
    open_options,
    creation_options,
    warp_options,
    exclude_empty_tiles,
):
    """Export a dataset to MBTiles (version 1.3) in a SQLite file.

    The input dataset may have any coordinate reference system. It must
    have at least three bands, which will be become the red, blue, and
    green bands of the output image tiles.

    An optional fourth alpha band may be copied to the output tiles by
    using the --rgba option in combination with the PNG or WEBP formats.
    This option requires that the input dataset has at least 4 bands.

    The default quality for JPEG and WEBP output (possible range:
    10-100) is 75. This value can be changed with the use of the QUALITY
    creation option, e.g. `--co QUALITY=90`.  The default zlib
    compression level for PNG output (possible range: 1-9) is 6. This
    value can be changed like `--co ZLEVEL=8`.  Lossless WEBP can be
    chosen with `--co LOSSLESS=TRUE`.

    If no zoom levels are specified, the defaults are the zoom levels
    nearest to the one at which one tile may contain the entire source
    dataset.

    If a title or description for the output file are not provided,
    they will be taken from the input dataset's filename.

    This command is suited for small to medium (~1 GB) sized sources.

    Python package: rio-mbtiles (https://github.com/mapbox/rio-mbtiles).

    """
    log = logging.getLogger(__name__)

    output, files = resolve_inout(
        files=files, output=output, overwrite=not (append), append=append, num_inputs=1,
    )
    inputfile = files[0]

    if implementation == "cf" and sys.version_info < (3, 7):
        raise click.BadParameter(
            "concurrent.futures implementation requires python>=3.7"
        )
    elif implementation == "cf":
        from mbtiles.cf import process_tiles
    elif implementation == "mp":
        from mbtiles.mp import process_tiles
    elif sys.version_info >= (3, 7):
        from mbtiles.cf import process_tiles
    else:
        from mbtiles.mp import process_tiles

    with ctx.obj["env"]:

        # Read metadata from the source dataset.
        with rasterio.open(inputfile, **open_options) as src:

            if dst_nodata is not None and (
                src_nodata is None and src.profile.get("nodata") is None
            ):
                raise click.BadParameter(
                    "--src-nodata must be provided because " "dst-nodata is not None."
                )
            base_kwds = {"dst_nodata": dst_nodata, "src_nodata": src_nodata}

            if src_nodata is not None:
                base_kwds.update(nodata=src_nodata)

            if dst_nodata is not None:
                base_kwds.update(nodata=dst_nodata)

            # Name and description.
            title = title or os.path.basename(src.name)
            description = description or src.name

            # Compute the geographic bounding box of the dataset.
            (west, east), (south, north) = transform(
                src.crs, "EPSG:4326", src.bounds[::2], src.bounds[1::2]
            )

            # cutlines must be transformed from CRS84 to src pixel/line
            # coordinates and then formatted as WKT.
            if cutline is not None:
                geoms = [shape(f["geometry"]) for f in cutline]
                union = unary_union(geoms)
                if union.geom_type not in ("MultiPolygon", "Polygon"):
                    raise click.ClickException("Unexpected cutline geometry type")
                west, south, east, north = union.bounds
                cutline_src = shape(
                    transform_geom("OGC:CRS84", src.crs, mapping(union))
                )
                invtransform = ~src.transform
                shapely_matrix = (
                    invtransform.a,
                    invtransform.b,
                    invtransform.d,
                    invtransform.e,
                    invtransform.xoff,
                    invtransform.yoff,
                )
                cutline_rev = shapely.affinity.affine_transform(
                    cutline_src, shapely_matrix
                )
                warp_options["cutline"] = shapely.wkt.dumps(cutline_rev)

        if covers is not None:
            covers_tile = mercantile.quadkey_to_tile(covers)
            west, south, east, north = mercantile.bounds(covers_tile)

        # Resolve the minimum and maximum zoom levels for export.
        if zoom_levels:
            minzoom, maxzoom = map(int, zoom_levels.split(".."))
        else:
            zw = int(round(math.log(360.0 / (east - west), 2.0)))
            zh = int(round(math.log(170.1022 / (north - south), 2.0)))
            minzoom = min(zw, zh)
            maxzoom = max(zw, zh)

        log.debug("Zoom range: %d..%d", minzoom, maxzoom)

        if rgba:
            if img_format == "JPEG":
                raise click.BadParameter(
                    "RGBA output is not possible with JPEG format."
                )
            else:
                count = 4
        else:
            count = 3

        # Parameters for creation of tile images.
        base_kwds.update(
            {
                "driver": img_format.upper(),
                "dtype": "uint8",
                "nodata": 0,
                "height": tile_size,
                "width": tile_size,
                "count": count,
                "crs": TILES_CRS,
            }
        )

        img_ext = "jpg" if img_format.lower() == "jpeg" else img_format.lower()

        # Constrain bounds.
        EPS = 1.0e-10
        west = max(-180 + EPS, west)
        south = max(-85.051129, south)
        east = min(180 - EPS, east)
        north = min(85.051129, north)

        if progress_bar:
            # Estimate total number of tiles.
            west_merc, south_merc = mercantile.xy(west, south)
            east_merc, north_merc = mercantile.xy(east, north)
            raster_area = (east_merc - west_merc) * (north_merc - south_merc)

            est_num_tiles = 0
            zoom = minzoom

            (
                minz_west_merc,
                minz_south_merc,
                minz_east_merc,
                minz_north_merc,
            ) = mercantile.xy_bounds(mercantile.tile(0, 0, zoom))
            minzoom_tile_area = (minz_east_merc - minz_west_merc) * (
                minz_north_merc - minz_south_merc
            )
            ratio = min_ratio = raster_area / minzoom_tile_area

            # If given a cutline, we use its mercator area and the
            # supermercado module to help estimate the number of output
            # tiles.
            if cutline:
                geoms = [shape(f["geometry"]) for f in cutline]
                union = unary_union(geoms)
                cutline_mercator = transform_geom(
                    "OGC:CRS84", "EPSG:3857", mapping(union)
                )
                min_ratio *= shape(cutline_mercator).area / raster_area
                ratio = min_ratio
                estimator = functools.partial(supermercado.burntiles.burn, cutline)
            else:
                estimator = functools.partial(
                    mercantile.tiles, west, south, east, north
                )

            est_num_tiles = len(list(estimator(zoom)))
            ratio *= 4.0

            while zoom < maxzoom and ratio < 16:
                zoom += 1
                est_num_tiles += len(list(estimator(zoom)))
                ratio *= 4.0
            else:
                zoom += 1

            est_num_tiles += int(
                sum(
                    math.ceil(math.pow(4.0, z - minzoom) * min_ratio)
                    for z in range(zoom, maxzoom + 1)
                )
            )

            pbar = tqdm(total=est_num_tiles)

        else:
            pbar = None

        # Initialize the sqlite db.
        output_exists = os.path.exists(output)
        if append:
            appending = output_exists
        elif output_exists:
            appending = False
            log.info("Overwrite mode chosen, unlinking output file.")
            os.unlink(output)

        # workaround for bug here: https://bugs.python.org/issue27126
        sqlite3.connect(":memory:").close()
        conn = sqlite3.connect(output)

        def init_mbtiles():
            """Note: this closes over other local variables of the command function."""
            cur = conn.cursor()

            if appending:
                cur.execute("SELECT * FROM metadata WHERE name = 'bounds';")
                (
                    _,
                    bounds,
                ) = cur.fetchone()

                prev_west, prev_south, prev_east, prev_north = map(
                    float, bounds.split(",")
                )
                new_west = min(west, prev_west)
                new_south = min(south, prev_south)
                new_east = max(east, prev_east)
                new_north = max(north, prev_north)

                cur.execute(
                    "UPDATE metadata SET value = ? WHERE name = 'bounds';",
                    ("%f,%f,%f,%f" % (new_west, new_south, new_east, new_north),),
                )
            else:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS tiles "
                    "(zoom_level integer, tile_column integer, "
                    "tile_row integer, tile_data blob);"
                )
                cur.execute(
                    "CREATE UNIQUE INDEX idx_zcr ON tiles (zoom_level, tile_column, tile_row);"
                )
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS metadata (name text, value text);"
                )

                cur.execute(
                    "INSERT INTO metadata (name, value) VALUES (?, ?);", ("name", title)
                )
                cur.execute(
                    "INSERT INTO metadata (name, value) VALUES (?, ?);",
                    ("type", layer_type),
                )
                cur.execute(
                    "INSERT INTO metadata (name, value) VALUES (?, ?);",
                    ("version", "1.1"),
                )
                cur.execute(
                    "INSERT INTO metadata (name, value) VALUES (?, ?);",
                    ("description", description),
                )
                cur.execute(
                    "INSERT INTO metadata (name, value) VALUES (?, ?);",
                    ("format", img_ext),
                )
                cur.execute(
                    "INSERT INTO metadata (name, value) VALUES ('bounds', ?);",
                    ("%f,%f,%f,%f" % (west, south, east, north),),
                )
            conn.commit()

        def insert_results(tile, contents, img_ext=None, image_dump=None):
            """Also a closure."""
            cursor = conn.cursor()
            if contents is None:
                log.info("Tile %r is empty and will be skipped", tile)
                return

            # MBTiles have a different origin than Mercantile/tilebelt.
            tiley = int(math.pow(2, tile.z)) - tile.y - 1

            # Optional image dump.
            if image_dump:
                img_name = "{}-{}-{}.{}".format(tile.x, tiley, tile.z, img_ext)
                img_path = os.path.join(image_dump, img_name)
                with open(img_path, "wb") as img:
                    img.write(contents)

            # Insert tile into db.
            log.info("Inserting tile: tile=%r", tile)

            cursor.execute(
                "INSERT OR REPLACE INTO tiles "
                "(zoom_level, tile_column, tile_row, tile_data) "
                "VALUES (?, ?, ?, ?);",
                (tile.z, tile.x, tiley, sqlite3.Binary(contents)),
            )

        def commit_mbtiles():
            conn.commit()

        if cutline:

            def gen_tiles():
                for zk in range(minzoom, maxzoom + 1):
                    for arr in supermercado.burntiles.burn(cutline, zk):
                        # Supermercado's numpy scalars must be cast to
                        # ints.  Python's sqlite module does not do this
                        # for us.
                        yield mercantile.Tile(*(int(v) for v in arr))

            tiles = gen_tiles()
        else:
            tiles = mercantile.tiles(
                west, south, east, north, range(minzoom, maxzoom + 1)
            )

        with conn:
            process_tiles(
                tiles,
                init_mbtiles,
                insert_results,
                commit_mbtiles,
                num_workers=num_workers,
                inputfile=inputfile,
                base_kwds=base_kwds,
                resampling=resampling,
                img_ext=img_ext,
                image_dump=image_dump,
                progress_bar=pbar,
                open_options=open_options,
                creation_options=creation_options,
                warp_options=warp_options,
                exclude_empty_tiles=exclude_empty_tiles,
            )

            if pbar is not None:
                pbar.update(pbar.total - pbar.n)
