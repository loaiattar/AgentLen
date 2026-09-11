from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation within a session."""

    id: UUID
    session_id: UUID
    sequence_index: int  # order within the session
    tool_name: str
    status: str  # 'ok','error','unknown'
    duration_ms: int | None = None  # None ≠ 0 ms
    error_message: str | None = None
    model_call_id: UUID | None = None  # the model call that triggered this, if known
    started_at: datetime | None = None

    VALID_STATUSES = frozenset({"ok", "error", "unknown"})

    def __post_init__(self) -> None:
        if self.status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of {sorted(self.VALID_STATUSES)}."
            )
