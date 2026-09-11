"""Reading a file for an import: every record, as written, in a single pass."""

from __future__ import annotations

import builtins
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import polars as pl
import pytest

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.import_run import ImportIssue, ImportReport
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


@pytest.mark.parametrize(
    ("bad_line", "code"),
    [
        (b'{"prompt": "TRACE-4b1d"', "INVALID_JSON"),
        (b'{"a": NaN}', "INVALID_JSON"),
        (b'{"a": 1e400}', "INVALID_JSON"),
        (b'{"prompt": "TRACE-\xff"}', "INVALID_JSON"),
        (b'["TRACE-4b1d"]', "NOT_A_JSON_OBJECT"),
    ],
)
def test_a_line_that_is_not_a_json_object_is_rejected_at_its_rank(
    tmp_path: Path, bad_line: bytes, code: str
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b'{"a": 1}\n\n' + bad_line + b'\n{"a": 2}\n')

    first, rejected, last = _read_all(path)

    assert (first, last) == ({"a": 1}, {"a": 2})  # the read goes on
    assert isinstance(rejected, ImportIssue)
    assert (rejected.severity, rejected.code, rejected.line_number) == ("rejected", code, 2)
    # Record 2 sits on physical line 3, after the blank one: the message says so.
    assert rejected.message.startswith("Ligne 3 du fichier illisible")
    assert "TRACE" not in rejected.message


def test_csv_nan_and_infinities_are_read_as_null(tmp_path: Path) -> None:
    path = tmp_path / "nan.csv"
    path.write_text("sid,score\ns1,NaN\ns2,inf\ns3,-inf\ns4,1.5\n", encoding="utf-8")

    assert [r["score"] for r in _read_all(path)] == [None, None, None, 1.5]


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


SESSIONS = Mapping(
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


async def _import(path: Path, format_: str) -> tuple[ImportReport, InMemoryUnitOfWork, str]:
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="late", name="Late")
        mapping_id = await uow.mappings.save(SESSIONS, data_source_id=source)
        stored = await uow.file_uploads.create(
            original_name=path.name,
            storage_path=str(path),
            format=format_,
            size_bytes=path.stat().st_size,
            content_hash="b" * 64,
        )
        run_id = await uow.import_runs.create(
            data_source_id=source, file_upload_id=stored.id, mapping_id=mapping_id
        )
        await uow.commit()
    report = await RunImport(uow, PolarsRecordReader()).execute(run_id)
    async with uow:
        run = await uow.import_runs.get(run_id)
    assert run is not None
    return report, uow, run["status"]


async def test_run_import_stores_the_late_field_and_the_source_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = _late_field_rows()
    path = _write_jsonl(tmp_path / "import.jsonl", rows)
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "40")

    report, uow, _ = await _import(path, "jsonl")

    assert report.records_read == ROWS
    assert list(uow._store.payloads.values()) == rows
    agents = {s.external_id: s.agent_name for s, _ in uow._store.sessions.values()}
    assert agents[f"s{LATE_ROW - 1}"] is None
    assert agents[f"s{LATE_ROW}"] == f"agent-{LATE_ROW}"


async def test_parquet_dates_decimals_and_nan_are_read_as_json_and_imported(
    tmp_path: Path,
) -> None:
    """#189: a datetime or a Decimal made the record impossible to hash, and the
    whole run failed. Dates as ISO 8601, decimals as exact text, NaN as null."""
    path = tmp_path / "typed.parquet"
    pl.DataFrame(
        {
            "sid": ["s1"],
            "ts": [datetime(2024, 1, 2, 3, 4, 5, 123456)],  # noqa: DTZ001 - a naive column
            "day": [date(2024, 1, 2)],
            "at": [time(3, 4, 5)],
            "cost": pl.Series([Decimal("12345678901234.567890")], dtype=pl.Decimal(20, 6)),
            "took": [timedelta(minutes=1, microseconds=500_000)],
            "nested": [{"when": [date(2024, 1, 3)], "ratio": float("nan")}],
        }
    ).with_columns(utc=pl.col("ts").dt.replace_time_zone("UTC")).write_parquet(path)

    [record] = _read_all(path)
    report, uow, status = await _import(path, "parquet")

    assert record == {
        "sid": "s1",
        "ts": "2024-01-02T03:04:05.123456",
        "day": "2024-01-02",
        "at": "03:04:05",
        "cost": "12345678901234.567890",
        "took": "PT60.5S",
        "nested": {"when": ["2024-01-03"], "ratio": None},
        "utc": "2024-01-02T03:04:05.123456+00:00",
    }
    assert (status, report.records_imported) == ("succeeded", 1)
    assert list(uow._store.payloads.values()) == [record]


async def test_an_invalid_line_and_a_nul_character_are_rejected_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#189: one bad line used to fail the whole run. Each is now one rejection
    with its line number, across batches, and the run ends `partial`."""
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "2")
    path = tmp_path / "mixed.jsonl"
    lines = [
        '{"sid": "s1"}',
        "",
        '{"sid": "s2",',
        '{"sid": "s3", "prompt": "a\\u0000b"}',
        '{"sid": "s4"}',
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report, uow, status = await _import(path, "jsonl")

    rejected = [(i.code, i.line_number, i.field_path) for i in report.issues]
    assert rejected == [("INVALID_JSON", 2, None), ("UNSTORABLE_VALUE", 3, "$.prompt")]
    assert (report.records_read, report.records_rejected, status) == (4, 2, "partial")
    assert {s.external_id for s, _ in uow._store.sessions.values()} == {"s1", "s4"}
    # Both rejected lines are kept without payload, so their issues point at them.
    assert list(uow._store.payloads.values()) == [{"sid": "s1"}, None, None, {"sid": "s4"}]
