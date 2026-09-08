"""Dashboard metric routes.

`/metrics/definitions` is served from the domain registry and needs no database:
the definition of an indicator is a product decision, not a query result. That
also means the front can render the "how is this computed?" affordance before a
single file has been imported.
"""

from __future__ import annotations

from fastapi import APIRouter

from agentlen.application.use_cases.query_dashboard import (
    QueryDashboardOverview,
    QueryMetricDefinitions,
)
from agentlen.interfaces.http.dependencies import DashboardQueriesDep
from agentlen.interfaces.http.filters import FiltersDep
from agentlen.interfaces.http.schemas.metrics import (
    CoverageOut,
    DefinitionOut,
    DefinitionsOut,
    MetricOut,
    OverviewOut,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "/definitions",
    response_model=DefinitionsOut,
    summary="How each indicator is computed, and what it does with missing data",
)
async def definitions() -> DefinitionsOut:
    return DefinitionsOut(
        definitions=[
            DefinitionOut(
                key=d.key,
                label=d.label,
                unit=d.unit,
                formula=d.formula,
                scope=d.scope,
                missing_policy=d.missing_policy,
                comparability=d.comparability,
            )
            for d in QueryMetricDefinitions.execute()
        ]
    )


@router.get(
    "/overview",
    response_model=OverviewOut,
    summary="The four headline indicators, each with its coverage",
)
async def overview(queries: DashboardQueriesDep, filters: FiltersDep) -> OverviewOut:
    metrics = await QueryDashboardOverview(queries).execute(filters)
    return OverviewOut(
        filters_applied=filters.as_drill_down(),
        metrics=[
            MetricOut(
                key=m.key,
                value=m.value,
                unit=m.unit,
                coverage=CoverageOut(
                    present=m.coverage.present,
                    total=m.coverage.total,
                    ratio=m.coverage.ratio,
                ),
                warning=m.warning,
            )
            for m in metrics
        ],
    )
