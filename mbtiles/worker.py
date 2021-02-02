"""rio-mbtiles processing worker"""

import logging
import warnings

from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window
from rasterio.windows import from_bounds as window_from_bounds
import mercantile
import rasterio

TILES_CRS = "EPSG:3857"

log = logging.getLogger(__name__)


def init_worker(path, profile, resampling_method, open_opts=None, warp_opts=None, creation_opts=None):
    global base_kwds, filename, resampling, open_options, warp_options, creation_options
    resampling = Resampling[resampling_method]
    base_kwds = profile.copy()
    filename = path
    open_options = open_opts.copy() if open_opts is not None else {}
    warp_options = warp_opts.copy() if warp_opts is not None else {}
    creation_options = creation_opts.copy() if creation_opts is not None else {}


def process_tile(tile):
    """Process a single MBTiles tile

    Parameters
    ----------
    tile : mercantile.Tile
    warp_options : Mapping
        GDAL warp options as keyword arguments.

    Returns
    -------

    tile : mercantile.Tile
        The input tile.
    bytes : bytearray
        Image bytes corresponding to the tile.

    """
    global base_kwds, resampling, filename, open_options, warp_options, creation_options

    with rasterio.open(filename, **open_options) as src:

        # Get the bounds of the tile.
        ulx, uly = mercantile.xy(*mercantile.ul(tile.x, tile.y, tile.z))
        lrx, lry = mercantile.xy(*mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

        kwds = base_kwds.copy()
        kwds.update(**creation_options)
        kwds["transform"] = transform_from_bounds(
            ulx, lry, lrx, uly, kwds["width"], kwds["height"]
        )
        src_nodata = kwds.pop("src_nodata", None)
        dst_nodata = kwds.pop("dst_nodata", None)

        warnings.simplefilter("ignore")

        log.info("Reprojecting tile: tile=%r", tile)

        with MemoryFile() as memfile:

            with memfile.open(**kwds) as tmp:

                # determine window of source raster corresponding to the tile
                # image, with small buffer at edges
                try:
                    west, south, east, north = transform_bounds(
                        TILES_CRS, src.crs, ulx, lry, lrx, uly
                    )
                    tile_window = window_from_bounds(
                        west, south, east, north, transform=src.transform
                    )
                    adjusted_tile_window = Window(
                        tile_window.col_off - 1,
                        tile_window.row_off - 1,
                        tile_window.width + 2,
                        tile_window.height + 2,
                    )
                    tile_window = adjusted_tile_window.round_offsets().round_shape()

                    # if no data in window, skip processing the tile
                    if not src.read_masks(1, window=tile_window).any():
                        return tile, None

                except ValueError:
                    log.info(
                        "Tile %r will not be skipped, even if empty. This is harmless.",
                        tile,
                    )

                num_threads = int(warp_options.pop("num_threads", 2))

                reproject(
                    rasterio.band(src, tmp.indexes),
                    rasterio.band(tmp, tmp.indexes),
                    src_nodata=src_nodata,
                    dst_nodata=dst_nodata,
                    num_threads=num_threads,
                    resampling=resampling,
                    **warp_options
                )

            return tile, memfile.read()
