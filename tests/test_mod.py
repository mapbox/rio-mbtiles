import mercantile
import rasterio

import mbtiles


def test_process_tile(data):
    mbtiles.init_worker(str(data.join('RGB.byte.tif')), {
            'driver': 'PNG',
            'dtype': 'uint8',
            'nodata': 0,
            'height': 256,
            'width': 256,
            'count': 3,
            'crs': 'EPSG:3857'},
            "nearest")
    tile, contents = mbtiles.process_tile(mercantile.Tile(36, 73, 7))
    assert tile.x == 36
    assert tile.y == 73
    assert tile.z == 7
