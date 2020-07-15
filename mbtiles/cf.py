# concurrent.futures implementation

import concurrent.futures
from itertools import islice
import logging

from mbtiles.worker import init_worker, process_tile

BATCH_SIZE = 100

log = logging.getLogger(__name__)


def process_tiles(
    conn,
    tiles,
    insert_results,
    num_workers=None,
    inputfile=None,
    base_kwds=None,
    resampling=None,
    img_ext=None,
    image_dump=None,
):
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=init_worker,
        initargs=(inputfile, base_kwds, resampling),
    ) as executor:
        cur = conn.cursor()
        group = islice(tiles, BATCH_SIZE)
        futures = {executor.submit(process_tile, tile) for tile in group}

        while futures:
            done, futures = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )

            for future in done:
                tile, contents = future.result()
                insert_results(
                    cur, tile, contents, img_ext=img_ext, image_dump=image_dump
                )

            group = islice(tiles, len(done))
            for tile in group:
                futures.add(executor.submit(process_tile, tile))

            conn.commit()
