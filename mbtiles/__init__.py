"""rio-mbtiles package"""

import sys
import warnings

__version__ = "1.5b1"

if sys.version_info < (3, 7):
    warnings.warn(
        "Support for Python versions < 3.7 will be dropped in rio-mbtiles version 2.0",
        FutureWarning,
        stacklevel=2,
    )
