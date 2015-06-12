#!/usr/bin/env bash

set -e

DATA_DIR="file://rasterio-0.24.0-$TRAVIS_PYTHON_VERSION-linux-x86_64/data"

INSTALL_ARGS=''
if [ -f "$DATA_DIR/requirements.txt" ]; then
  INSTALL_ARGS="$INSTALL_ARGS"\ -r\ "$DATA_DIR/requirements.txt"
fi

echo "Installing rasterio-0.24.0"
"$VIRTUAL_ENV/bin/pip" install --pre --no-index --find-links "$DATA_DIR" wheel $INSTALL_ARGS rasterio | grep -v '^$'
