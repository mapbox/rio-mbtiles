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
    progress_bar=None,
):
    """Warp imagery into tiles and commit to mbtiles database.
    """
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

            group = islice(tiles, len(done))
            for tile in group:
                futures.add(executor.submit(process_tile, tile))

            for future in done:
                tile, contents = future.result()
                insert_results(
                    cur, tile, contents, img_ext=img_ext, image_dump=image_dump
                )

            conn.commit()

            if progress_bar is not None:
                if progress_bar.n + len(done) < progress_bar.total:
                    progress_bar.update(len(done))
