import sys

import mercantile
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from rasterio._io import virtual_file_to_buffer


buffer = bytes if sys.version_info > (3,) else buffer


def process_tile(arg):
    """Process a single MBTiles tile."""
    tile, base_kwds, inputfile = arg
    # Get the bounds of the tile.
    ulx, uly = mercantile.xy(
        *mercantile.ul(tile.x, tile.y, tile.z))
    lrx, lry = mercantile.xy(
        *mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

    kwds = base_kwds.copy()
    kwds['transform'] = from_bounds(ulx, lry, lrx, uly, 256, 256)

    with rasterio.open('/vsimem/tileimg', 'w', **kwds) as tmp:
        with rasterio.open(inputfile) as src:
            # Reproject the src dataset into image tile.
            for bidx in tmp.indexes:
                reproject(
                    rasterio.band(src, bidx),
                    rasterio.band(tmp, bidx))

    # Get contents of the virtual file and repair it.
    contents = bytearray(virtual_file_to_buffer('/vsimem/tileimg'))
    return tile, contents[-1:] + contents[:-1]
