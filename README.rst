rio-mbtiles
===========

.. image:: https://travis-ci.org/mapbox/rio-mbtiles.svg
   :target: https://travis-ci.org/mapbox/rio-mbtiles

A plugin for the
`Rasterio CLI <https://github.com/mapbox/rasterio/blob/master/docs/cli.rst>`__
that exports a raster dataset to the MBTiles (version 1.3) format. Features
include automatic reprojection and concurrent tile generation.

Usage
-----

.. code-block:: console

    Usage: rio mbtiles [OPTIONS] INPUT [OUTPUT]

      Export a dataset to MBTiles (version 1.3) in a SQLite file.

      The input dataset may have any coordinate reference system. It must have
      at least three bands, which will be become the red, blue, and green bands
      of the output image tiles.

      An optional fourth alpha band may be copied to the output tiles by using
      the --rgba option in combination with the PNG or WEBP formats. This option
      requires that the input dataset has at least 4 bands.

      The default quality for JPEG and WEBP output (possible range: 10-100) is
      75. This value can be changed with the use of the QUALITY creation option,
      e.g. `--co QUALITY=90`.  The default zlib compression level for PNG output
      (possible range: 1-9) is 6. This value can be changed like `--co
      ZLEVEL=8`.  Lossless WEBP can be chosen with `--co LOSSLESS=TRUE`.

      If no zoom levels are specified, the defaults are the zoom levels nearest
      to the one at which one tile may contain the entire source dataset.

      If a title or description for the output file are not provided, they will
      be taken from the input dataset's filename.

      This command is suited for small to medium (~1 GB) sized sources.

      Python package: rio-mbtiles (https://github.com/mapbox/rio-mbtiles).

    Options:
      -o, --output PATH               Path to output file (optional alternative to
                                      a positional arg).

      --append / --overwrite          Append tiles to an existing file or
                                      overwrite.

      --title TEXT                    MBTiles dataset title.
      --description TEXT              MBTiles dataset description.
      --overlay                       Export as an overlay (the default).
      --baselayer                     Export as a base layer.
      -f, --format [JPEG|PNG|WEBP]    Tile image format.
      --tile-size INTEGER             Width and height of individual square tiles
                                      to create.  [default: 256]

      --zoom-levels MIN..MAX          A min...max range of export zoom levels. The
                                      default zoom level is the one at which the
                                      dataset is contained within a single tile.

      --image-dump PATH               A directory into which image tiles will be
                                      optionally dumped.

      -j INTEGER                      Number of workers (default: number of
                                      computer's processors).

      --src-nodata FLOAT              Manually override source nodata
      --dst-nodata FLOAT              Manually override destination nodata
      --resampling [nearest|bilinear|cubic|cubic_spline|lanczos|average|mode|gauss|max|min|med|q1|q3|rms]
                                      Resampling method to use.  [default:
                                      nearest]

      --version                       Show the version and exit.
      --rgba                          Select RGBA output. For PNG or WEBP only.
      --implementation [cf|mp]        Concurrency implementation. Use
                                      concurrent.futures (cf) or multiprocessing
                                      (mp).

      -#, --progress-bar              Display progress bar.
      --covers TEXT                   Restrict mbtiles output to cover a quadkey
      --cutline PATH                  Path to a GeoJSON FeatureCollection to be
                                      used as a cutline. Only source pixels within
                                      the cutline features will be exported.

      --oo NAME=VALUE                 Format driver-specific options to be used
                                      when accessing the input dataset. See the
                                      GDAL format driver documentation for more
                                      information.

      --co, --profile NAME=VALUE      Driver specific creation options. See the
                                      documentation for the selected output driver
                                      for more information.

      --wo NAME=VALUE                 See the GDAL warp options documentation for
                                      more information.

      --exclude-empty-tiles / --include-empty-tiles
                                      Whether to exclude or include empty tiles
                                      from the output.

      --help                          Show this message and exit.

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

``pip install rio-mbtiles``
