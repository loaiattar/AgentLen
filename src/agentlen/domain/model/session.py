from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Session:
    """One agent working session, from start to finish.

    All temporal fields are optional: a source that does not provide
    timestamps must remain distinguishable from a source that reports
    zero-duration sessions.
    """

    id: UUID
    data_source_id: int
    external_id: str  # identifier as found in the source
    agent_name: str | None = None
    started_at: datetime | None = None  # None = information absent
    ended_at: datetime | None = None
    duration_ms: int | None = None  # None ≠ 0 ms
    outcome: str | None = None  # 'completed','error','aborted','unknown'

    VALID_OUTCOMES = frozenset({"completed", "error", "aborted", "unknown"})

    def __post_init__(self) -> None:
        if self.outcome is not None and self.outcome not in self.VALID_OUTCOMES:
            raise ValueError(
                f"Invalid outcome '{self.outcome}'. Must be one of {sorted(self.VALID_OUTCOMES)}."
            )
