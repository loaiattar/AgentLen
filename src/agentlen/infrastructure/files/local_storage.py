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

import hashlib
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

from agentlen.application.ports.file_storage import (
    FileTooLargeError,
    StoredFile,
    UnsupportedFileFormatError,
)

#: Read granularity. Large enough to keep syscalls cheap, small enough that a
#: hostile upload cannot make one chunk expensive.
CHUNK_SIZE = 1024 * 1024

#: Enough to hold a first line and the Parquet marker; format detection needs
#: no more than that, and keeping it small bounds what a hostile first "line"
#: can make us buffer.
_HEAD_BYTES = 64 * 1024

ALLOWED_EXTENSIONS = {".jsonl", ".ndjson", ".csv", ".parquet"}
DEFAULT_MAX_UPLOAD_MB = 512

#: Parquet brackets its payload with this marker at both ends.
_PARQUET_MAGIC = b"PAR1"


def max_upload_bytes() -> int:
    return int(os.environ.get("MAX_UPLOAD_SIZE_MB", DEFAULT_MAX_UPLOAD_MB)) * 1024 * 1024


def detect_format(head: bytes, original_name: str) -> str:
    """Identify the format from the leading bytes, using the name only to
    disambiguate between two text formats that both look plausible."""
    if head.startswith(_PARQUET_MAGIC):
        return "parquet"

    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedFileFormatError(
            "Le contenu n'est ni du Parquet ni du texte UTF-8."
        ) from None

    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if first_line.startswith("{"):
        try:
            json.loads(first_line)
            return "jsonl"
        except json.JSONDecodeError:
            # A line that opens like JSON and does not parse is a broken JSONL,
            # not a CSV whose first cell happens to start with a brace.
            raise UnsupportedFileFormatError(
                "La première ligne ressemble à du JSON mais ne parse pas."
            ) from None

    suffix = Path(original_name).suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
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

    async def store(self, chunks: AsyncIterator[bytes], *, original_name: str) -> StoredFile:
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileFormatError(
                f"Extension '{suffix or 'aucune'}' non autorisée. "
                f"Attendu : {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        self._root.mkdir(parents=True, exist_ok=True)
        # Written under a temporary name first: a file only becomes visible at
        # its content-addressed path once it is complete, so a failed upload
        # cannot be mistaken for a stored one.
        staging = self._root / f".incoming-{os.getpid()}-{id(chunks):x}"

        digest = hashlib.sha256()
        size = 0
        # Collected then joined once: repeatedly concatenating bytes would copy
        # the accumulated head on every chunk, which is quadratic and shows up
        # as a memory spike on small chunk sizes.
        head_parts: list[bytes] = []
        head_len = 0
        try:
            with staging.open("wb") as out:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise FileTooLargeError(
                            f"Fichier trop volumineux : limite "
                            f"{self._max_bytes // (1024 * 1024)} Mo."
                        )
                    if head_len < _HEAD_BYTES:
                        piece = chunk[: _HEAD_BYTES - head_len]
                        head_parts.append(piece)
                        head_len += len(piece)
                    digest.update(chunk)
                    out.write(chunk)

            detected = detect_format(b"".join(head_parts), original_name)
            content_hash = digest.hexdigest()

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
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
