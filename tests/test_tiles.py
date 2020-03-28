"""Module tests"""
import tempfile
from pathlib import Path

from mercantile import Tile
import pytest

import mbtiles.tiles


@pytest.mark.parametrize("tile", [Tile(36, 73, 7), Tile(0, 0, 0), Tile(1, 1, 1)])
@pytest.mark.parametrize("filename", ["RGB.byte.tif", "RGBA.byte.tif"])
def test_process_tile(data, filename: str, tile: Tile):
    src_path = str(data.join(filename))

    tile_directory = tempfile.TemporaryDirectory(prefix="test_rio_mbtiles_")
    tile_path = Path(tile_directory.name)

    dst_profile = {
        "driver": "PNG",
        "dtype": "uint8",
        "nodata": 0,
        "height": 256,
        "width": 256,
        "count": 3,
        "crs": "EPSG:3857",
    }

    img_file_name = "%06d_%06d_%06d.%s" % (tile.z, tile.x, tile.y, "png")
    img_file_path = tile_path / img_file_name

    td = mbtiles.tiles.TileData(
        tile=tile, img_path=img_file_path, mbtile_y=tile.y  # hack for test
    )

    mbtiles.tiles.init_worker(src_path, dst_profile)
    mbtiles.tiles.process_tile(td)
    assert img_file_path.exists()
