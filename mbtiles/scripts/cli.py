# Mbtiles command.

import logging
import math
import os
import sqlite3
import sys

import click
import mercantile
import rasterio
from rasterio.enums import Resampling
from rasterio.rio.helpers import resolve_inout
from rasterio.rio.options import overwrite_opt, output_opt
from rasterio.warp import transform
from tqdm import tqdm

from mbtiles import __version__ as mbtiles_version


DEFAULT_NUM_WORKERS = None
RESAMPLING_METHODS = [method.name for method in Resampling]
TILES_CRS = "EPSG:3857"

log = logging.getLogger(__name__)


@click.command(short_help="Export a dataset to MBTiles.")
@click.argument(
    "files",
    nargs=-1,
    type=click.Path(resolve_path=True),
    required=True,
    metavar="INPUT [OUTPUT]",
)
@output_opt
@overwrite_opt
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
    type=click.Choice(["JPEG", "PNG"]),
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
    "--rgba", default=False, is_flag=True, help="Select RGBA output. For PNG only."
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
@click.pass_context
def mbtiles(
    ctx,
    files,
    output,
    overwrite,
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
):
    """Export a dataset to MBTiles (version 1.1) in a SQLite file.

    The input dataset may have any coordinate reference system. It must
    have at least three bands, which will be become the red, blue, and
    green bands of the output image tiles.

    An optional fourth alpha band may be copied to the output tiles by
    using the --rgba option in combination with the PNG format. This
    option requires that the input dataset has at least 4 bands.

    If no zoom levels are specified, the defaults are the zoom levels
    nearest to the one at which one tile may contain the entire source
    dataset.

    If a title or description for the output file are not provided,
    they will be taken from the input dataset's filename.

    This command is suited for small to medium (~1 GB) sized sources.

    Python package: rio-mbtiles (https://github.com/mapbox/rio-mbtiles).

    """
    output, files = resolve_inout(files=files, output=output, overwrite=overwrite)
    inputfile = files[0]

    log = logging.getLogger(__name__)

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
        with rasterio.open(inputfile) as src:

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

        img_ext = "jpg" if img_format.lower() == "jpeg" else "png"

        # Initialize the sqlite db.
        if os.path.exists(output):
            os.unlink(output)

        # workaround for bug here: https://bugs.python.org/issue27126
        sqlite3.connect(":memory:").close()

        conn = sqlite3.connect(output)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE tiles "
            "(zoom_level integer, tile_column integer, "
            "tile_row integer, tile_data blob);"
        )
        cur.execute("CREATE TABLE metadata (name text, value text);")

        # Insert mbtiles metadata into db.
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);", ("name", title)
        )
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);", ("type", layer_type)
        )
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);", ("version", "1.1")
        )
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("description", description),
        )
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);", ("format", img_ext)
        )
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("bounds", "%f,%f,%f,%f" % (west, south, east, north)),
        )

        conn.commit()

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

            while ratio < 16:
                est_num_tiles += len(
                    list(mercantile.tiles(west, south, east, north, [zoom]))
                )
                zoom += 1
                ratio *= 4.0

            est_num_tiles += int(
                sum(
                    math.ceil(math.pow(4.0, z - minzoom) * min_ratio)
                    for z in range(zoom, maxzoom + 1)
                )
            )

            pbar = tqdm(total=est_num_tiles)

        else:
            pbar = None

        # Initialize iterator over output tiles.
        tiles = mercantile.tiles(west, south, east, north, range(minzoom, maxzoom + 1))

        def insert_results(cursor, tile, contents, img_ext=None, image_dump=None):
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
                "INSERT INTO tiles "
                "(zoom_level, tile_column, tile_row, tile_data) "
                "VALUES (?, ?, ?, ?);",
                (tile.z, tile.x, tiley, sqlite3.Binary(contents)),
            )

        process_tiles(
            conn,
            tiles,
            insert_results,
            num_workers=num_workers,
            inputfile=inputfile,
            base_kwds=base_kwds,
            resampling=resampling,
            img_ext=img_ext,
            image_dump=image_dump,
            progress_bar=pbar,
        )

        if pbar is not None:
            pbar.update(pbar.total - pbar.n)

        conn.commit()
        conn.close()
