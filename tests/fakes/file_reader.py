"""In-memory `FileReader`: records handed over directly, no file involved."""

from __future__ import annotations

from typing import Any


class InMemoryFileReader:
    def __init__(self, records_by_path: dict[str, list[dict[str, Any]]]) -> None:
        self._records = records_by_path
        self.last_limit: int | None = None

    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[dict[str, Any]]:
        # Recorded so a test can assert the limit is really pushed down rather
        # than the whole file being read and sliced afterwards.
        self.last_limit = limit
        records = self._records.get(path, [])
        return records[:limit] if limit is not None else records
