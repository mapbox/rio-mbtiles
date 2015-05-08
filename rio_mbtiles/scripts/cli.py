# Mbtiles command.

import logging
import math
from multiprocessing import Pool
import os
import sqlite3
import sys

import click
import mercantile
import rasterio
from rasterio.rio.cli import cli, output_opt, resolve_inout
from rasterio.warp import transform

from rio_mbtiles import buffer, init_worker, process_tile


@cli.command(short_help="Export a dataset to MBTiles.")
@click.argument(
    'files',
    nargs=-1,
    type=click.Path(resolve_path=True),
    required=True,
    metavar="INPUT [OUTPUT]")
@click.option(
    '-o', '--output', 'output_opt',
    default=None,
    type=click.Path(resolve_path=True),
    help="Path to output file (optional alternative to a positional arg "
         "for some commands).")
@click.option('--title', help="MBTiles dataset title.")
@click.option('--description', help="MBTiles dataset description.")
@click.option('--overlay', 'layer_type', flag_value='overlay', default=True,
              help="Export as an overlay (the default).")
@click.option('--baselayer', 'layer_type', flag_value='baselayer',
              help="Export as a base layer.")
@click.option('--format', 'img_format', type=click.Choice(['JPEG', 'PNG']),
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
@click.option('-j', 'num_workers', type=int, default=1,
              help="Number of worker processes (default: 1).")
@click.pass_context
def mbtiles(ctx, files, output_opt, title, description, layer_type,
            img_format, zoom_levels, image_dump, num_workers):
    """Export a dataset to MBTiles (version 1.1) in a SQLite file.

    The input dataset may have any coordinate reference system. It must
    have at least three bands, which will be become the red, blue, and
    green bands of the output image tiles.

    If no zoom levels are specified, the defaults are the zoom levels
    nearest to the one at which one tile may contain the entire source
    dataset.

    If a title or description for the output file are not provided,
    they will be taken from the input dataset's filename.
    """

    verbosity = (ctx.obj and ctx.obj.get('verbosity')) or 1
    logger = logging.getLogger('rio')

    output, files = resolve_inout(files=files, output=output_opt)
    inputfile = files[0]

    with rasterio.drivers(CPL_DEBUG=verbosity > 2):

        # Read metadata from the source dataset.
        with rasterio.open(inputfile) as src:

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
            zw = int(round(math.log(360.0/(east-west), 2.0)))
            zh = int(round(math.log(170.1022/(north-south), 2.0)))
            minzoom = min(zw, zh)
            maxzoom = max(zw, zh)
        logger.debug("Zoom range: %d..%d", minzoom, maxzoom)

        # Parameters for creation of tile images.
        base_kwds = {
            'driver': img_format.upper(),
            'dtype': 'uint8',
            'nodata': 0,
            'height': 256,
            'width': 256,
            'count': 3,
            'crs': 'EPSG:3857'}

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

        # Create a pool of workers to process tile tasks.
        pool = Pool(num_workers, init_worker, (inputfile, base_kwds), 100)

        tiles = list(mercantile.tiles(
            west, south, east, north, range(minzoom, maxzoom+1)))

        # Adaptive chunksize.
        chunksize = max(1, int(round(len(tiles)/num_workers)))

        for tile, contents in pool.imap_unordered(
                process_tile, tiles, chunksize):

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

        sys.exit(0)
