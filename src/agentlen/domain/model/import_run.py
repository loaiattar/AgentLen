from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportIssue:
    """One problem encountered during import for a specific source record."""

    severity: str  # 'rejected', 'duplicate', 'warning'
    code: str  # stable machine-readable code e.g. 'CAST_FAILED'
    message: str  # human-readable explanation
    field_path: str | None = None  # e.g. '$.usage.input_tokens'
    line_number: int | None = None  # position in the source file

    VALID_SEVERITIES = frozenset({"rejected", "duplicate", "warning"})

    def __post_init__(self) -> None:
        if self.severity not in self.VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of {sorted(self.VALID_SEVERITIES)}."
            )


@dataclass(frozen=True)
class ImportReport:
    """Summary produced at the end of an import run.

    Frozen as a historical record: even if raw_records are purged later,
    the report remains accurate.
    """

    records_read: int
    records_imported: int
    records_duplicate: int
    records_rejected: int
    issues: tuple[ImportIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def success_rate(self) -> float | None:
        if self.records_read == 0:
            return None
        return self.records_imported / self.records_read
