import logging
import os
import sqlite3
import sys

import pytest

from mbtiles.scripts.cli import mbtiles

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)


def test_cli_help(runner):
    result = runner.invoke(mbtiles, ['--help'])
    assert result.exit_code == 0
    assert "Export a dataset to MBTiles (version 1.1)" in result.output


def test_export_metadata(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(mbtiles, [inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == 'RGB.byte.tif'


def test_export_metadata_output_opt(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(mbtiles, [inputfile, '-o', outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == 'RGB.byte.tif'


def test_export_metadata_output_existing_output(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(mbtiles, [inputfile, outputfile])
    assert result.exit_code == 0
    assert os.path.exists(outputfile)

    result = runner.invoke(mbtiles, [inputfile, outputfile])
    assert result.exit_code == 1
    assert "file exists and won't be overwritten " in result.output


def test_export_metadata_output_force_overwrite(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(mbtiles, [inputfile, outputfile])
    assert result.exit_code == 0
    assert os.path.exists(outputfile)

    result = runner.invoke(mbtiles, [inputfile, outputfile,
                                     '--force-overwrite'])
    assert result.exit_code == 0
    assert os.path.exists(outputfile)


def test_export_tiles(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(mbtiles, [inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_zoom(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(
        mbtiles, [inputfile, outputfile, '--zoom-levels', '6..7'])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_jobs(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    result = runner.invoke(
        mbtiles, [inputfile, outputfile, '-j', '4'])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_dump(runner, data):
    inputfile = str(data.join('RGB.byte.tif'))
    outputfile = str(data.join('export.mbtiles'))
    dumpdir = pytest.ensuretemp('dump')
    result = runner.invoke(
        mbtiles, [inputfile, outputfile, '--image-dump', str(dumpdir)])
    assert result.exit_code == 0
    assert len(os.listdir(str(dumpdir))) == 6
