__version__ = "1.4.2"

import logging
import os
import sys
import time

logging.Formatter.converter = time.gmtime

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "[%(levelname)s]  %(asctime)s.%(msecs)03dZ  %(name)s:%(funcName)s:%(lineno)d  %(message)s"
LOG_FORMATTER = logging.Formatter(LOG_FORMAT, "%Y-%m-%dT%H:%M:%S")
handler = logging.StreamHandler(sys.stdout)
handler.formatter = LOG_FORMATTER
logger = logging.getLogger("rio-mbtiles")
logger.handlers = []
logger.addHandler(handler)
logger.setLevel(LOG_LEVEL)
logger.propagate = False
