"""Turn the read side's raw aggregates into the dashboard's published metrics.

The split is deliberate. `DashboardQueries` answers "what do the numbers say";
this use case answers "which four indicators do we publish, and what does each
one mean when the data is incomplete". The first is infrastructure, the second
is a product decision recorded in `domain/services/metric_registry.py`.

Keeping them apart is what lets a test assert the missing-value policy without
a database, and what stops the SQL from quietly becoming the definition.
"""

from __future__ import annotations

from agentlen.application.dto.dashboard import DashboardFilters, OverviewTotals
from agentlen.application.ports.dashboard_queries import DashboardQueries
from agentlen.domain.model.metrics import Coverage, MetricDefinition, MetricValue
from agentlen.domain.services import metric_registry

#: Emitted next to any `per_source_only` metric requested across several
#: sources. None of the current four are per-source, but the path exists so a
#: cache metric cannot be added later without the warning coming with it.
CROSS_SOURCE_WARNING = (
    "Indicateur non comparable entre sources : agrégé sur une seule source à la fois."
)


class QueryDashboardOverview:
    """Compose the four headline indicators (API.md §7)."""

    def __init__(self, queries: DashboardQueries) -> None:
        self._queries = queries

    async def execute(self, filters: DashboardFilters) -> list[MetricValue]:
        totals = await self._queries.overview(filters)
        return [
            self._build(definition, totals, filters)
            for definition in metric_registry.all_definitions()
        ]

    def _build(
        self,
        definition: MetricDefinition,
        totals: OverviewTotals,
        filters: DashboardFilters,
    ) -> MetricValue:
        value, coverage = self._value_and_coverage(definition.key, totals)
        warning = None
        if definition.comparability == "per_source_only" and filters.data_source_id is None:
            warning = CROSS_SOURCE_WARNING
        return MetricValue(
            key=definition.key,
            value=value,
            unit=definition.unit,
            coverage=coverage,
            warning=warning,
        )

    @staticmethod
    def _value_and_coverage(
        key: str, totals: OverviewTotals
    ) -> tuple[float | int | None, Coverage]:
        """Map one registry key onto the aggregates, following its stated policy.

        Every branch here mirrors a `missing_policy` string in the registry. A
        test asserts the two stay in step, because a policy that only lives in
        prose drifts from the code that is supposed to implement it.
        """
        match key:
            case "session_count":
                # A count is never unknown: zero sessions in scope really is
                # zero, so this one is always fully covered.
                n = totals.session_count
                return n, Coverage(present=n, total=n)
            case "avg_tokens_per_session":
                # Sessions carrying no token data at all are out of both the
                # numerator and the denominator — never counted as 0 tokens.
                return totals.avg_tokens_per_session, totals.token_coverage
            case "avg_session_duration_ms":
                # A missing duration is not a zero-length session.
                return totals.avg_session_duration_ms, totals.duration_coverage
            case "tool_error_rate":
                # Calls with status 'unknown' leave the denominator: treating
                # them as successes would deflate the rate on any source that
                # does not report tool outcomes.
                return totals.tool_error_rate, totals.tool_status_coverage
            case _:  # pragma: no cover - guarded by test_registry_is_fully_mapped
                raise KeyError(f"No mapping for metric '{key}'")


class QueryMetricDefinitions:
    """Serve the registry itself.

    `GET /metrics/definitions` exists so a number on the dashboard can always be
    traced to how it is computed and what it does with missing data — the
    "definition accessible" requirement.
    """

    @staticmethod
    def execute() -> tuple[MetricDefinition, ...]:
        return metric_registry.all_definitions()
