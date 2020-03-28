import math
import tempfile
from multiprocessing.pool import Pool
from pathlib import Path
from typing import Dict
from typing import List
from typing import NamedTuple

import click
import mercantile
import numpy as np
import psutil
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import reproject
from rasterio.warp import transform

from mbtiles import logger

TILES_CRS = "EPSG:3857"
WGS84_CRS = "EPSG:4326"

#: physical cores (at least 1, or N cores - 1)
cpu_cores = max(1, psutil.cpu_count(logical=False) - 1)

MAX_NUM_WORKERS = cpu_cores

SRC: rasterio.DatasetReader
BASE_KWDS: Dict
RESAMPLING: int
SRC_NODATA: float
DST_NODATA: float


class TileData(NamedTuple):
    tile: mercantile.Tile
    img_path: Path
    mbtile_y: int


class GeoBounds(NamedTuple):
    west: float
    south: float
    east: float
    north: float


def validate_nodata(dst_nodata, src_nodata, meta_nodata):
    """Raise BadParameter if we don't have a src nodata for a dst"""
    if dst_nodata is not None and (src_nodata is None and meta_nodata is None):
        raise click.BadParameter(
            "--src-nodata must be provided because " "dst-nodata is not None."
        )


def raster_metadata(input_file: str) -> Dict:
    """use rasterio to get metadata"""

    meta_data = {}

    with rasterio.open(input_file) as src:
        # https://github.com/sgillies/affine#usage-with-gis-data-packages
        # Use this in Affine.from_gdal(*src.transform.to_gdal())
        # to_gdal -> (x_offset, x_pixel_size, x_rotation, y_offset, y_rotation, y_pixel_size)
        # the x_offset and the y_offset are at the top-left of the raster
        gdal_transform = src.transform.to_gdal()

        # Compute the geographic bounding box of the dataset.
        (west, east), (south, north) = transform(
            src.crs, WGS84_CRS, src.bounds[::2], src.bounds[1::2]
        )
        geo_bounds = GeoBounds(west=west, south=south, east=east, north=north)

        meta_data.update(
            {
                "name": src.name,
                "shape": src.shape,  # (height, width)
                "width": src.width,
                "height": src.height,
                "nodata": src.profile.get("nodata"),
                "crs_wkt": src.crs.to_wkt(),
                "bounds": src.bounds,
                "geo_bounds": geo_bounds,
                "gdal_transform": gdal_transform,
                "x_pixel_size": abs(gdal_transform[1]),
                "y_pixel_size": abs(gdal_transform[5]),
            }
        )

    return meta_data


def init_worker(
    path,
    profile,
    resampling_method: str = "nearest",
    src_nodata: float = 0,
    dst_nodata: float = 0,
):
    global SRC, BASE_KWDS, RESAMPLING, SRC_NODATA, DST_NODATA
    RESAMPLING = Resampling[resampling_method]
    SRC = rasterio.open(path)
    BASE_KWDS = profile.copy()
    SRC_NODATA = src_nodata
    DST_NODATA = dst_nodata


def process_tile(td: TileData):
    """Process a single MBTiles tile

    The tile data is saved directly to the td.img_path

    Parameters
    ----------
    td : TileData
        A named tuple to wrap the mercantile.Tile with it's output image path and mbtile-z
    """
    global SRC, BASE_KWDS, RESAMPLING, SRC_NODATA, DST_NODATA

    tile = td.tile
    kwds = BASE_KWDS.copy()

    # Get the bounds of the tile.
    ulx, uly = mercantile.xy(*mercantile.ul(tile.x, tile.y, tile.z))
    lrx, lry = mercantile.xy(*mercantile.ul(tile.x + 1, tile.y + 1, tile.z))

    kwds["transform"] = transform_from_bounds(
        ulx, lry, lrx, uly, kwds["width"], kwds["height"]
    )

    with rasterio.open(td.img_path, "w", **kwds) as dst:
        reproject(
            rasterio.band(SRC, dst.indexes),
            rasterio.band(dst, dst.indexes),
            src_nodata=SRC_NODATA,
            dst_nodata=DST_NODATA,
            num_threads=1,
            resampling=RESAMPLING,
        )

    return td


