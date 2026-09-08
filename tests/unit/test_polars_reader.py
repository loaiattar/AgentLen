from pathlib import Path

from agentlen.infrastructure.files.polars_reader import read_jsonl

SAMPLE_FILE = Path(__file__).parents[2] / "data" / "samples" / "tracelab_example_session.jsonl"


def test_read_jsonl_returns_expected_row_count():
    df = read_jsonl(SAMPLE_FILE)
    assert df.height == 19


def test_read_jsonl_has_expected_columns():
    df = read_jsonl(SAMPLE_FILE)
    assert "session_id" in df.columns
    assert "provider" in df.columns
