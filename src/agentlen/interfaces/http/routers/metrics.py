"""Dashboard metric routes.

`/metrics/definitions` is served from the domain registry and needs no database:
the definition of an indicator is a product decision, not a query result. That
also means the front can render the "how is this computed?" affordance before a
single file has been imported.
"""

from __future__ import annotations

from fastapi import APIRouter

from agentlen.application.dto.dashboard import day_bounds, point_filters
from agentlen.application.use_cases.query_dashboard import (
    QueryDashboardOverview,
    QueryMetricDefinitions,
)
from agentlen.domain.model.metrics import Coverage
from agentlen.interfaces.http.dependencies import DashboardQueriesDep
from agentlen.interfaces.http.filters import FiltersDep
from agentlen.interfaces.http.schemas.metrics import (
    ActivityPointOut,
    CoverageOut,
    DefinitionOut,
    DefinitionsOut,
    MetricOut,
    ModelPointOut,
    OverviewOut,
    PointsOut,
    QualityPointOut,
    ToolPointOut,
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


#: Emitted when cache figures are returned across more than one source. Cache
#: metrics are `per_source_only`: some sources report them, some never do, so a
#: total spanning both means "the sources that bothered" rather than "all of
#: them". The front must show this rather than let the number stand alone.
CACHE_CROSS_SOURCE_WARNING = (
    "Les métriques de cache ne sont pas comparables entre sources : certaines "
    "sources ne les fournissent pas. Filtrer par data_source_id pour les lire."
)


def _coverage(coverage: Coverage) -> CoverageOut:
    return CoverageOut(present=coverage.present, total=coverage.total, ratio=coverage.ratio)


@router.get(
    "/activity",
    response_model=PointsOut[ActivityPointOut],
    summary="Sessions and tokens per day and per source",
)
async def activity(
    queries: DashboardQueriesDep, filters: FiltersDep
) -> PointsOut[ActivityPointOut]:
    points = await queries.activity(filters)
    return PointsOut[ActivityPointOut](
        filters_applied=filters.as_drill_down(),
        points=[
            ActivityPointOut(
                day=p.day.isoformat(),
                data_source_id=p.data_source_id,
                session_count=p.session_count,
                model_call_count=p.model_call_count,
                tool_call_count=p.tool_call_count,
                input_tokens=p.input_tokens,
                output_tokens=p.output_tokens,
                coverage=_coverage(p.token_coverage),
                # A day is an interval on GET /sessions, not a date.
                filters=point_filters(
                    filters,
                    data_source_id=p.data_source_id,
                    date_from=day_bounds(p.day)[0],
                    date_to=day_bounds(p.day)[1],
                ),
            )
            for p in points
        ],
    )


@router.get(
    "/tools",
    response_model=PointsOut[ToolPointOut],
    summary="Call volume and error rate per tool",
)
async def tools(queries: DashboardQueriesDep, filters: FiltersDep) -> PointsOut[ToolPointOut]:
    points = await queries.tool_usage(filters)
    return PointsOut[ToolPointOut](
        filters_applied=filters.as_drill_down(),
        points=[
            ToolPointOut(
                label=p.tool_name,
                tool_id=p.tool_id,
                data_source_id=p.data_source_id,
                call_count=p.call_count,
                error_count=p.error_count,
                error_ratio=p.error_ratio,
                coverage=_coverage(p.status_coverage),
                filters=point_filters(filters, tool_id=p.tool_id, data_source_id=p.data_source_id),
            )
            for p in points
        ],
    )


@router.get(
    "/models",
    response_model=PointsOut[ModelPointOut],
    summary="Call volume and tokens per model and provider",
)
async def models(queries: DashboardQueriesDep, filters: FiltersDep) -> PointsOut[ModelPointOut]:
    points = await queries.model_usage(filters)

    warnings: list[str] = []
    sources_with_cache = {p.data_source_id for p in points if p.cache_coverage.present > 0}
    if filters.data_source_id is None and len({p.data_source_id for p in points}) > 1:
        if sources_with_cache:
            warnings.append(CACHE_CROSS_SOURCE_WARNING)

    return PointsOut[ModelPointOut](
        filters_applied=filters.as_drill_down(),
        warnings=warnings,
        points=[
            ModelPointOut(
                label=p.model_name or "unknown",
                model_id=p.model_id,
                provider_name=p.provider_name,
                data_source_id=p.data_source_id,
                call_count=p.call_count,
                input_tokens=p.input_tokens,
                output_tokens=p.output_tokens,
                coverage=_coverage(p.token_coverage),
                cache_read_tokens=p.cache_read_tokens,
                cache_coverage=_coverage(p.cache_coverage),
                filters=point_filters(
                    filters, model_id=p.model_id, data_source_id=p.data_source_id
                ),
            )
            for p in points
        ],
    )


@router.get(
    "/quality",
    response_model=PointsOut[QualityPointOut],
    summary="What each import got in, and what it rejected",
)
async def quality(queries: DashboardQueriesDep, filters: FiltersDep) -> PointsOut[QualityPointOut]:
    points = await queries.import_quality(filters)
    return PointsOut[QualityPointOut](
        filters_applied=filters.as_drill_down(),
        points=[
            QualityPointOut(
                import_run_id=p.import_run_id,
                data_source_id=p.data_source_id,
                status=p.status,
                records_read=p.records_read,
                records_imported=p.records_imported,
                records_duplicate=p.records_duplicate,
                records_rejected=p.records_rejected,
                issue_count=p.issue_count,
                rejection_ratio=p.rejection_ratio,
                fields_missing=p.fields_missing,
                filters=point_filters(
                    filters,
                    import_run_id=p.import_run_id,
                    data_source_id=p.data_source_id,
                ),
            )
            for p in points
        ],
    )
