rio-mbtiles
===========

.. image:: https://travis-ci.org/mapbox/rio-mbtiles.svg
   :target: https://travis-ci.org/mapbox/rio-mbtiles

A plugin command for the Rasterio CLI that exports a raster dataset to the
MBTiles (version 1.1) format. Features include automatic reprojection and
parallel processing.

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

    Options:
      -o, --output PATH       Path to output file (optional alternative to a
                              positional arg for some commands).
      --title TEXT            MBTiles dataset title.
      --description TEXT      MBTiles dataset description.
      --overlay               Export as an overlay (the default).
      --baselayer             Export as a base layer.
      --format [JPEG|PNG]     Tile image format.
      --zoom-levels MIN..MAX  A min...max range of export zoom levels. The default
                              zoom level is the one at which the dataset is
                              contained within a single tile.
      --image-dump PATH       A directory into which image tiles will be
                              optionally dumped.
      -j INTEGER              Number of worker processes (default: 1).
      --help                  Show this message and exit.
