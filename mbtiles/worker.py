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


def init_worker(
    path,
    profile,
    resampling_method,
    open_opts=None,
    warp_opts=None,
    creation_opts=None,
    exclude_empties=True,
):
    global base_kwds, filename, resampling, open_options, warp_options, creation_options, exclude_empty_tiles
    resampling = Resampling[resampling_method]
    base_kwds = profile.copy()
    filename = path
    open_options = open_opts.copy() if open_opts is not None else {}
    warp_options = warp_opts.copy() if warp_opts is not None else {}
    creation_options = creation_opts.copy() if creation_opts is not None else {}
    exclude_empty_tiles = exclude_empties


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
    global base_kwds, resampling, filename, open_options, warp_options, creation_options, exclude_empty_tiles

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

        src_alpha = None
        dst_alpha = None
        add_alpha = False
        bindexes = None

        if kwds["count"] == 4:
            if src.count == 4:
                src_alpha = 4
                dst_alpha = 4
                bindexes = [1, 2, 3, 4]
            else:
                kwds["count"] = 3
                bindexes = [1, 2, 3]
                add_alpha = True
        else:
            bindexes = [1, 2, 3]

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
                    if (
                        exclude_empty_tiles
                        and not src.read_masks(1, window=tile_window).any()
                    ):
                        return tile, None

                except ValueError:
                    log.info(
                        "Tile %r will not be skipped, even if empty. This is harmless.",
                        tile,
                    )

                num_threads = int(warp_options.pop("num_threads", 2))

                reproject(
                    rasterio.band(src, bindexes),
                    rasterio.band(tmp, bindexes),
                    src_nodata=src_nodata,
                    dst_nodata=dst_nodata,
                    src_alpha=src_alpha,
                    dst_alpha=dst_alpha,
                    num_threads=num_threads,
                    resampling=resampling,
                    **warp_options
                )

                if len(bindexes) == 3 and add_alpha:

                    with MemoryFile() as second_memfile:
                        second_profile = kwds.copy()
                        second_profile["count"] = 4

                        with second_memfile.open(**second_profile) as second_tmp:
                            second_tmp.write(
                                tmp.read(indexes=[1, 2, 3]), indexes=[1, 2, 3]
                            )
                            second_tmp.write(tmp.dataset_mask(), indexes=4)

                        return tile, second_memfile.read()

            return tile, memfile.read()
