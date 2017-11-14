"""rio-mbtiles package"""

import sys


buffer = bytes if sys.version_info > (3,) else buffer

__version__ = '1.4.0'
