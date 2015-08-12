#!/usr/bin/env bash
#
# Conditionally download a wheel set satisfying Rasterio's dependencies to
# speed up builds.
#
# If we find the right rasterio wheel in the wheelhouse directory, we skip
# the download. Else, we download and extract into the wheelhouse dir.

set -e

WHEELHOUSE=$HOME/wheelhouse

if test -z $(find $WHEELHOUSE -name rasterio-$RASTERIO_VERSION-*-none-linux_x86_64.whl); then
    echo "Downloading speedy wheels..."
    curl -L https://github.com/mapbox/rasterio/releases/download/$RASTERIO_VERSION/rasterio-travis-wheels-$TRAVIS_PYTHON_VERSION.tar.gz > /tmp/wheelhouse.tar.gz
    echo "Extracting speedy wheels..."
    tar -xzvf /tmp/wheelhouse.tar.gz -C $HOME
else
    echo "Using existing wheelhouse."
fi
