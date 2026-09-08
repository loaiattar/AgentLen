"""Read-side DTOs for the dashboard.

Every aggregate over a nullable column travels with its `Coverage`. That pairing
is the whole point of this module: `SUM` skips NULLs silently, so a total of
184 203 tokens computed over 12 % of the rows is indistinguishable from one
computed over all of them unless the counts travel alongside it (ADR-009).

`Coverage` itself is reused from the domain rather than duplicated. It is a pure
value object with no I/O and no identity, and it is exactly the shape the API
contract promises; a second near-identical class here would drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from agentlen.domain.model.metrics import Coverage


@dataclass(frozen=True)
class DashboardFilters:
    """Filters shared by every read-side query.

    The same names are accepted by `GET /sessions`, which is what makes the
    drill-down contract work: a chart point hands its filters straight back to
    the session list with no translation (API.md §6).
    """

    data_source_id: int | None = None
    agent_id: int | None = None
    model_id: int | None = None
    tool_id: int | None = None
    import_run_id: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None

    def as_drill_down(self) -> dict[str, object]:
        """The non-empty filters, ready to be replayed on `GET /sessions`."""
        return {
            name: value
            for name, value in (
                ("data_source_id", self.data_source_id),
                ("agent_id", self.agent_id),
                ("model_id", self.model_id),
                ("tool_id", self.tool_id),
                ("import_run_id", self.import_run_id),
                ("date_from", self.date_from.isoformat() if self.date_from else None),
                ("date_to", self.date_to.isoformat() if self.date_to else None),
            )
            if value is not None
        }


@dataclass(frozen=True)
class OverviewTotals:
    """Session-level aggregates behind the four headline indicators.

    Values are `None` when nothing in scope carried the information — never 0.
    The paired `Coverage` says how much of the scope contributed.
    """

    session_count: int
    model_call_count: int
    tool_call_count: int

    total_input_tokens: int | None
    total_output_tokens: int | None
    token_coverage: Coverage

    avg_tokens_per_session: float | None
    avg_session_duration_ms: float | None
    duration_coverage: Coverage

    tool_error_count: int
    tool_status_known_count: int

    @property
    def tool_error_rate(self) -> float | None:
        """Errors over calls with a *known* status.

        Calls with `status = 'unknown'` leave the denominator entirely: counting
        them as successes would quietly deflate the rate on any source that does
        not report tool outcomes.
        """
        if self.tool_status_known_count == 0:
            return None
        return self.tool_error_count / self.tool_status_known_count

    @property
    def tool_status_coverage(self) -> Coverage:
        return Coverage(present=self.tool_status_known_count, total=self.tool_call_count)


@dataclass(frozen=True)
class ActivityPoint:
    """One day, for one source."""

    day: date
    data_source_id: int
    session_count: int
    model_call_count: int
    tool_call_count: int
    input_tokens: int | None
    output_tokens: int | None
    token_coverage: Coverage


@dataclass(frozen=True)
class ToolUsagePoint:
    """One tool, for one source."""

    tool_id: int
    tool_name: str
    data_source_id: int
    call_count: int
    error_count: int
    status_known_count: int

    @property
    def error_ratio(self) -> float | None:
        if self.status_known_count == 0:
            return None
        return self.error_count / self.status_known_count

    @property
    def status_coverage(self) -> Coverage:
        return Coverage(present=self.status_known_count, total=self.call_count)


@dataclass(frozen=True)
class ModelUsagePoint:
    """One model, for one source."""

    model_id: int | None
    model_name: str | None
    provider_name: str | None
    data_source_id: int
    call_count: int
    input_tokens: int | None
    output_tokens: int | None
    token_coverage: Coverage
    #: Cache metrics are absent from some sources entirely. Their coverage is
    #: what makes `cache_read_ratio` a `per_source_only` metric rather than a
    #: number that silently means different things per source.
    cache_read_tokens: int | None
    cache_coverage: Coverage


@dataclass(frozen=True)
class ImportQualityPoint:
    """One import run: what got in, what did not, and why."""

    import_run_id: int
    data_source_id: int
    status: str
    records_read: int
    records_imported: int
    records_duplicate: int
    records_rejected: int
    issue_count: int
    fields_missing: dict[str, int] = field(default_factory=dict)

    @property
    def rejection_ratio(self) -> float | None:
        if self.records_read == 0:
            return None
        return self.records_rejected / self.records_read
