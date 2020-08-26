# multiprocessing Pool implementation

from multiprocessing import Pool
import warnings

from mbtiles.compat import zip_longest
from mbtiles.worker import init_worker, process_tile

BATCH_SIZE = 100

warnings.warn(
    "The multiprocessing.Pool implementation will be removed in rio-mbtiles 2.0.0.",
    FutureWarning,
    stacklevel=2,
)


def process_tiles(
    tiles,
    init_mbtiles,
    insert_results,
    commit_mbtiles,
    num_workers=None,
    inputfile=None,
    base_kwds=None,
    resampling=None,
    img_ext=None,
    image_dump=None,
    progress_bar=None,
):
    """Warp raster into tiles and commit tiles to mbtiles database.
    """
    pool = Pool(
        num_workers, init_worker, (inputfile, base_kwds, resampling), 100 * BATCH_SIZE
    )

    def grouper(iterable, n, fillvalue=None):
        "Collect data into fixed-length chunks or blocks"
        # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
        args = [iter(iterable)] * n
        return zip_longest(*args, fillvalue=fillvalue)

    init_mbtiles()

    for group in grouper(pool.imap_unordered(process_tile, tiles), BATCH_SIZE):
        for group_n, item in enumerate(group, start=1):
            if item is None:
                break
            tile, contents = item
            insert_results(tile, contents, img_ext=img_ext, image_dump=image_dump)

        commit_mbtiles()

        if progress_bar is not None:
            if progress_bar.n + group_n < progress_bar.total:
                progress_bar.update(group_n)

    pool.close()
