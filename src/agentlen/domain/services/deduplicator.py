from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from agentlen.domain.model.import_run import ImportIssue


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
    def content_hash(payload: dict[str, Any] | None) -> str:
        """SHA-256 of the canonical JSON representation of a raw record.

        Used for file-level and record-level deduplication.
        Canonical = keys sorted, no extra whitespace, strict JSON (no NaN).
        """
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def storage_issue(payload: dict[str, Any], *, line_number: int) -> ImportIssue | None:
        """Why `payload` cannot be hashed and kept as a raw record, or None.

        A raw record is JSON text: strict JSON (no NaN or Infinity, JSON types
        only), valid Unicode, and no U+0000, which PostgreSQL's `jsonb` refuses.
        Such a record is rejected rather than altered: the payload is kept as
        written or not at all (ADR-008). The message names the offending path,
        never the value — it is trace content.
        """
        try:
            text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            text.encode()  # an unpaired surrogate fails here
        except (TypeError, ValueError, RecursionError):
            pass
        else:
            # Fast path: without this escape in the text there is no U+0000.
            if "\\u0000" not in text:
                return None
        found = _unstorable(payload, "$")
        if found is None:
            return None  # the escape was a literal backslash followed by "u0000"
        path, reason = found
        return ImportIssue(
            severity="rejected",
            code="UNSTORABLE_VALUE",
            message=f"Enregistrement non stockable : {reason} en {path}.",
            field_path=path,
            line_number=line_number,
        )


def _unstorable(value: Any, path: str) -> tuple[str, str] | None:  # noqa: PLR0911
    """The first path whose value cannot be stored, with the reason."""
    if isinstance(value, str):
        return None if _storable_text(value) else (path, _TEXT_REASON)
    if value is None or isinstance(value, bool | int):
        return None
    if isinstance(value, float):
        return None if math.isfinite(value) else (path, "nombre non fini (NaN ou infini)")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not _storable_text(key):
                return (path, "nom de champ invalide")
            if found := _unstorable(item, _member(path, key)):
                return found
        return None
    if isinstance(value, list):
        for index, item in enumerate(value):
            if found := _unstorable(item, f"{path}[{index}]"):
                return found
        return None
    return (path, f"valeur de type {type(value).__name__}, qui n'est pas un type JSON")


def _member(path: str, key: str) -> str:
    # MAPPING_CONTRACT.md §2.1: `.name` for a simple identifier, `["name"]` otherwise.
    if key.isascii() and key.isidentifier():
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


_TEXT_REASON = "texte contenant un caractère nul (U+0000) ou un Unicode invalide"


def _storable_text(text: str) -> bool:
    if "\x00" in text:
        return False
    try:
        text.encode()
    except UnicodeEncodeError:
        return False
    return True
