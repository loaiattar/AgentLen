from __future__ import annotations

from typing import Any, Protocol

from agentlen.domain.model.profile import FileProfile


class FileProfiler(Protocol):
    """Port for profiling source files.

    Implemented by Polars in infrastructure/files/.
    """

    async def profile(self, path: str, *, sample_size: int = 500) -> FileProfile: ...


class FileReader(Protocol):
    """Port for reading source records from a file."""

    def read_records(self, path: str) -> list[dict[str, Any]]: ...
