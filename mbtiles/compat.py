import sys
import warnings

if sys.version_info < (3,):
    warnings.warn(
        "Support for Python versions < 3 will be dropped in rio-mbtiles version 2.0",
        FutureWarning,
        stacklevel=2,
    )
    from itertools import izip_longest as zip_longest
else:
    from itertools import zip_longest
