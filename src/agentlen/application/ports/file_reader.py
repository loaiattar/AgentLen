from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.profile import FileProfile

#: What a reader yields for each record of the file, in file order: the record
#: as a JSON object, or the `rejected` issue standing in for a record that
#: could not be read. A rejection keeps its place, so one bad line never shifts
#: the numbering of the lines after it.
#:
#: A record's `line_number` is its rank among the file's records, from 1: a
#: blank JSONL line is not a record, the CSV header is not a record, a Parquet
#: row is one. It is the same number on the rejection, on `raw_record` and on
#: every issue of that record. The physical line, when it differs, is named in
#: the rejection's message.
#:
#: Values are JSON types only (str, int, float, bool, None, list, dict), so a
#: record can be hashed and stored as JSONB: see `PolarsRecordReader`.
SourceItem = dict[str, Any] | ImportIssue


class FileProfiler(Protocol):
    """Port for profiling source files.

    Implemented by Polars in infrastructure/files/.
    """

    async def profile(
        self, path: str, *, sample_size: int = 500, format: str | None = None
    ) -> FileProfile:
        """Profile the file at `path`.

        `format` should be passed whenever it is already known (it always is,
        once a file is stored: `file_upload.format`) — storage is
        content-addressed (`infrastructure/files/local_storage.py`), so the
        path itself carries no extension to infer a format from.
        """
        ...


class ProfileSanitizer(Protocol):
    """Sanitise every example before a profile reaches a provider."""

    def sanitize(self, profile: FileProfile) -> FileProfile: ...


class FileReader(Protocol):
    """Port for reading source records from a file."""

    def read_records(
        self, path: str, *, limit: int | None = None, format: str | None = None
    ) -> list[SourceItem]:
        """Read records, at most `limit` of them (a rejection counts as one).

        The limit is not a convenience: a preview looks at twenty rows, and
        reading a 500 MB file to show twenty rows would make the feature
        unusable on exactly the files that need it most.
        """
        ...

    def iter_batches(
        self, path: str, *, batch_size: int, format: str | None = None
    ) -> Iterator[list[SourceItem]]:
        """Yield records in batches, never holding the whole file.

        An import reads files of arbitrary size; loading one whole would make
        memory scale with the input, which is the failure mode that only shows
        up on the biggest and most important file someone tries.
        """
        ...
