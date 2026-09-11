"""Reading a file for an import: every record, as written, in a single pass."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl
import pytest

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.files import polars_record_reader
from agentlen.infrastructure.files.polars_profiler import PolarsFileProfiler
from agentlen.infrastructure.files.polars_reader import scan_file
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from tests.fakes.repositories import InMemoryUnitOfWork

ROWS = 150
LATE_ROW = 120  # past Polars' default 100-row inference window


def _late_field_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(ROWS):
        row: dict[str, Any] = {"sid": f"s{i}", "n": i}
        if i >= LATE_ROW:
            row["agent"] = f"agent-{i}"
        rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _read_all(path: Path, *, batch_size: int = 40, format: str | None = None) -> list[Any]:
    reader = PolarsRecordReader()
    return [
        r for b in reader.iter_batches(str(path), batch_size=batch_size, format=format) for r in b
    ]


async def test_jsonl_field_present_only_after_row_100_is_read_and_profiled(tmp_path: Path) -> None:
    rows = _late_field_rows()
    path = _write_jsonl(tmp_path / "late.jsonl", rows)

    # Records equal to the source: the late field is there, and no null
    # "agent" key was added to the records that never had one.
    assert _read_all(path) == rows

    profile = await PolarsFileProfiler().profile(str(path), sample_size=10)
    assert "$.agent" in {f.path for f in profile.fields}


async def test_csv_field_present_only_after_row_100_is_read_as_profiled(tmp_path: Path) -> None:
    path = tmp_path / "late.csv"
    empty = (f"{i}," for i in range(LATE_ROW))
    filled = (f"{i},{i}" for i in range(LATE_ROW, ROWS))
    path.write_text("\n".join(["id,tokens", *empty, *filled]) + "\n", encoding="utf-8")

    records = _read_all(path)
    profile = await PolarsFileProfiler().profile(str(path))

    assert len(records) == ROWS
    assert records[LATE_ROW - 1]["tokens"] is None
    # An integer, as the profile says — a 100-row window reads the string "120".
    assert records[LATE_ROW]["tokens"] == LATE_ROW
    assert next(f for f in profile.fields if f.path == "$.tokens").types == ("integer", "null")


async def test_csv_late_type_change_is_read_as_the_profile_shows_it(tmp_path: Path) -> None:
    path = tmp_path / "late_type.csv"
    lines = ["id,score", *(f"{i},{i}" for i in range(ROWS)), f"{ROWS},1.5"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    records = _read_all(path)  # used to raise ComputeError past row 100
    profile = await PolarsFileProfiler().profile(str(path))

    assert records[-1]["score"] == 1.5
    assert {type(r["score"]) for r in records} == {float}
    assert next(f for f in profile.fields if f.path == "$.score").types == ("float",)


def test_jsonl_payload_is_the_source_object_verbatim(tmp_path: Path) -> None:
    lines = [
        '{"z": 1, "a": null, "nested": {"y": [1, {"x": null}], "b": "é"}}',
        '{"a": 2, "big": 123456789012345678901234567890, "f": 1.0, "extra": true}',
        '{"only": "this"}',
    ]
    path = tmp_path / "verbatim.jsonl"
    path.write_text("\n".join(lines), encoding="utf-8")  # no trailing newline

    records = _read_all(path, batch_size=2)

    assert [json.dumps(r, ensure_ascii=False) for r in records] == lines  # key order included
    assert records[2] == {"only": "this"}


def test_blank_lines_are_skipped_and_do_not_count_as_records(tmp_path: Path) -> None:
    path = tmp_path / "blank.jsonl"
    path.write_text('{"a": 1}\n\n   \n{"a": 2}\r\n{"a": 3}\n\n', encoding="utf-8")

    batches = list(PolarsRecordReader().iter_batches(str(path), batch_size=2))

    assert batches == [[{"a": 1}, {"a": 2}], [{"a": 3}]]


@pytest.mark.parametrize("bad_line", ['{"a": 1', "[1, 2]", '{"a": NaN}'])
def test_a_line_that_is_not_a_json_object_fails_with_its_line_number(
    tmp_path: Path, bad_line: str
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(f'{{"a": 1}}\n\n{bad_line}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Line 3"):
        _read_all(path)


def test_jsonl_is_opened_once_for_all_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_jsonl(tmp_path / "once.jsonl", _late_field_rows())
    opened: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> Any:
        opened.append(args[0])
        return builtins.open(*args, **kwargs)

    monkeypatch.setattr(polars_record_reader, "open", spy, raising=False)

    batches = list(PolarsRecordReader().iter_batches(str(path), batch_size=10))

    assert len(batches) == ROWS // 10
    assert opened == [str(path)]


@pytest.mark.parametrize("format_", ["csv", "parquet"])
def test_csv_and_parquet_are_scanned_once_for_all_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, format_: str
) -> None:
    frame = pl.DataFrame({"id": list(range(ROWS)), "name": [f"n{i}" for i in range(ROWS)]})
    path = tmp_path / f"once.{format_}"
    if format_ == "csv":
        frame.write_csv(path)
    else:
        frame.write_parquet(path, row_group_size=32)
    scans: list[Any] = []

    def spy(*args: Any, **kwargs: Any) -> pl.LazyFrame:
        scans.append(args[0])
        return scan_file(*args, **kwargs)

    monkeypatch.setattr(polars_record_reader, "scan_file", spy)

    batches = list(PolarsRecordReader().iter_batches(str(path), batch_size=40))

    assert [len(b) for b in batches] == [40, 40, 40, 30]
    assert [r for b in batches for r in b] == frame.to_dicts()
    assert scans == [str(path)]


@pytest.mark.parametrize("format_", ["jsonl", "csv"])
def test_read_records_stops_at_the_limit(tmp_path: Path, format_: str) -> None:
    rows = _late_field_rows()
    path = tmp_path / f"limit.{format_}"
    if format_ == "jsonl":
        _write_jsonl(path, rows)
        with path.open("a", encoding="utf-8") as f:
            f.write("not json\n")  # never reached: the preview reads 5 records
    else:
        pl.DataFrame(rows).write_csv(path)

    records = PolarsRecordReader().read_records(str(path), limit=5)

    assert [r["sid"] for r in records] == [f"s{i}" for i in range(5)]


@pytest.mark.parametrize("format_", ["jsonl", "csv"])
def test_an_empty_file_yields_no_batch(tmp_path: Path, format_: str) -> None:
    path = tmp_path / f"empty.{format_}"
    path.touch()

    assert list(PolarsRecordReader().iter_batches(str(path), batch_size=10)) == []


async def test_run_import_stores_the_late_field_and_the_source_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = _late_field_rows()
    path = _write_jsonl(tmp_path / "import.jsonl", rows)
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "40")
    mapping = Mapping(
        id=uuid4(),
        name="late",
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(
                    FieldRule(target="external_id", source="$.sid", required=True),
                    FieldRule(target="agent_name", source="$.agent"),
                ),
            ),
        ),
    )
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="late", name="Late")
        mapping_id = await uow.mappings.save(mapping, data_source_id=source)
        stored = await uow.file_uploads.create(
            original_name="import.jsonl",
            storage_path=str(path),
            format="jsonl",
            size_bytes=path.stat().st_size,
            content_hash="b" * 64,
        )
        run_id = await uow.import_runs.create(
            data_source_id=source, file_upload_id=stored.id, mapping_id=mapping_id
        )
        await uow.commit()

    report = await RunImport(uow, PolarsRecordReader()).execute(run_id)

    assert report.records_read == ROWS
    assert list(uow._store.payloads.values()) == rows
    agents = {s.external_id: s.agent_name for s, _ in uow._store.sessions.values()}
    assert agents[f"s{LATE_ROW - 1}"] is None
    assert agents[f"s{LATE_ROW}"] == f"agent-{LATE_ROW}"
