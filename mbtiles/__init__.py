"""mbtiles worker"""

import sys

import mercantile
import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio.io import MemoryFile
from rasterio._io import virtual_file_to_buffer

buffer = bytes if sys.version_info > (3,) else buffer

__version__ = '1.4.0'

base_kwds = None
src = None


def init_worker(path, profile, resampling_method):
    global base_kwds, src, resampling
    resampling = Resampling[resampling_method]
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
    global base_kwds, resampling, src
    # Get the bounds of the tile.
    ulx, uly = mercantile.xy(
        *mercantile.ul(tile.x, tile.y, tile.z))
    lrx, lry = mercantile.xy(
        *mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

    kwds = base_kwds.copy()
    kwds['transform'] = from_bounds(ulx, lry, lrx, uly, 256, 256)
    src_nodata = kwds.pop('src_nodata', None)
    dst_nodata = kwds.pop('dst_nodata', None)
    kwds['driver'] = 'GTiff'

    # Reproject into a GeoTIFF tile.
    with MemoryFile() as memdst:
        with memdst.open(**kwds) as tiledst:
            reproject(
                rasterio.band(src, src.indexes),
                rasterio.band(tiledst, tiledst.indexes),
                src_nodata=src_nodata, dst_nodata=dst_nodata, num_threads=2,
                resampling=resampling)

        # If the tiledst dataset has any valid data, we read and return it.
        # Otherwise, we return None.
        #
        # To save time, we check the only mask of the first band for
        # valid data.
        with memdst.open() as tiledst:
            mask = tiledst.read_masks(1)
            if mask.any():
                # We're using MemoryFile to get a filename from
                # the in-memory filesystem only; it doesn't support
                # copy yet.
                with MemoryFile() as memimg:
                    copy(tiledst, memimg.name, driver=base_kwds['driver'])
                    img_bytes = bytearray(virtual_file_to_buffer(memimg.name))
                # Workaround for https://bugs.python.org/issue23349.
                if sys.version_info[0] == 2 and sys.version_info[2] < 10:
                    img_bytes[:] = img_bytes[-1:] + img_bytes[:-1]
            else:
                img_bytes = None

    return tile, img_bytes
