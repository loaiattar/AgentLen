"""Local file storage: streaming, hashing, and the refusals that matter.

These are the security properties from ARCHITECTURE §10, so each is asserted on
observed behaviour rather than on the code being written a certain way.
"""

from __future__ import annotations

import hashlib
import tracemalloc
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agentlen.application.ports.file_storage import (
    FileTooLargeError,
    UnsupportedFileFormatError,
)
from agentlen.infrastructure.files.local_storage import LocalFileStorage, detect_format

JSONL = b'{"session_id": "a3f2"}\n{"session_id": "b91c"}\n'
CSV = b"id,name\n1,alpha\n"
PARQUET = b"PAR1" + b"\x00" * 64 + b"PAR1"


async def stream(payload: bytes, *, chunk: int = 8) -> AsyncIterator[bytes]:
    for start in range(0, len(payload), chunk):
        yield payload[start : start + chunk]


async def test_content_hash_matches_a_plain_sha256(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)

    stored = await storage.store(stream(JSONL), original_name="t.jsonl")

    assert stored.content_hash == hashlib.sha256(JSONL).hexdigest()
    assert stored.size_bytes == len(JSONL)
    assert Path(stored.storage_path).read_bytes() == JSONL


async def test_the_path_never_contains_the_uploaded_name(tmp_path: Path) -> None:
    """Path traversal cannot work, because the name is not used to build the
    path at all — stronger than sanitising it, since there is nothing left to
    sanitise wrongly."""
    storage = LocalFileStorage(tmp_path)

    stored = await storage.store(stream(JSONL), original_name="../../../../etc/passwd.jsonl")

    path = Path(stored.storage_path).resolve()
    assert tmp_path.resolve() in path.parents
    assert "passwd" not in stored.storage_path
    assert "etc" not in Path(stored.storage_path).parts


async def test_identical_content_is_stored_once_on_disk(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)

    first = await storage.store(stream(JSONL), original_name="a.jsonl")
    second = await storage.store(stream(JSONL), original_name="b.jsonl")

    assert first.storage_path == second.storage_path
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(written) == 1


async def test_a_large_file_is_not_held_in_memory(tmp_path: Path) -> None:
    """The whole point of streaming. 64 MB written, peak allocation must stay
    far below it — otherwise a few concurrent uploads exhaust the process."""
    storage = LocalFileStorage(tmp_path)
    payload_size = 64 * 1024 * 1024

    async def big() -> AsyncIterator[bytes]:
        block = b'{"a":1}\n' * 1024  # 8 KiB
        yield b'{"session_id":"x"}\n'
        for _ in range(payload_size // len(block)):
            yield block

    tracemalloc.start()
    stored = await storage.store(big(), original_name="big.jsonl")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert stored.size_bytes > payload_size
    # Generous ceiling: the assertion is "not proportional to the file", not a
    # precise budget. Buffering the file whole would be ~64 MB.
    assert peak < 8 * 1024 * 1024, f"pic mémoire {peak / 1024 / 1024:.1f} Mo"


async def test_over_the_limit_is_refused_without_reading_it_all(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_bytes=1024)
    consumed = 0

    async def counted() -> AsyncIterator[bytes]:
        nonlocal consumed
        for _ in range(1000):
            consumed += 1
            yield b'{"a":1}\n' * 128  # 1 KiB per chunk

    with pytest.raises(FileTooLargeError):
        await storage.store(counted(), original_name="big.jsonl")

    # Refusing a huge upload must not require reading the whole thing first.
    assert consumed < 10


async def test_a_refused_upload_leaves_nothing_behind(tmp_path: Path) -> None:
    """A partially written file must not be mistaken for a stored one."""
    storage = LocalFileStorage(tmp_path, max_bytes=64)

    with pytest.raises(FileTooLargeError):
        await storage.store(stream(b'{"a":1}\n' * 100), original_name="big.jsonl")

    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


@pytest.mark.parametrize("name", ["x.exe", "x.txt", "x.zip", "x"])
async def test_disallowed_extensions_are_refused(tmp_path: Path, name: str) -> None:
    storage = LocalFileStorage(tmp_path)

    with pytest.raises(UnsupportedFileFormatError):
        await storage.store(stream(JSONL), original_name=name)


# ---------------------------------------------------------------------------
# Format detection: the bytes decide, not the extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "name", "expected"),
    [
        (JSONL, "t.jsonl", "jsonl"),
        (JSONL, "t.csv", "jsonl"),  # misnamed, content wins
        (CSV, "t.csv", "csv"),
        (PARQUET, "t.parquet", "parquet"),
        (PARQUET, "t.csv", "parquet"),  # magic bytes win over extension
    ],
)
def test_format_is_detected_from_content(payload: bytes, name: str, expected: str) -> None:
    assert detect_format(payload, name) == expected


def test_a_file_claiming_jsonl_but_holding_csv_is_refused() -> None:
    with pytest.raises(UnsupportedFileFormatError):
        detect_format(CSV, "pretend.jsonl")


def test_broken_json_is_refused_rather_than_read_as_csv() -> None:
    with pytest.raises(UnsupportedFileFormatError):
        detect_format(b'{"unterminated": \n', "t.jsonl")


def test_binary_that_is_not_parquet_is_refused() -> None:
    with pytest.raises(UnsupportedFileFormatError):
        detect_format(b"\x89PNG\r\n\x1a\n\x00\x00", "t.csv")
