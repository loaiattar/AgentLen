"""Local-disk implementation of `FileStorage`.

Three properties matter more than the storage itself:

**Nothing is ever held whole in memory.** The stream is consumed in chunks and
written straight through, with the hash and the byte count accumulated as it
passes. A 500 MB upload costs one chunk of memory, not 500 MB.

**The path never contains anything the user chose.** Files are stored
content-addressed — `<root>/<hash[:2]>/<hash>` — so a name like
`../../etc/passwd` cannot escape the directory, because the name is not used to
build the path at all. That is stronger than sanitising the name, since there is
nothing left to sanitise wrong.

**The format comes from the bytes.** An extension is a claim by the uploader;
the magic bytes are evidence. Both are checked, and the evidence wins.
"""

from __future__ import annotations

import asyncio
import codecs
import hashlib
import json
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import BinaryIO

from agentlen.application.ports.file_storage import (
    FileTooLargeError,
    StoredFile,
    UnsupportedFileFormatError,
)

#: Read granularity. Large enough to keep syscalls cheap, small enough that a
#: hostile upload cannot make one chunk expensive.
CHUNK_SIZE = 1024 * 1024

#: What format detection reads first: enough for the Parquet marker, a CSV
#: header, and the first record of a typical JSONL.
HEAD_BYTES = 64 * 1024

#: How far detection keeps reading when the head opens a JSON line it does not
#: finish. A trace that embeds tool output can easily put 80 KB on one line, so
#: the head alone is not enough; the bound keeps a hostile newline-free "line"
#: from making us buffer the whole upload.
MAX_FIRST_LINE_BYTES = 8 * CHUNK_SIZE

ALLOWED_EXTENSIONS = {".jsonl", ".ndjson", ".csv", ".parquet"}
DEFAULT_MAX_UPLOAD_MB = 512

_JSONL_SUFFIXES = {".jsonl", ".ndjson"}

#: Parquet brackets its payload with this marker at both ends.
_PARQUET_MAGIC = b"PAR1"


def max_upload_bytes() -> int:
    return int(os.environ.get("MAX_UPLOAD_SIZE_MB", DEFAULT_MAX_UPLOAD_MB)) * 1024 * 1024


def detect_file_format(read: Callable[[int], bytes], original_name: str) -> str:
    """Identify the format of a file readable through `read` (a binary
    `file.read`), from its leading bytes.

    Shared by the real storage and its in-memory test double, so both read
    exactly the same bytes before deciding.

    The first JSON line is read to its end, up to `MAX_FIRST_LINE_BYTES`,
    rather than guessed from its opening brace: the line is then really parsed,
    so a broken JSONL is still refused at upload instead of surfacing later as
    an import where every record fails. Reading further only happens for a line
    that opens with `{` and is longer than the head, so Parquet and CSV files
    cost the same `HEAD_BYTES` as before.
    """
    head = read(HEAD_BYTES)
    stripped = head.lstrip()
    if stripped.startswith(b"{") and b"\n" not in stripped:
        parts = [head]
        total = len(head)
        while total < MAX_FIRST_LINE_BYTES:
            piece = read(min(CHUNK_SIZE, MAX_FIRST_LINE_BYTES - total))
            if not piece:
                break
            parts.append(piece)
            total += len(piece)
            if b"\n" in piece:
                break
        head = b"".join(parts)
    truncated = read(1) != b""
    return detect_format(head, original_name, truncated=truncated)


