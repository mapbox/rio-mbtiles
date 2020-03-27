# multiprocessing Pool implementation

from multiprocessing import Pool

from mbtiles.compat import zip_longest
from mbtiles.worker import init_worker, process_tile

BATCH_SIZE = 100


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


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
    pool = Pool(num_workers, init_worker, (inputfile, base_kwds, resampling), BATCH_SIZE)

    for group in grouper(pool.imap_unordered(process_tile, tiles), BATCH_SIZE):
        for item in group:
            if item is None:
                break
            tile, contents = item
            insert_results(conn, tile, contents, img_ext=img_ext, image_dump=image_dump)

        conn.commit()
