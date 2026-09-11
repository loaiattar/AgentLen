"""Implements the `FileReader` port, reading each file once from start to end.

JSONL does not go through Polars at all: every line is decoded with `json`, so
a record is exactly the source object — key order, explicit nulls, fields that
appear only on line 10,000 — and `raw_record.payload` really is the record as
it was written (ADR-008). A Polars frame would force one schema on every line,
adding null keys to some records and dropping unknown keys from others.

CSV and Parquet stream through one Polars scan, with the schema inference
shared with the profiler (`polars_reader.INFER_SCHEMA_LENGTH`): what the
profile showed is what the import reads. Their cells leave as JSON values, so a
record can be hashed and kept as JSONB (`_json_value`).

A JSONL line that is not a JSON object does not stop the read: it becomes a
`rejected` issue at its rank (`SourceItem`), and the next lines are read.
"""

from __future__ import annotations

import json
import math
from collections.abc import Generator, Iterator
from contextlib import closing
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import batched, islice
from pathlib import Path
from typing import Any, NoReturn

from agentlen.application.ports.file_reader import SourceItem
from agentlen.domain.model.import_run import ImportIssue
from agentlen.infrastructure.files.polars_reader import infer_format, scan_file


class PolarsRecordReader:
    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[SourceItem]:
        # Stops after `limit` records: the rest of the file is never read.
        with closing(_records(path, format or infer_format(path), limit=limit)) as records:
            return list(islice(records, limit))

    def iter_batches(
        self, path: str, *, batch_size: int, format: str | None = None
    ) -> Iterator[list[SourceItem]]:
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
) -> Generator[SourceItem, None, None]:
    # A zero-byte file holds no records in any format; Polars would raise on
    # it instead (same short-circuit as the profiler).
    if Path(path).stat().st_size == 0:
        return
    if format_ == "jsonl":
        yield from _jsonl_records(path)
        return
    lazy = scan_file(path, format=format_)
    if limit is not None:
        lazy = lazy.head(limit)
    for frame in lazy.collect_batches(chunk_size=chunk_size):
        for row in frame.iter_rows(named=True):
            yield {key: _json_value(value) for key, value in row.items()}


def _json_value(value: Any) -> Any:  # noqa: PLR0911
    """A Polars cell as a JSON value.

    Dates and times become ISO 8601 text (`2024-01-02T03:04:05+01:00`), and so
    does a duration (`PT90.5S`). A decimal becomes its exact text (`"12.340"`),
    since a float would round it. NaN and infinities, which JSON cannot hold,
    become null. Any other type (bytes) is left as is: the import rejects that
    record with `UNSTORABLE_VALUE` rather than guess an encoding.
    """
    if value is None or isinstance(value, str | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, timedelta):
        micros = (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds
        seconds, fraction = divmod(abs(micros), 1_000_000)
        text = f"PT{seconds}.{fraction:06d}".rstrip("0").rstrip(".")
        return f"{'-' if micros < 0 else ''}{text}S"
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _jsonl_records(path: str) -> Iterator[SourceItem]:
    """Decode one JSON object per non-blank line.

    Blank lines are skipped without counting as records, as Polars did, so
    the record numbering the importer derives from batch sizes is unchanged.
    A line that is not a JSON object still counts: its rejection takes its
    rank and names the physical line, which is what someone opening the file
    sees. Neither the rank nor the message quotes the line's content.
    """
    rank = 0
    # Binary mode: `json.loads` detects the encoding itself and accepts a
    # UTF-8 byte order mark on the first line.
    with open(path, "rb") as source:
        for physical_line, line in enumerate(source, start=1):
            if not line.strip():
                continue
            rank += 1
            code = "INVALID_JSON"
            try:
                record = json.loads(line, parse_constant=_reject_constant, parse_float=_finite)
            except json.JSONDecodeError as exc:
                reason = f"JSON invalide ({exc.msg}, colonne {exc.colno})"
            except _NotJsonError as exc:
                reason = str(exc)
            except (ValueError, RecursionError):
                reason = "JSON illisible (encodage, nombre trop long ou imbrication trop profonde)"
            else:
                if isinstance(record, dict):
                    yield record
                    continue
                code, reason = "NOT_A_JSON_OBJECT", "valeur JSON qui n'est pas un objet"
            yield ImportIssue(
                severity="rejected",
                code=code,
                message=f"Ligne {physical_line} du fichier illisible : {reason}.",
                line_number=rank,
            )


class _NotJsonError(ValueError):
    """Raised by the decoding hooks, with a message that quotes no content."""


def _reject_constant(name: str) -> NoReturn:
    # NaN and Infinity are not JSON, and a JSONB column refuses them.
    raise _NotJsonError(f"{name} n'est pas une valeur JSON")


def _finite(text: str) -> float:
    # `1e400` is valid JSON, but Python reads it as infinity, which JSONB refuses.
    value = float(text)
    if not math.isfinite(value):
        raise _NotJsonError("nombre hors des limites d'un flottant")
    return value
