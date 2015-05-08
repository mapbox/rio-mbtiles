import mercantile
import rasterio

import rio_mbtiles


def test_process_tile(data):
    rio_mbtiles.init_worker(str(data.join('RGB.byte.tif')), {
            'driver': 'PNG',
            'dtype': 'uint8',
            'nodata': 0,
            'height': 256,
            'width': 256,
            'count': 3,
            'crs': 'EPSG:3857'})
    tile, contents = rio_mbtiles.process_tile(mercantile.Tile(36, 73, 7))
    assert tile.x == 36
    assert tile.y == 73
    assert tile.z == 7
