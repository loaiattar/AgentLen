"""Read-side exploration DTOs, including source provenance."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class SessionDetail:
    id: int
    data_source_id: int
    import_run_id: int
    raw_record_id: int
    external_id: str
    agent_id: int | None
    repository_id: int | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_ms: int | None
    outcome: str | None


@dataclass(frozen=True)
class ModelCallDetail:
    id: int
    session_id: int
    raw_record_id: int
    model_id: int | None
    sequence_index: int
    external_id: str | None
    started_at: datetime | None
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_creation_tokens: int | None
    reasoning_tokens: int | None
    stop_reason: str | None
    status: str
    error_code: str | None


@dataclass(frozen=True)
class ToolCallDetail:
    id: int
    session_id: int
    model_call_id: int | None
    raw_record_id: int
    tool_id: int
    sequence_index: int
    external_id: str | None
    started_at: datetime | None
    duration_ms: int | None
    status: str
    error_message: str | None
    arguments: Any
    result_size: int | None


@dataclass(frozen=True)
class SessionWithCalls:
    session: SessionDetail
    model_calls: list[ModelCallDetail]
    tool_calls: list[ToolCallDetail]


@dataclass(frozen=True)
class TimelineEvent:
    type: Literal["model_call", "tool_call"]
    event: ModelCallDetail | ToolCallDetail


@dataclass(frozen=True)
class RawRecordDetail:
    id: int
    import_run_id: int
    line_number: int
    payload: Any
    content_hash: str
