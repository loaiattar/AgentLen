"""Single domain definition of fields produced for each normalized entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any

TargetType = type[Any] | tuple[type[Any], ...] | None

# None means the field accepts arbitrary JSON. Keeping names and runtime types
# together prevents mapping validation and normalization from drifting apart.
TARGET_FIELD_TYPES: dict[str, dict[str, TargetType]] = {
    "session": {
        "external_id": str,
        "agent_name": str,
        "started_at": datetime,
        "ended_at": datetime,
        "duration_ms": int,
        "outcome": str,
    },
    "model_call": {
        "sequence_index": int,
        "model_name": str,
        "provider_name": str,
        "input_tokens": int,
        "output_tokens": int,
        "cache_read_tokens": int,
        "cache_creation_tokens": int,
        "duration_ms": int,
        "started_at": datetime,
        "stop_reason": str,
        "status": str,
        "error_code": str,
    },
    "tool_call": {
        "sequence_index": int,
        "tool_name": str,
        "status": str,
        "duration_ms": int,
        "started_at": datetime,
        "error_message": str,
    },
}
