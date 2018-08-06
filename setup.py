from codecs import open as codecs_open
from setuptools import setup, find_packages


# Parse the version from the mbtiles module.
with open('mbtiles/__init__.py') as f:
    for line in f:
        if line.find("__version__") >= 0:
            version = line.split("=")[1].strip()
            version = version.strip('"')
            version = version.strip("'")
            break

# Get the long description from the relevant file
with codecs_open('README.rst', encoding='utf-8') as f:
    long_description = f.read()


setup(name='rio-mbtiles',
      version=version,
      description=u"A Rasterio plugin command that exports MBTiles",
      long_description=long_description,
      classifiers=[],
      keywords='',
      author=u"Sean Gillies",
      author_email='sean@mapbox.com',
      url='https://github.com/mapbox/rio-mbtiles',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      python_requires='>=2.7.10',
      install_requires=[
          'click',
          'mercantile',
          'numpy>=1.10',
          'rasterio~=1.0'
      ],
      extras_require={
          'test': ['coveralls', 'pytest', 'pytest-cov'],
      },
      entry_points="""
      [rasterio.rio_plugins]
      mbtiles=mbtiles.scripts.cli:mbtiles
      """
      )
