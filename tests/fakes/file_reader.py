"""In-memory `FileReader`: records handed over directly, no file involved."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class InMemoryFileReader:
    def __init__(self, records_by_path: dict[str, list[dict[str, Any]]]) -> None:
        self._records = records_by_path
        self.last_limit: int | None = None
        self.batch_sizes: list[int] = []

    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[dict[str, Any]]:
        # Recorded so a test can assert the limit is really pushed down rather
        # than the whole file being read and sliced afterwards.
        self.last_limit = limit
        records = self._records.get(path, [])
        return records[:limit] if limit is not None else records

    def iter_batches(
        self, path: str, *, batch_size: int, format: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        self.batch_sizes.append(batch_size)
        records = self._records.get(path, [])
        for start in range(0, len(records), batch_size):
            yield records[start : start + batch_size]
