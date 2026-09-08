from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class TokenUsage:
    """Token counts for a single model call.

    All fields are optional: a source that does not provide cache details
    must remain distinguishable from a source reporting zero cache usage.
    None means unknown, not zero.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None

    @property
    def total(self) -> int | None:
        """Sum of input and output tokens.

        Returns None if both are unknown (not zero).
        Returns a partial sum if only one is known.
        """
        parts = [self.input_tokens, self.output_tokens]
        if all(p is None for p in parts):
            return None          # unknown ≠ zero
        return sum(p or 0 for p in parts)


@dataclass(frozen=True)
class ModelCall:
    """One request/response inference call within a session."""

    id: UUID
    session_id: UUID
    sequence_index: int              # order within the session
    token_usage: TokenUsage
    status: str                      # 'ok','error','unknown'
    model_name: str | None = None
    provider_name: str | None = None
    started_at: datetime | None = None
    duration_ms: int | None = None   # None ≠ 0 ms
    stop_reason: str | None = None
    error_code: str | None = None

    VALID_STATUSES = frozenset({"ok", "error", "unknown"})

    def __post_init__(self) -> None:
        if self.status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{self.status}'. "
                f"Must be one of {sorted(self.VALID_STATUSES)}."
            )
