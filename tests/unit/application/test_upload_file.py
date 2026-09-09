"""Uploading a file, and recognising one we already have.

No disk, no database: `InMemoryFileStorage` plus `InMemoryUnitOfWork`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from agentlen.application.ports.file_storage import (
    FileTooLargeError,
    UnsupportedFileFormatError,
)
from agentlen.application.use_cases.upload_file import UploadFile
from tests.fakes.file_storage import InMemoryFileStorage
from tests.fakes.repositories import InMemoryUnitOfWork

JSONL = b'{"session_id": "a3f2", "agent": "claude-code"}\n{"session_id": "b91c"}\n'
CSV = b"id,name,score\n1,alpha,3.5\n2,beta,19.0\n"


async def stream(payload: bytes, *, chunk: int = 16) -> AsyncIterator[bytes]:
    """Deliberately chunked: the real storage never sees the whole file at once."""
    for start in range(0, len(payload), chunk):
        yield payload[start : start + chunk]


def build() -> tuple[UploadFile, InMemoryFileStorage, InMemoryUnitOfWork]:
    storage, uow = InMemoryFileStorage(), InMemoryUnitOfWork()
    return UploadFile(storage, uow), storage, uow


async def test_a_new_file_is_stored_and_described() -> None:
    upload, _, _ = build()

    result = await upload.execute(stream(JSONL), original_name="traces.jsonl")

    assert result.already_seen is False
    assert result.format == "jsonl"
    assert result.size_bytes == len(JSONL)
    assert len(result.content_hash) == 64
    assert result.previous_import_run_ids == []


async def test_the_same_content_under_another_name_is_recognised() -> None:
    """The hash decides, not the filename — this is the first idempotence
    barrier, and it is what lets the front warn before a duplicate import."""
    upload, _, _ = build()

    first = await upload.execute(stream(JSONL), original_name="traces.jsonl")
    second = await upload.execute(stream(JSONL), original_name="copie-du-2-septembre.jsonl")

    assert second.already_seen is True
    assert second.id == first.id
    assert second.content_hash == first.content_hash
    # The stored name stays the one from the first upload: it is the same file.
    assert second.original_name == "traces.jsonl"


async def test_different_content_is_a_different_file() -> None:
    upload, _, _ = build()

    first = await upload.execute(stream(JSONL), original_name="a.jsonl")
    second = await upload.execute(stream(CSV), original_name="b.csv")

    assert second.already_seen is False
    assert second.id != first.id
    assert second.format == "csv"


async def test_a_known_file_reports_the_runs_that_used_it(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    upload, _, uow = build()
    first = await upload.execute(stream(JSONL), original_name="traces.jsonl")

    async with uow:
        source = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        run_id = await uow.import_runs.create(
            data_source_id=source, file_upload_id=first.id, mapping_id=1
        )
        await uow.commit()

    again = await upload.execute(stream(JSONL), original_name="traces.jsonl")

    assert again.already_seen is True
    assert again.previous_import_run_ids == [run_id]


@pytest.mark.parametrize("name", ["malware.exe", "notes.txt", "archive.zip", "sansextension"])
async def test_unsupported_extensions_are_refused(name: str) -> None:
    upload, _, _ = build()

    with pytest.raises(UnsupportedFileFormatError) as exc:
        await upload.execute(stream(JSONL), original_name=name)
    assert exc.value.code == "UNSUPPORTED_FILE_FORMAT"


async def test_a_file_over_the_limit_is_refused() -> None:
    storage = InMemoryFileStorage(max_bytes=64)
    upload = UploadFile(storage, InMemoryUnitOfWork())

    with pytest.raises(FileTooLargeError) as exc:
        await upload.execute(stream(b"x" * 1000 + b"\n"), original_name="big.csv")
    assert exc.value.code == "FILE_TOO_LARGE"


async def test_a_jsonl_named_file_holding_something_else_is_refused() -> None:
    """The extension is the uploader's claim; the bytes are the evidence."""
    upload, _, _ = build()

    with pytest.raises(UnsupportedFileFormatError):
        await upload.execute(stream(CSV), original_name="pretend.jsonl")
