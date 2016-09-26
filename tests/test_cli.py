import logging
import os
import sqlite3
import sys

from click.testing import CliRunner
import pytest
import rasterio
from rasterio.rio.main import main_group

from mbtiles.scripts.cli import mbtiles


logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main_group, ['mbtiles', '--help'])
    assert result.exit_code == 0
    assert "Export a dataset to MBTiles (version 1.1)" in result.output


def test_export_metadata(tmpdir, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(tmpdir.join('export.mbtiles'))
    runner = CliRunner()
    result = runner.invoke(main_group, ['mbtiles', inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == 'RGB.byte.tif'


def test_export_metadata_output_opt(tmpdir, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(tmpdir.join('export.mbtiles'))
    runner = CliRunner()
    result = runner.invoke(main_group, ['mbtiles', inputfile, '-o', outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == 'RGB.byte.tif'


def test_export_tiles(tmpdir, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(tmpdir.join('export.mbtiles'))
    runner = CliRunner()
    result = runner.invoke(main_group, ['mbtiles', inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_zoom(tmpdir, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(tmpdir.join('export.mbtiles'))
    runner = CliRunner()
    result = runner.invoke(
        main_group,
        ['mbtiles', inputfile, outputfile, '--zoom-levels', '6..7'])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_jobs(tmpdir, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(tmpdir.join('export.mbtiles'))
    runner = CliRunner()
    result = runner.invoke(
        main_group, ['mbtiles', inputfile, outputfile, '-j', '4'])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_dump(tmpdir, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(tmpdir.join('export.mbtiles'))
    dumpdir = pytest.ensuretemp('dump')
    runner = CliRunner()
    result = runner.invoke(
        main_group,
        ['mbtiles', inputfile, outputfile, '--image-dump', str(dumpdir)])
    assert result.exit_code == 0
    assert len(os.listdir(str(dumpdir))) == 6
