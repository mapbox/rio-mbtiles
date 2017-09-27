# Mbtiles command.

import logging
import math
from multiprocessing import cpu_count, Pool
import os
import sqlite3

import click
import mercantile
import rasterio
from rasterio.enums import Resampling
from rasterio.rio.helpers import resolve_inout
from rasterio.rio.options import force_overwrite_opt, output_opt
from rasterio.warp import transform

from mbtiles import buffer, init_worker, process_tile
from mbtiles import __version__ as mbtiles_version


DEFAULT_NUM_WORKERS = cpu_count() - 1
RESAMPLING_METHODS = [method.name for method in Resampling]


def validate_nodata(dst_nodata, src_nodata, meta_nodata):
    """Raise BadParameter if we don't have a src nodata for a dst"""
    if dst_nodata is not None and (src_nodata is None and meta_nodata is None):
        raise click.BadParameter("--src-nodata must be provided because "
                                 "dst-nodata is not None.")


@click.command(short_help="Export a dataset to MBTiles.")
@click.argument(
    'files',
    nargs=-1,
    type=click.Path(resolve_path=True),
    required=True,
    metavar="INPUT [OUTPUT]")
@output_opt
@force_overwrite_opt
@click.option('--title', help="MBTiles dataset title.")
@click.option('--description', help="MBTiles dataset description.")
@click.option('--overlay', 'layer_type', flag_value='overlay', default=True,
              help="Export as an overlay (the default).")
@click.option('--baselayer', 'layer_type', flag_value='baselayer',
              help="Export as a base layer.")
@click.option('-f', '--format', 'img_format', type=click.Choice(['JPEG', 'PNG']),
              default='JPEG',
              help="Tile image format.")
@click.option('--zoom-levels',
              default=None,
              metavar="MIN..MAX",
              help="A min...max range of export zoom levels. "
                   "The default zoom level "
                   "is the one at which the dataset is contained within "
                   "a single tile.")
@click.option('--image-dump',
              metavar="PATH",
              help="A directory into which image tiles will be optionally "
                   "dumped.")
@click.option('-j', 'num_workers', type=int, default=DEFAULT_NUM_WORKERS,
              help="Number of worker processes (default: %d)." % (
                  DEFAULT_NUM_WORKERS))
@click.option('--src-nodata', default=None, show_default=True,
              type=float, help="Manually override source nodata")
@click.option('--dst-nodata', default=None, show_default=True,
              type=float, help="Manually override destination nodata")
@click.option('--resampling', type=click.Choice(RESAMPLING_METHODS),
              default='nearest', show_default=True,
              help="Resampling method to use.")
@click.version_option(version=mbtiles_version, message='%(version)s')
@click.pass_context
def mbtiles(ctx, files, output, force_overwrite, title, description,
            layer_type, img_format, zoom_levels, image_dump, num_workers,
            src_nodata, dst_nodata, resampling):
    """Export a dataset to MBTiles (version 1.1) in a SQLite file.

    The input dataset may have any coordinate reference system. It must
    have at least three bands, which will be become the red, blue, and
    green bands of the output image tiles.

    If no zoom levels are specified, the defaults are the zoom levels
    nearest to the one at which one tile may contain the entire source
    dataset.

    If a title or description for the output file are not provided,
    they will be taken from the input dataset's filename.

    This command is suited for small to medium (~1 GB) sized sources.

    Python package: rio-mbtiles (https://github.com/mapbox/rio-mbtiles).
    """
    output, files = resolve_inout(files=files, output=output,
                                  force_overwrite=force_overwrite)
    inputfile = files[0]

    logger = logging.getLogger('rio-mbtiles')

    with ctx.obj['env']:

        # Read metadata from the source dataset.
        with rasterio.open(inputfile) as src:

            validate_nodata(dst_nodata, src_nodata, src.profile.get('nodata'))
            base_kwds = {'dst_nodata': dst_nodata, 'src_nodata': src_nodata}

            if src_nodata is not None:
                base_kwds.update(nodata=src_nodata)

            if dst_nodata is not None:
                base_kwds.update(nodata=dst_nodata)

            # Name and description.
            title = title or os.path.basename(src.name)
            description = description or src.name

            # Compute the geographic bounding box of the dataset.
            (west, east), (south, north) = transform(
                src.crs, 'EPSG:4326', src.bounds[::2], src.bounds[1::2])

        # Resolve the minimum and maximum zoom levels for export.
        if zoom_levels:
            minzoom, maxzoom = map(int, zoom_levels.split('..'))
        else:
            zw = int(round(math.log(360.0 / (east - west), 2.0)))
            zh = int(round(math.log(170.1022 / (north - south), 2.0)))
            minzoom = min(zw, zh)
            maxzoom = max(zw, zh)

        logger.debug("Zoom range: %d..%d", minzoom, maxzoom)

        # Parameters for creation of tile images.
        base_kwds.update({
            'driver': img_format.upper(),
            'dtype': 'uint8',
            'nodata': 0,
            'height': 256,
            'width': 256,
            'count': 3,
            'crs': 'EPSG:3857'})

        img_ext = 'jpg' if img_format.lower() == 'jpeg' else 'png'

        # Initialize the sqlite db.
        if os.path.exists(output):
            os.unlink(output)
        conn = sqlite3.connect(output)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE tiles "
            "(zoom_level integer, tile_column integer, "
            "tile_row integer, tile_data blob);")
        cur.execute(
            "CREATE TABLE metadata (name text, value text);")

        # Insert mbtiles metadata into db.
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("name", title))
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("type", layer_type))
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("version", "1.1"))
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("description", description))
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("format", img_ext))
        cur.execute(
            "INSERT INTO metadata (name, value) VALUES (?, ?);",
            ("bounds", "%f,%f,%f,%f" % (west, south, east, north)))

        conn.commit()

        # Create a pool of workers to process tile tasks.
        pool = Pool(num_workers, init_worker,
                    (inputfile, base_kwds, resampling), 100)

        # Constrain bounds.
        EPS = 1.0e-10
        west = max(-180 + EPS, west)
        south = max(-85.051129, south)
        east = min(180 - EPS, east)
        north = min(85.051129, north)

        # Initialize iterator over output tiles.
        tiles = mercantile.tiles(
            west, south, east, north, range(minzoom, maxzoom + 1))

        for tile, contents in pool.imap_unordered(process_tile, tiles):

            # MBTiles has a different origin than Mercantile/tilebelt.
            tiley = int(math.pow(2, tile.z)) - tile.y - 1

            # Optional image dump.
            if image_dump:
                img_name = '%d-%d-%d.%s' % (
                    tile.x, tiley, tile.z, img_ext)
                img_path = os.path.join(image_dump, img_name)
                with open(img_path, 'wb') as img:
                    img.write(contents)

            # Insert tile into db.
            cur.execute(
                "INSERT INTO tiles "
                "(zoom_level, tile_column, tile_row, tile_data) "
                "VALUES (?, ?, ?, ?);",
                (tile.z, tile.x, tiley, buffer(contents)))

            conn.commit()

        conn.close()
        # Done!
