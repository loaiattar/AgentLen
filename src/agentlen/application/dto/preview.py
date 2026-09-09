"""What a dry-run would have done."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PreviewIssue:
    """One problem, located precisely enough to act on."""

    line_number: int | None
    severity: str
    code: str
    message: str
    field_path: str | None = None


@dataclass(frozen=True)
class PreviewEntities:
    """A sample of what would be created, per target entity."""

    target: str
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class PreviewResult:
    """The body of `POST /imports/preview` (API.md §5)."""

    sampled: int
    would_import: dict[str, int]
    would_reject: int
    entities: list[PreviewEntities] = field(default_factory=list)
    issues: list[PreviewIssue] = field(default_factory=list)