def detect_format(head: bytes, original_name: str, *, truncated: bool = False) -> str:
    """Identify the format from the leading bytes, using the name only to
    disambiguate between two text formats that both look plausible.

    `truncated` says the file goes on past `head`: its last character or its
    first line may then be cut, which is not a defect of the file.
    """
    if head.startswith(_PARQUET_MAGIC):
        return "parquet"

    try:
        # A head cut mid-file can end inside a multi-byte character (an accent,
        # an emoji). The incremental decoder holds such a trailing fragment back
        # instead of failing, and still refuses invalid bytes anywhere else.
        text = codecs.getincrementaldecoder("utf-8")().decode(head, final=not truncated)
    except UnicodeDecodeError:
        raise UnsupportedFileFormatError(
            "Le contenu n'est ni du Parquet ni du texte UTF-8."
        ) from None

    suffix = Path(original_name).suffix.lower()
    # Split on "\n" only, as JSONL does: `str.splitlines` also breaks on
    # characters such as U+2028 that JSON allows raw inside a string.
    lines = text.split("\n")
    index, first_line = next(
        ((i, line) for i, line in enumerate(lines) if line.strip()), (len(lines), "")
    )
    if first_line.startswith("{"):
        if truncated and index == len(lines) - 1:
            # Still no end of line after MAX_FIRST_LINE_BYTES: the record cannot
            # be parsed here. It opens like JSON and, if the name says JSONL too,
            # the two claims agree; the record reader explains any bad record.
            if suffix in _JSONL_SUFFIXES:
                return "jsonl"
            raise UnsupportedFileFormatError(
                f"La première ligne dépasse {MAX_FIRST_LINE_BYTES // (1024 * 1024)} Mo "
                "et le fichier n'est pas nommé '.jsonl' : format non vérifiable."
            )
        try:
            json.loads(first_line)
            return "jsonl"
        except json.JSONDecodeError:
            # A line that opens like JSON and does not parse is a broken JSONL,
            # not a CSV whose first cell happens to start with a brace.
            raise UnsupportedFileFormatError(
                "La première ligne ressemble à du JSON mais ne parse pas."
            ) from None

    if suffix in _JSONL_SUFFIXES:
        raise UnsupportedFileFormatError(
            f"Le fichier est nommé '{suffix}' mais son contenu n'est pas du JSONL."
        )
    if first_line:
        return "csv"
    raise UnsupportedFileFormatError("Fichier vide ou format non reconnu.")


class LocalFileStorage:
    def __init__(self, root: str | Path, *, max_bytes: int | None = None) -> None:
        self._root = Path(root)
        self._max_bytes = max_bytes if max_bytes is not None else max_upload_bytes()

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    async def store(self, chunks: AsyncIterator[bytes], *, original_name: str) -> StoredFile:
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileFormatError(
                f"Extension '{suffix or 'aucune'}' non autorisée. "
                f"Attendu : {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        # Every disk operation and the hashing run in a worker thread: an upload
        # of several hundred megabytes must not stall the other requests the
        # event loop is serving.
        await asyncio.to_thread(self._root.mkdir, parents=True, exist_ok=True)
        # Written under a temporary name first: a file only becomes visible at
        # its content-addressed path once it is complete, so a failed upload
        # cannot be mistaken for a stored one.
        staging = self._root / f".incoming-{os.getpid()}-{id(chunks):x}"

        digest = hashlib.sha256()
        size = 0
        out = await asyncio.to_thread(staging.open, "wb")
        try:
            # Network chunks are small (tens of KB); they are grouped up to
            # CHUNK_SIZE so a large upload costs few thread hand-offs.
            pending: list[bytes] = []
            pending_size = 0
            async for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                # Checked before anything is buffered or written: the refusal
                # comes as soon as the stream crosses the limit.
                if size > self._max_bytes:
                    raise FileTooLargeError(
                        f"Fichier trop volumineux : limite {self._max_bytes // (1024 * 1024)} Mo."
                    )
                pending.append(chunk)
                pending_size += len(chunk)
                if pending_size >= CHUNK_SIZE:
                    await asyncio.to_thread(_append, out, digest.update, b"".join(pending))
                    pending, pending_size = [], 0
            await asyncio.to_thread(_append, out, digest.update, b"".join(pending))
            await asyncio.to_thread(out.close)

            return await asyncio.to_thread(
                self._place, staging, digest.hexdigest(), size, original_name
            )
        except BaseException:
            # Synchronous on purpose: this also runs when the request is
            # cancelled, where awaiting a thread could be interrupted in turn
            # and leave the partial file behind.
            out.close()
            staging.unlink(missing_ok=True)
            raise

    def _place(self, staging: Path, content_hash: str, size: int, original_name: str) -> StoredFile:
        """Detect the format and move the staged file to its final path.

        Blocking: called through `asyncio.to_thread`.
        """
        # Read back from the staged file rather than captured in flight:
        # detection may need more than the head when the first JSON line is
        # long, and the bytes are already on disk.
        with staging.open("rb") as written:
            detected = detect_file_format(written.read, original_name)

        final = self._root / content_hash[:2] / content_hash
        final.parent.mkdir(parents=True, exist_ok=True)
        # Same content uploaded twice: the bytes are already there, and
        # they are identical by construction.
        if final.exists():
            staging.unlink(missing_ok=True)
        else:
            staging.replace(final)

        return StoredFile(
            storage_path=str(final),
            size_bytes=size,
            content_hash=content_hash,
            detected_format=detected,
        )


def _append(out: BinaryIO, hash_update: Callable[[bytes], None], data: bytes) -> None:
    """Hash and write one group of chunks. Blocking: run in a worker thread.

    `hashlib` releases the GIL on large buffers, so hashing here does not hold
    back the event loop either.
    """
    hash_update(data)
    out.write(data)
