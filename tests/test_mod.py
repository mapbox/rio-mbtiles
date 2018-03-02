import mercantile
import pytest
import rasterio

import mbtiles


@pytest.mark.parametrize("tile_size", (256, 512))
def test_process_tile(data, tile_size):
    mbtiles.init_worker(str(data.join('RGB.byte.tif')), {
            'driver': 'PNG',
            'dtype': 'uint8',
            'nodata': 0,
            'height': tile_size,
            'width': tile_size,
            'count': 3,
            'crs': 'EPSG:3857'},
            'nearest')
    tile, contents = mbtiles.process_tile(mercantile.Tile(36, 73, 7))
    assert tile.x == 36
    assert tile.y == 73
    assert tile.z == 7
    assert contents.shape == (tile_size, tile_size)
