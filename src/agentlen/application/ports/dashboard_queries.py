"""The read-side port (light CQRS).

Writes go through repositories and entities. Reads come through here, backed by
aggregated SQL that returns DTOs. The split exists because the two have opposite
needs: a write must load an aggregate to enforce its invariants, a dashboard
must not load ten thousand sessions to produce one average.

Implemented by `infrastructure/persistence/read_models/` against real SQL views,
and by an in-memory double for tests that must run without Postgres.
"""

from __future__ import annotations

from typing import Protocol

from agentlen.application.dto.dashboard import (
    ActivityPoint,
    DashboardFilters,
    ImportQualityPoint,
    ModelUsagePoint,
    OverviewTotals,
    ToolUsagePoint,
)


class DashboardQueries(Protocol):
    """Aggregated reads for the dashboard.

    Every method takes the same filters and returns DTOs — never domain
    entities, never a SQLAlchemy row. `import-linter` enforces that the
    application layer never sees the SQL side of this.
    """

    async def overview(self, filters: DashboardFilters) -> OverviewTotals:
        """Session, call and token totals behind the four headline indicators."""
        ...

    async def activity(self, filters: DashboardFilters) -> list[ActivityPoint]:
        """One point per day and per source, oldest first."""
        ...

    async def tool_usage(self, filters: DashboardFilters) -> list[ToolUsagePoint]:
        """One point per tool and per source, busiest first."""
        ...

    async def model_usage(self, filters: DashboardFilters) -> list[ModelUsagePoint]:
        """One point per model and per source, busiest first."""
        ...

    async def import_quality(self, filters: DashboardFilters) -> list[ImportQualityPoint]:
        """One row per import run, most recent first."""
        ...
