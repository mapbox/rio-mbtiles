import mercantile

import rio_mbtiles


def test_process_tile(data):
    tile = mercantile.Tile(36, 73, 7)
    tile, contents = rio_mbtiles.process_tile((
        mercantile.Tile(36, 73, 7), {
            'driver': 'PNG',
            'dtype': 'uint8',
            'nodata': 0,
            'height': 256,
            'width': 256,
            'count': 3,
            'crs': 'EPSG:3857'},
        str(data.join('RGB.byte.tif'))))
    assert tile.x == 36
    assert tile.y == 73
    assert tile.z == 7
