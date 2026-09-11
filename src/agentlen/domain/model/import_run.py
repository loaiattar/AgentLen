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
    """Summary of an import run, saved after each committed batch and at the end.

    Frozen as a historical record: even if raw_records are purged later,
    the report remains accurate. The counters do not share one unit
    (DATA_MODEL.md §6): lines for `read` and `rejected`, entities for the rest.
    """

    records_read: int  # source lines read, rejected ones included
    records_imported: int  # entities inserted: sessions and calls added together
    records_duplicate: int  # entities already stored: a session once per run
    records_rejected: int  # source lines with at least one `rejected` issue
    issues: tuple[ImportIssue, ...] = field(default_factory=tuple)
    # "entity.field" -> how many normalised entities lacked it (data-quality view).
    fields_missing: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def success_rate(self) -> float | None:
        if self.records_read == 0:
            return None
        return self.records_imported / self.records_read
