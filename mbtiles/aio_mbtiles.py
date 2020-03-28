# AioMbtiles
import asyncio
import sqlite3
from typing import Dict
from typing import List
from typing import NamedTuple

import aiosqlite
from aiofile import AIOFile
from aiosqlite import Connection

from mbtiles.tiles import TileData


async def sqlite_create_mbtiles(conn: Connection):
    """
    Setup mbtiles database
    """

    query = "DROP TABLE IF EXISTS metadata;"
    await conn.execute(query)
    query = "CREATE TABLE metadata (name text, value text);"
    await conn.execute(query)

    query = "DROP TABLE IF EXISTS tiles;"
    await conn.execute(query)
    query = (
        "CREATE TABLE tiles (zoom_level integer, tile_column integer, tile_row integer, "
        "tile_data blob);"
    )
    await conn.execute(query)
    await conn.commit()


async def sqlite_insert_metadata(conn: Connection, values: List[Dict]):
    insert_metadata = "INSERT INTO metadata (name, value) VALUES (?, ?);"
    for value in values:
        insert_values = (value["name"], value["value"])
        await conn.execute(insert_metadata, insert_values)
    await conn.commit()


class TileValues(NamedTuple):
    zoom_level: int
    tile_column: int
    tile_row: int
    tile_data: memoryview


async def sqlite_insert_tile(conn: Connection, values: TileValues):
    insert_tiles = (
        "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data)"
        "VALUES (?, ?, ?, ?);"
    )
    await conn.execute(insert_tiles, values)
    await conn.commit()


async def insert_tile(conn: Connection, td: TileData):

    async with AIOFile(str(td.img_path), "rb") as aio_img:
        contents = await aio_img.read()

    # Insert tile into db.
    tile_values = TileValues(
        zoom_level=td.tile.z,
        tile_column=td.tile.x,
        tile_row=td.mbtile_y,
        tile_data=sqlite3.Binary(contents),
    )
    await sqlite_insert_tile(conn, tile_values)


async def save_mbtiles(output: str, tile_data: List[TileData], metadata: List[Dict]):
    async with aiosqlite.connect(output) as db:
        await sqlite_create_mbtiles(db)
        await sqlite_insert_metadata(db, metadata)
        for td in tile_data:
            await insert_tile(db, td)
        await db.commit()


def run_save_mbtiles(output: str, tile_data: List[TileData], metadata: List[Dict]):
    main_loop = asyncio.new_event_loop()
    try:
        main_loop.run_until_complete(save_mbtiles(output, tile_data, metadata))
    finally:
        main_loop.stop()
        main_loop.close()
