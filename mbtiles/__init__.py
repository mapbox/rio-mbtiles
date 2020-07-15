"""rio-mbtiles package"""

import sys
import warnings

if sys.version_info < (3, 6):
    warnings.warn(
        "Support for Python versions < 3.6 will be dropped in rio-mbtiles version 2.0",
        FutureWarning,
        stacklevel=2,
    )

__version__ = "1.5dev"
