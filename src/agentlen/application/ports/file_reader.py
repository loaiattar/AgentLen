from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from agentlen.domain.model.profile import FileProfile


class FileProfiler(Protocol):
    """Port for profiling source files.

    Implemented by Polars in infrastructure/files/.
    """

    async def profile(self, path: str, *, sample_size: int = 500) -> FileProfile: ...


class FileReader(Protocol):
    """Port for reading source records from a file."""

    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[dict[str, Any]]:
        """Read records, at most `limit` of them.

        The limit is not a convenience: a preview looks at twenty rows, and
        reading a 500 MB file to show twenty rows would make the feature
        unusable on exactly the files that need it most.
        """
        ...

    def iter_batches(
        self, path: str, *, batch_size: int, format: str | None = None
    ) -> Iterator[list[dict[str, Any]]]:
        """Yield records in batches, never holding the whole file.

        An import reads files of arbitrary size; loading one whole would make
        memory scale with the input, which is the failure mode that only shows
        up on the biggest and most important file someone tries.
        """
        ...
