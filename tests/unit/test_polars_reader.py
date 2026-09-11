from pathlib import Path

import polars as pl
import pytest

from agentlen.infrastructure.files.polars_reader import (
    PREVIEW_INFER_SCHEMA_LENGTH,
    infer_format,
    read_csv,
    read_head,
    read_jsonl,
    read_parquet,
    scan_file,
)
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader

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


def _csv_with_a_string_at_row(path: Path, row: int, rows: int) -> Path:
    """Column `n` holds integers except on data row `row`, which holds text."""
    lines = ("oops,x" if i == row - 1 else f"{i},x" for i in range(rows))
    path.write_text("\n".join(["n,s", *lines]) + "\n", encoding="utf-8")
    return path


def test_a_csv_preview_does_not_read_the_whole_file(tmp_path: Path) -> None:
    """Row 50 001 turns `n` into text for whole-file inference. A one-record
    preview that still reads `n` as an integer never went that far."""
    path = _csv_with_a_string_at_row(tmp_path / "big.csv", row=50_001, rows=50_001)

    preview = PolarsRecordReader().read_records(str(path), limit=1, format="csv")

    assert preview == [{"n": 0, "s": "x"}]
    # The import keeps whole-file inference (#176): the late text widens `n`.
    batches = PolarsRecordReader().iter_batches(str(path), batch_size=10, format="csv")
    assert next(iter(batches))[0] == {"n": "0", "s": "x"}


def test_a_type_change_just_past_the_preview_window_falls_back_to_the_whole_file(
    tmp_path: Path,
) -> None:
    """Polars parses beyond the rows it returns, so a bounded window can meet a
    value it did not infer and fail. The preview must not fail where the
    import reads the file: it retries with whole-file inference."""
    row = PREVIEW_INFER_SCHEMA_LENGTH + 1
    path = _csv_with_a_string_at_row(tmp_path / "near.csv", row=row, rows=4 * row)

    assert read_head(path, "csv", 1).collect().to_dicts() == [{"n": "0", "s": "x"}]
