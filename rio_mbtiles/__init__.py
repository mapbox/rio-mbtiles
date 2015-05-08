import sys

import mercantile
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio._io import virtual_file_to_buffer


buffer = bytes if sys.version_info > (3,) else buffer

base_kwds = None
src = None


def init_worker(path, profile):
    global base_kwds, src
    base_kwds = profile.copy()
    src = rasterio.open(path)


def process_tile(tile):
    """Process a single MBTiles tile."""
    global base_kwds, src
    # Get the bounds of the tile.
    ulx, uly = mercantile.xy(
        *mercantile.ul(tile.x, tile.y, tile.z))
    lrx, lry = mercantile.xy(
        *mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

    kwds = base_kwds.copy()
    kwds['transform'] = from_bounds(ulx, lry, lrx, uly, 256, 256)

    with rasterio.open('/vsimem/tileimg', 'w', **kwds) as tmp:
        # Reproject the src dataset into image tile.
        for bidx in tmp.indexes:
            reproject(
                rasterio.band(src, bidx),
                rasterio.band(tmp, bidx))

    # Get contents of the virtual file and repair it.
    contents = bytearray(virtual_file_to_buffer('/vsimem/tileimg'))
    return tile, contents[-1:] + contents[:-1]
