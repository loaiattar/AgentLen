from pathlib import Path

import polars as pl
import pytest

from agentlen.infrastructure.files.polars_reader import (
    infer_format,
    read_csv,
    read_jsonl,
    read_parquet,
    scan_file,
)

SAMPLE_FILE = Path(__file__).parents[2] / "data" / "samples" / "tracelab_example_session.jsonl"
FLAT_FIXTURES = Path(__file__).parents[2] / "tests" / "fixtures" / "profiler"
SAMPLE_ROW_COUNT = 19
FLAT_FIXTURE_ROW_COUNT = 10


def test_read_jsonl_is_lazy():
    assert isinstance(read_jsonl(SAMPLE_FILE), pl.LazyFrame)


def test_read_jsonl_returns_expected_row_count():
    df = read_jsonl(SAMPLE_FILE).collect()
    assert df.height == SAMPLE_ROW_COUNT


def test_read_jsonl_has_expected_columns():
    df = read_jsonl(SAMPLE_FILE).collect()
    assert "session_id" in df.columns
    assert "provider" in df.columns


@pytest.mark.parametrize(
    "reader, filename",
    [
        (read_jsonl, "flat_sample.jsonl"),
        (read_csv, "flat_sample.csv"),
        (read_parquet, "flat_sample.parquet"),
    ],
)
def test_readers_are_lazy_and_read_the_same_row_count(reader, filename):
    lf = reader(FLAT_FIXTURES / filename)
    assert isinstance(lf, pl.LazyFrame)
    assert lf.select(pl.len()).collect().item() == FLAT_FIXTURE_ROW_COUNT


@pytest.mark.parametrize(
    "format_, filename",
    [
        ("jsonl", "flat_sample.jsonl"),
        ("csv", "flat_sample.csv"),
        ("parquet", "flat_sample.parquet"),
    ],
)
def test_scan_file_dispatches_by_format(format_, filename):
    lf = scan_file(FLAT_FIXTURES / filename, format=format_)
    assert lf.select(pl.len()).collect().item() == FLAT_FIXTURE_ROW_COUNT


def test_scan_file_rejects_unsupported_format():
    with pytest.raises(ValueError):
        scan_file(SAMPLE_FILE, format="xml")


@pytest.mark.parametrize(
    "path, expected",
    [
        ("data/x.jsonl", "jsonl"),
        ("data/x.ndjson", "jsonl"),
        ("data/x.csv", "csv"),
        ("data/x.parquet", "parquet"),
        ("data/x.pq", "parquet"),
    ],
)
def test_infer_format(path, expected):
    assert infer_format(path) == expected


def test_infer_format_rejects_unknown_suffix():
    with pytest.raises(ValueError):
        infer_format("data/x.xml")
