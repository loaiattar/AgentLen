"""Implements the `FileReader` port, reading each file once from start to end.

JSONL does not go through Polars at all: every line is decoded with `json`, so
a record is exactly the source object — key order, explicit nulls, fields that
appear only on line 10,000 — and `raw_record.payload` really is the record as
it was written (ADR-008). A Polars frame would force one schema on every line,
adding null keys to some records and dropping unknown keys from others.

CSV and Parquet stream through one Polars scan, with the schema inference
shared with the profiler (`polars_reader.INFER_SCHEMA_LENGTH`): what the
profile showed is what the import reads.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Iterator
from contextlib import closing
from itertools import batched, islice
from pathlib import Path
from typing import Any, NoReturn

from agentlen.infrastructure.files.polars_reader import infer_format, read_head, scan_file


class PolarsRecordReader:
    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[dict[str, Any]]:
        # Stops after `limit` records: the rest of the file is never read.
        with closing(_records(path, format or infer_format(path), limit=limit)) as records:
            return list(islice(records, limit))

    def iter_batches(
        self, path: str, *, batch_size: int, format: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        """One pass over the file, `batch_size` records at a time.

        Nothing is re-read between batches — JSONL and CSV cannot seek to a
        record, so rebuilding a scan per batch re-parsed everything before it.
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size!r}.")
        resolved = format or infer_format(path)
        with closing(_records(path, resolved, chunk_size=batch_size)) as records:
            for batch in batched(records, batch_size):
                yield list(batch)


def _records(
    path: str, format_: str, *, limit: int | None = None, chunk_size: int | None = None
) -> Generator[dict[str, Any], None, None]:
    # A zero-byte file holds no records in any format; Polars would raise on
    # it instead (same short-circuit as the profiler).
    if Path(path).stat().st_size == 0:
        return
    if format_ == "jsonl":
        yield from _jsonl_records(path)
        return
    lazy = scan_file(path, format=format_) if limit is None else read_head(path, format_, limit)
    if limit is not None:
        lazy = lazy.head(limit)
    for frame in lazy.collect_batches(chunk_size=chunk_size):
        yield from frame.iter_rows(named=True)


def _jsonl_records(path: str) -> Iterator[dict[str, Any]]:
    """Decode one JSON object per non-blank line.

    Blank lines are skipped without counting as records, as Polars did, so
    the record numbering the importer derives from batch sizes is unchanged.
    Errors name the physical line, which is what someone opening the file sees.
    """
    # Binary mode: `json.loads` detects the encoding itself and accepts a
    # UTF-8 byte order mark on the first line.
    with open(path, "rb") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line, parse_constant=_reject_constant)
            except ValueError as exc:
                raise ValueError(f"Line {line_number} is not valid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(
                    f"Line {line_number} is a JSON {type(record).__name__}, not an object."
                )
            yield record


def _reject_constant(name: str) -> NoReturn:
    # NaN and Infinity are not JSON, and a JSONB column refuses them.
    raise ValueError(f"{name} is not a valid JSON value")
