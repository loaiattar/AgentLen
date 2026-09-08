from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    """Port for getting the current time.

    Replaced by a fixed clock in tests for deterministic results.
    """

    def now(self) -> datetime: ...


class SystemClock:
    """Default implementation: returns the real current UTC time."""

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)
