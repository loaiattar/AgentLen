"""Polars implementation of `FileReader`.

Built on the lazy scanners, so `limit` is pushed down into the scan: previewing
twenty rows of a 500 MB file reads twenty rows, not 500 MB.
"""

from __future__ import annotations

from collections.abc import Iterator
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

    def iter_batches(
        self, path: str, *, batch_size: int, format: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        """Slice the lazy scan, one window at a time.

        `slice` is pushed into the scan, so each step materialises `batch_size`
        rows rather than the file. Memory stays flat whether the file holds a
        thousand records or ten million.
        """
        resolved = format or infer_format(path)
        offset = 0
        while True:
            batch = scan_file(path, format=resolved).slice(offset, batch_size).collect()
            if batch.height == 0:
                return
            yield batch.to_dicts()
            if batch.height < batch_size:
                return
            offset += batch_size
