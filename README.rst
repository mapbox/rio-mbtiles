rio-mbtiles
===========

.. image:: https://travis-ci.org/mapbox/rio-mbtiles.svg
   :target: https://travis-ci.org/mapbox/rio-mbtiles

A plugin for the
`Rasterio CLI <https://github.com/mapbox/rasterio/blob/master/docs/cli.rst>`__
that exports a raster dataset to the MBTiles (version 1.1) format. Features
include automatic reprojection and parallel processing.

Usage
-----

.. code-block:: console

    $ rio mbtiles --help
    Usage: rio mbtiles [OPTIONS] INPUT [OUTPUT]

      Export a dataset to MBTiles (version 1.1) in a SQLite file.

      The input dataset may have any coordinate reference system. It must have
      at least three bands, which will be become the red, blue, and green bands
      of the output image tiles.

      If no zoom levels are specified, the defaults are the zoom levels nearest
      to the one at which one tile may contain the entire source dataset.

      If a title or description for the output file are not provided, they will
      be taken from the input dataset's filename.
      
      This command is suited for small to medium (~1 GB) sized sources.
      
      Python package: rio-mbtiles (https://github.com/mapbox/rio-mbtiles).

    Options:
      -o, --output PATH       Path to output file (optional alternative to a
                              positional arg).
      --force-overwrite       Always overwrite an existing output file.
      --title TEXT            MBTiles dataset title.
      --description TEXT      MBTiles dataset description.
      --overlay               Export as an overlay (the default).
      --baselayer             Export as a base layer.
      --format [JPEG|PNG]     Tile image format. PNG format required for nodata
                              values to display as transparent.
      --zoom-levels MIN..MAX  A min..max range of export zoom levels. The default
                              zoom level is the one at which the dataset is
                              contained within a single tile.
      --image-dump PATH       A directory into which image tiles will be
                              optionally dumped.
      -j INTEGER              Number of worker processes (default: 3).
      --src-nodata FLOAT      Manually override source nodata
      --dst-nodata FLOAT      Manually override destination nodata
      --resampling            Resampling method to use. Options within
                              rasterio.enums.Resampling are supported.
                              (default: nearest)
      --version               Show the version and exit.
      --help                  Show this message and exit.

Performance
-----------

The rio-mbtiles command is suited for small to medium (~1 GB) raster sources.
On a MacBook Air, the 1:10M scale Natural Earth raster 
(a 21,600 x 10,800 pixel, 700 MB TIFF) exports to MBTiles (levels 1 through 5)
in 45 seconds.

.. code-block:: console

    $ time GDAL_CACHEMAX=256 rio mbtiles NE1_HR_LC.tif \
    > -o ne.mbtiles --zoom-levels 1..5 -j 4
    
    real    0m44.925s
    user    1m20.152s
    sys     0m22.428s

Installation
------------

If you've already 
`installed Rasterio <https://github.com/mapbox/rasterio#installation>`__,
installation is just ``pip install rio-mbtiles``.
