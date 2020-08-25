import os
import sqlite3
import sys
import warnings

import click
from click.testing import CliRunner
import pytest
import rasterio
from rasterio.rio.main import main_group

import mbtiles.scripts.cli

from conftest import mock


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", "--help"])
    assert result.exit_code == 0
    assert "Export a dataset to MBTiles (version 1.1)" in result.output


@mock.patch("mbtiles.scripts.cli.rasterio")
def test_dst_nodata_validation(rio):
    """--dst-nodata requires source nodata in some form"""
    rio.open.return_value.__enter__.return_value.profile.get.return_value = None
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", "--dst-nodata", "0", "in.tif", "out.mbtiles"])
    assert result.exit_code == 2


@pytest.mark.parametrize("filename", ["RGB.byte.tif", "RGBA.byte.tif"])
def test_export_metadata(tmpdir, data, filename):
    inputfile = str(data.join(filename))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == filename


def test_export_overwrite(tmpdir, data):
    """Overwrites existing file"""
    inputfile = str(data.join("RGB.byte.tif"))
    output = tmpdir.join("export.mbtiles")
    output.write("lolwut")
    outputfile = str(output)
    runner = CliRunner()
    result = runner.invoke(
        main_group, ["mbtiles", "--overwrite", inputfile, outputfile]
    )
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == "RGB.byte.tif"


def test_export_metadata_output_opt(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", inputfile, "-o", outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == "RGB.byte.tif"


def test_export_tiles(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_zoom(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group, ["mbtiles", inputfile, outputfile, "--zoom-levels", "6..7"]
    )
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_jobs(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", inputfile, outputfile, "-j", "4"])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_src_nodata(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group,
        ["mbtiles", inputfile, outputfile, "--src-nodata", "0", "--dst-nodata", "0"],
    )
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_export_dump(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    dumpdir = tmpdir.ensure("dump", dir=True)
    runner = CliRunner()
    result = runner.invoke(
        main_group, ["mbtiles", inputfile, outputfile, "--image-dump", str(dumpdir)]
    )
    assert result.exit_code == 0
    assert len(os.listdir(str(dumpdir))) == 6


@pytest.mark.parametrize("tile_size", [256, 512])
def test_export_tile_size(tmpdir, data, tile_size):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    dumpdir = tmpdir.ensure("dump", dir=True)
    runner = CliRunner()
    result = runner.invoke(
        main_group,
        [
            "mbtiles",
            inputfile,
            outputfile,
            "--image-dump",
            str(dumpdir),
            "--tile-size",
            tile_size,
        ],
    )
    dump_files = os.listdir(str(dumpdir))
    assert result.exit_code == 0
    warnings.simplefilter("ignore")
    with rasterio.open(os.path.join(str(dumpdir), dump_files[0]), "r") as src:
        assert src.shape == (tile_size, tile_size)
    warnings.resetwarnings()


def test_export_bilinear(tmpdir, data):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group, ["mbtiles", inputfile, outputfile, "--resampling", "bilinear"]
    )
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 6


def test_skip_empty(tmpdir, empty_data):
    """This file has the same shape as RGB.byte.tif, but no data."""
    inputfile = empty_data
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(main_group, ["mbtiles", inputfile, outputfile])
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    assert len(cur.fetchall()) == 0


def test_invalid_format_rgba(tmpdir, empty_data):
    """--format JPEG --rgba is not allowed"""
    inputfile = empty_data
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group, ["mbtiles", "--format", "JPEG", "--rgba", inputfile, outputfile]
    )
    assert result.exit_code == 2


@pytest.mark.parametrize("filename", ["RGBA.byte.tif"])
def test_rgba_png(tmpdir, data, filename):
    inputfile = str(data.join(filename))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group, ["mbtiles", "--rgba", "--format", "PNG", inputfile, outputfile]
    )
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from metadata where name == 'name'")
    assert cur.fetchone()[1] == filename


@pytest.mark.parametrize(
    "minzoom,maxzoom,exp_num_tiles", [(4, 10, 70), (6, 7, 6)],
)
@pytest.mark.parametrize(
    "impl",
    [
        pytest.param(
            "cf",
            marks=pytest.mark.skipif(
                sys.version_info < (3, 7),
                reason="c.f. implementation requires Python 3.7",
            ),
        ),
        "mp",
    ],
)
def test_export_count(tmpdir, data, minzoom, maxzoom, exp_num_tiles, impl):
    inputfile = str(data.join("RGB.byte.tif"))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group,
        [
            "mbtiles",
            "--implementation",
            impl,
            "--zoom-levels",
            "{}..{}".format(minzoom, maxzoom),
            inputfile,
            outputfile,
        ],
    )
    assert result.exit_code == 0
    conn = sqlite3.connect(outputfile)
    cur = conn.cursor()
    cur.execute("select * from tiles")
    results = cur.fetchall()
    assert len(results) == exp_num_tiles


@pytest.mark.parametrize("filename", ["RGBA.byte.tif"])
@pytest.mark.parametrize(
    "impl",
    [
        pytest.param(
            "cf",
            marks=pytest.mark.skipif(
                sys.version_info < (3, 7),
                reason="c.f. implementation requires Python 3.7",
            ),
        ),
        "mp",
    ],
)
def test_progress_bar(tmpdir, data, impl, filename):
    inputfile = str(data.join(filename))
    outputfile = str(tmpdir.join("export.mbtiles"))
    runner = CliRunner()
    result = runner.invoke(
        main_group,
        [
            "mbtiles",
            "-#",
            "--implementation",
            impl,
            "--zoom-levels",
            "4..11",
            "--rgba",
            "--format",
            "PNG",
            inputfile,
            outputfile,
        ],
    )
    assert result.exit_code == 0
    assert "100%" in result.output
