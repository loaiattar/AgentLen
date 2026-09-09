"""Polars implementation of `FileReader`.

Built on the lazy scanners, so `limit` is pushed down into the scan: previewing
twenty rows of a 500 MB file reads twenty rows, not 500 MB.
"""

from __future__ import annotations

from typing import Any

from agentlen.infrastructure.files.polars_reader import infer_format, scan_file


class PolarsRecordReader:
    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[dict[str, Any]]:
        frame = scan_file(path, format=format or infer_format(path))
        if limit is not None:
            frame = frame.head(limit)
        records: list[dict[str, Any]] = frame.collect().to_dicts()
        return records
