"""In-memory `FileStorage`, so the upload use case can be tested without a disk.

Enforces the same refusals as the real one — extension, size, format detection —
because a double that accepts what production rejects turns every upload test
into a false positive.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import AsyncIterator
from pathlib import Path

from agentlen.application.ports.file_storage import (
    FileTooLargeError,
    StoredFile,
    UnsupportedFileFormatError,
)
from agentlen.infrastructure.files.local_storage import ALLOWED_EXTENSIONS, detect_file_format


class InMemoryFileStorage:
    def __init__(self, *, max_bytes: int = 512 * 1024 * 1024) -> None:
        self._max_bytes = max_bytes
        self.contents: dict[str, bytes] = {}

    async def store(self, chunks: AsyncIterator[bytes], *, original_name: str) -> StoredFile:
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileFormatError(f"Extension '{suffix or 'aucune'}' non autorisée.")

        body = b""
        async for chunk in chunks:
            body += chunk
            if len(body) > self._max_bytes:
                raise FileTooLargeError("Fichier trop volumineux.")

        # The same reading rule as the real storage — same head size, same
        # extension for a long first line — not a bigger head of its own that
        # would hide the cases production refuses.
        detected = detect_file_format(io.BytesIO(body).read, original_name)
        content_hash = hashlib.sha256(body).hexdigest()
        self.contents[content_hash] = body
        return StoredFile(
            storage_path=f"memory://{content_hash}",
            size_bytes=len(body),
            content_hash=content_hash,
            detected_format=detected,
        )
