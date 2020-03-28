# Mbtiles command.
import os
import tempfile
from pathlib import Path

import click
from rasterio.enums import Resampling
from rasterio.rio.helpers import resolve_inout
from rasterio.rio.options import output_opt
from rasterio.rio.options import overwrite_opt

from mbtiles import __version__ as mbtiles_version
from mbtiles import logger
from mbtiles.aio_mbtiles import run_save_mbtiles
from mbtiles.tiles import extract_tiles
from mbtiles.tiles import MAX_NUM_WORKERS
from mbtiles.tiles import raster_metadata
from mbtiles.tiles import TILES_CRS
from mbtiles.tiles import validate_nodata

RESAMPLING_METHODS = [method.name for method in Resampling]


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
    default=MAX_NUM_WORKERS,
    help="Number of worker processes (default: %d)." % MAX_NUM_WORKERS,
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
    input_file = files[0]

    if image_dump:
        tile_path = Path(image_dump)
        tile_path.mkdir(parents=True, exist_ok=True)
    else:
        tile_directory = tempfile.TemporaryDirectory(prefix="rio_mbtiles_")
        tile_path = Path(tile_directory.name)

    if zoom_levels:
        min_zoom, max_zoom = map(int, zoom_levels.split(".."))
    else:
        min_zoom = None  # it will be estimated from the data
        max_zoom = None

    img_ext = "jpg" if img_format.lower() == "jpeg" else "png"
    if rgba:
        if img_format == "JPEG":
            raise click.BadParameter("RGBA output is not possible with JPEG format.")
        else:
            band_count = 4
    else:
        band_count = 3

    with ctx.obj["env"]:

        meta_data = raster_metadata(input_file)
        validate_nodata(dst_nodata, src_nodata, meta_data.get("nodata"))
        if src_nodata is not None:
            meta_data.update(nodata=src_nodata)
        if dst_nodata is not None:
            meta_data.update(nodata=dst_nodata)

        tile_data = extract_tiles(
            input_file,
            image_path=tile_path,
            image_count=band_count,
            image_format=img_format,
            image_resampling=resampling,
            src_nodata=src_nodata,
            dst_nodata=dst_nodata,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            tile_size=tile_size,
            num_workers=num_workers,
        )

        # Initialize the sqlite db.
        if os.path.exists(output):
            os.unlink(output)

        # Name and description.
        title = title or os.path.basename(meta_data["name"])
        description = description or title

        logger.info("Saving mbtiles to:\t%s", output)
        geo = meta_data["geo_bounds"]
        metadata_values = [
            {"name": "name", "value": title},
            {"name": "type", "value": layer_type},
            {"name": "version", "value": "1.1"},
            {"name": "description", "value": description},
            {"name": "format", "value": img_ext},
            {
                "name": "bounds",
                "value": "%f,%f,%f,%f" % (geo.west, geo.south, geo.east, geo.north),
            },
        ]
        run_save_mbtiles(output, tile_data, metadata_values)
        logger.info("Saved mbtiles to:\t%s", output)
