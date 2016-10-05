import sys

import mercantile
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio._io import virtual_file_to_buffer


buffer = bytes if sys.version_info > (3,) else buffer

__version__ = '1.3.0'

base_kwds = None
src = None


def init_worker(path, profile):
    global base_kwds, src
    base_kwds = profile.copy()
    src = rasterio.open(path)


def process_tile(tile):
    """Process a single MBTiles tile

    Parameters
    ----------
    tile : mercantile.Tile

    Returns:
    tile : mercantile.Tile
        The input tile.
    bytes : bytearray
        Image bytes corresponding to the tile.
    """
    global base_kwds, src
    # Get the bounds of the tile.
    ulx, uly = mercantile.xy(
        *mercantile.ul(tile.x, tile.y, tile.z))
    lrx, lry = mercantile.xy(
        *mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

    kwds = base_kwds.copy()
    kwds['transform'] = from_bounds(ulx, lry, lrx, uly, 256, 256)
    src_nodata = kwds.pop('src_nodata', None)
    dst_nodata = kwds.pop('dst_nodata', None)

    with rasterio.open('/vsimem/tileimg', 'w', **kwds) as tmp:
        reproject(rasterio.band(src, src.indexes),
                  rasterio.band(tmp, tmp.indexes),
                  src_nodata=src_nodata,
                  dst_nodata=dst_nodata,
                  num_threads=1)

    data = bytearray(virtual_file_to_buffer('/vsimem/tileimg'))

    # Workaround for https://bugs.python.org/issue23349.
    if sys.version_info[0] == 2 and sys.version_info[2] < 10:
        data[:] = data[-1:] + data[:-1]

    return tile, data