def extract_tiles(
    input_file: str,
    image_path: Path,
    image_count: int = 3,
    image_format: str = "JPG",
    image_resampling: str = "nearest",
    src_nodata: float = 0,
    dst_nodata: float = 0,
    tile_size: int = 256,
    min_zoom: int = None,
    max_zoom: int = None,
    num_workers: int = MAX_NUM_WORKERS,
) -> List[TileData]:

    logger.info("Image outputs path: %s", image_path)
    assert image_path.exists()

    meta_data = raster_metadata(input_file)
    geo = meta_data["geo_bounds"]

    # Resolve the minimum and maximum zoom levels for export.
    if not (min_zoom and max_zoom):
        zw = int(round(math.log(360.0 / (geo.east - geo.west), 2.0)))
        zh = int(round(math.log(170.1022 / (geo.north - geo.south), 2.0)))
        min_zoom = min(zw, zh)
        max_zoom = max(zw, zh)

    logger.debug("Zoom range: %d..%d", min_zoom, max_zoom)

    # Constrain bounds.
    eps = 1.0e-10
    tile_bounds = GeoBounds(
        west=max(-180 + eps, geo.west),
        south=max(-85.051129, geo.south),
        east=min(180 - eps, geo.east),
        north=min(85.051129, geo.north),
    )

    # Initialize iterator over output tiles.
    tiles = mercantile.tiles(
        tile_bounds.west,
        tile_bounds.south,
        tile_bounds.east,
        tile_bounds.north,
        range(min_zoom, max_zoom + 1),
    )

    tile_ext = "jpg" if image_format.lower() == "jpeg" else "png"

    tile_data = []
    for tile in tiles:
        # MBTiles have a different origin than Mercantile.
        mbtile_y = int(math.pow(2, tile.z)) - tile.y - 1

        img_file_name = "%06d_%06d_%06d.%s" % (tile.z, tile.x, mbtile_y, tile_ext)
        img_file_path = image_path / img_file_name

        td = TileData(tile=tile, img_path=img_file_path, mbtile_y=mbtile_y)
        tile_data.append(td)

    # Parameters for creation of tile images.
    dst_profile = {
        "driver": image_format.upper(),
        "dtype": "uint8",
        "nodata": 0,
        "height": tile_size,
        "width": tile_size,
        "count": image_count,
        "crs": TILES_CRS,
    }

    # Create a pool of workers and process tile tasks.
    #
    # TODO: explore dask.distributed workers with init-worker
    #       https://docs.dask.org/en/latest/setup/custom-startup.html
    #

    B2MB = 1048576
    B2GB = 1073741824
    mem = psutil.virtual_memory()
    src_mem = (
        image_count
        * meta_data["width"]
        * meta_data["height"]
        * np.dtype(np.uint8).itemsize
    )

    # use mem.free rather than mem.available to avoid major page faults
    max_mem_cores = int(mem.free / src_mem)
    if max_mem_cores < 1:
        logger.warning("Tile extraction could run out of memory")
        max_mem_cores = 1

    logger.info("Memory total:\t\t%016.4f Mb", mem.total / B2MB)
    logger.info("Memory available:\t%016.4f Mb", mem.available / B2MB)
    logger.info("Memory free:\t\t%016.4f Mb", mem.free / B2MB)
    logger.info("Memory estimate:\t%016.4f Mb", src_mem / B2MB)
    logger.info("N cores for max_mem:\t%d", max_mem_cores)

    worker_args = (input_file, dst_profile, image_resampling, src_nodata, dst_nodata)
    max_workers = min(MAX_NUM_WORKERS, num_workers, max_mem_cores)
    logger.info("N physical cores - 1:\t%d", MAX_NUM_WORKERS)
    logger.info("N process workers:\t%d", max_workers)

    if max_workers > 1:
        task_chunks = max_workers
        max_tasks = None  # None == process lives as long as the Pool
        with Pool(
            processes=max_workers,
            initializer=init_worker,
            initargs=worker_args,
            maxtasksperchild=max_tasks,
        ) as pool:
            for td in pool.imap_unordered(process_tile, tile_data, task_chunks):
                assert td.img_path.exists()
    else:
        init_worker(*worker_args)
        for td in map(process_tile, tile_data):
            assert td.img_path.exists()

    return tile_data
