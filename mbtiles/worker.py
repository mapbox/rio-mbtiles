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


base_kwds = None
src = None

TILES_CRS = "EPSG:3857"

log = logging.getLogger(__name__)


def init_worker(path, profile, resampling_method):
    global base_kwds, filename, resampling
    resampling = Resampling[resampling_method]
    # src = rasterio.open(path)
    base_kwds = profile.copy()
    filename = path


def process_tile(tile):
    """Process a single MBTiles tile

    Parameters
    ----------
    tile : mercantile.Tile

    Returns
    -------

    tile : mercantile.Tile
        The input tile.
    bytes : bytearray
        Image bytes corresponding to the tile.

    """
    global base_kwds, resampling, filename

    src = rasterio.open(filename)

    # Get the bounds of the tile.
    ulx, uly = mercantile.xy(*mercantile.ul(tile.x, tile.y, tile.z))
    lrx, lry = mercantile.xy(*mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

    kwds = base_kwds.copy()
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

            reproject(
                rasterio.band(src, tmp.indexes),
                rasterio.band(tmp, tmp.indexes),
                src_nodata=src_nodata,
                dst_nodata=dst_nodata,
                num_threads=2,
                resampling=resampling,
            )

        return tile, memfile.read()
