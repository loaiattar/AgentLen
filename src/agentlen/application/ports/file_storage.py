"""Port for putting an uploaded file somewhere durable.

The implementation decides *where* (local disk today, object storage later);
the application only ever learns what came back: a path it can hand to a
reader, the size, and the content hash.

That hash is the first of the three idempotence barriers (DATA_MODEL.md §6.1).
It is computed while the bytes stream past, not by re-reading the file
afterwards — a second pass on a 500 MB upload is both slow and a chance for the
two passes to disagree.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredFile:
    """What the storage layer knows after writing a file."""

    storage_path: str
    size_bytes: int
    content_hash: str
    detected_format: str


class FileStorageError(Exception):
    """Base for refusals that are the caller's fault, not the disk's."""

    code = "FILE_STORAGE_ERROR"


class UnsupportedFileFormatError(FileStorageError):
    code = "UNSUPPORTED_FILE_FORMAT"


class FileTooLargeError(FileStorageError):
    code = "FILE_TOO_LARGE"


class FileStorage(Protocol):
    async def store(self, chunks: AsyncIterator[bytes], *, original_name: str) -> StoredFile:
        """Consume the stream, write it, and describe what was written.

        Raises `UnsupportedFileFormatError` or `FileTooLargeError` before the
        whole stream has been consumed where possible — refusing a 2 GB upload
        should not require reading 2 GB first.
        """
        ...
