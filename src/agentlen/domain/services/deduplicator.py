from __future__ import annotations

import hashlib
import json
from typing import Any


class Deduplicator:
    """Computes natural keys for domain entities.

    Used by the import worker to determine whether an entity already
    exists in the database before inserting.
    """

    @staticmethod
    def natural_key(entity_target: str, data: dict[str, Any], natural_key_fields: list[str]) -> str:
        """Build a stable string key from the declared natural key fields.

        If any key field is missing, it is treated as an empty string so
        the key is always computable (import can proceed, but a warning
        is issued upstream).
        """
        parts = [entity_target]
        for field in natural_key_fields:
            parts.append(str(data.get(field, "")))
        return ":".join(parts)

    @staticmethod
    def content_hash(payload: dict[str, Any]) -> str:
        """SHA-256 of the canonical JSON representation of a raw record.

        Used for file-level and record-level deduplication.
        Canonical = keys sorted, no extra whitespace.
        """
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
