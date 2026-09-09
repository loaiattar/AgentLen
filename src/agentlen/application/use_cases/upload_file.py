"""Accept a file, store it once, and say whether we have seen it before.

The interesting behaviour is the second half. Uploading the same content twice
must not create a second `file_upload` row — `content_hash` is UNIQUE — so the
second upload returns the *existing* record with `already_seen: true` and the
runs that already used it.

That is not a nicety: it is what lets the front warn "you have already imported
this" instead of silently queueing a duplicate import (API.md §2).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from agentlen.application.ports.file_storage import FileStorage
from agentlen.application.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class UploadResult:
    """The body of `POST /files` (API.md §2)."""

    id: int
    original_name: str
    format: str
    size_bytes: int
    content_hash: str
    already_seen: bool
    previous_import_run_ids: list[int] = field(default_factory=list)


class UploadFile:
    def __init__(self, storage: FileStorage, uow: UnitOfWork) -> None:
        self._storage = storage
        self._uow = uow

    async def execute(self, chunks: AsyncIterator[bytes], *, original_name: str) -> UploadResult:
        # Storing first is deliberate: the hash is only known once the bytes
        # have been read, and it is the hash that decides whether a row is
        # needed. The storage layer is content-addressed, so re-storing
        # identical bytes is a no-op rather than a duplicate file on disk.
        stored = await self._storage.store(chunks, original_name=original_name)

        async with self._uow as uow:
            existing = await uow.file_uploads.get_by_hash(stored.content_hash)
            if existing is not None:
                runs = await uow.file_uploads.import_run_ids(existing.id)
                await uow.commit()
                return UploadResult(
                    id=existing.id,
                    original_name=existing.original_name,
                    format=existing.format,
                    size_bytes=existing.size_bytes,
                    content_hash=existing.content_hash,
                    already_seen=True,
                    previous_import_run_ids=runs,
                )

            record = await uow.file_uploads.create(
                original_name=original_name,
                storage_path=stored.storage_path,
                format=stored.detected_format,
                size_bytes=stored.size_bytes,
                content_hash=stored.content_hash,
            )
            await uow.commit()
            return UploadResult(
                id=record.id,
                original_name=record.original_name,
                format=record.format,
                size_bytes=record.size_bytes,
                content_hash=record.content_hash,
                already_seen=False,
            )
