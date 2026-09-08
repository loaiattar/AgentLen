"""SQL implementation of `DashboardQueries`, reading the views from revision 0002.

Every filter is bound, never interpolated: the only thing that varies between
requests is the set of parameters, and no user value ever becomes SQL text.
Column names come from a closed set defined here, so there is no path from
input to an identifier either.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.application.dto.dashboard import (
    ActivityPoint,
    DashboardFilters,
    ImportQualityPoint,
    ModelUsagePoint,
    OverviewTotals,
    ToolUsagePoint,
)
from agentlen.domain.model.metrics import Coverage


def _session_predicates(filters: DashboardFilters) -> tuple[list[str], dict[str, Any]]:
    """WHERE fragments over `v_session_metrics`, plus their bound parameters.

    `model_id` and `tool_id` do not live on a session, so they become EXISTS
    restrictions: "sessions that used this model / this tool". That is what the
    drill-down means when a chart point for tool Bash is replayed on the session
    list.
    """
    where: list[str] = []
    params: dict[str, Any] = {}

    for column in ("data_source_id", "agent_id", "import_run_id"):
        value = getattr(filters, column)
        if value is not None:
            where.append(f"sm.{column} = :{column}")
            params[column] = value

    if filters.date_from is not None:
        where.append("sm.started_at >= :date_from")
        params["date_from"] = filters.date_from
    if filters.date_to is not None:
        where.append("sm.started_at <= :date_to")
        params["date_to"] = filters.date_to

    if filters.model_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM model_call mc "
            "WHERE mc.session_id = sm.session_id AND mc.model_id = :model_id)"
        )
        params["model_id"] = filters.model_id
    if filters.tool_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM tool_call tc "
            "WHERE tc.session_id = sm.session_id AND tc.tool_id = :tool_id)"
        )
        params["tool_id"] = filters.tool_id

    return where, params


def _clause(where: list[str]) -> str:
    """Join predicate fragments into a WHERE clause.

    The only place this module composes SQL text. Every fragment reaching here
    is a literal written in `_session_predicates` or `import_quality`; user
    input only ever arrives as a bound parameter, and no identifier is ever
    derived from a request. That is why the `S608` suppressions below are
    accurate rather than a silencing — check this function and you have checked
    all of them.
    """
    return f"WHERE {' AND '.join(where)}" if where else ""


def _coverage(row: Row[Any], present: str, total: str) -> Coverage:
    return Coverage(present=int(row._mapping[present] or 0), total=int(row._mapping[total] or 0))


def _ratio(numerator: int | None, denominator: int) -> float | None:
    """None when nothing contributed — never 0.0, which would read as a real
    measurement of zero."""
    if not denominator or numerator is None:
        return None
    return numerator / denominator


class SqlDashboardQueries:
    """Reads the dashboard views. One instance per request is fine: it holds
    only the engine.

    On `coalesce(..., 0)` below: it appears only over **counts** — calls,
    errors, coverage numerators. Zero calls really is zero calls, so a count is
    not a measurement that can be absent. It never appears over a measure
    (`input_tokens`, `duration_ms`, `cache_read_tokens`): those stay NULL when
    unknown, which is the whole point of ADR-009 and the reason the coverage
    counters exist beside them.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def overview(self, filters: DashboardFilters) -> OverviewTotals:
        where, params = _session_predicates(filters)
        sql = text(f"""
            SELECT
                count(*)                            AS session_count,
                coalesce(sum(sm.model_call_count), 0) AS model_call_count,
                coalesce(sum(sm.tool_call_count), 0)  AS tool_call_count,
                sum(sm.input_tokens)                AS total_input_tokens,
                sum(sm.output_tokens)               AS total_output_tokens,
                -- A session counts towards token coverage once it has at least
                -- one call carrying token data.
                count(*) FILTER (WHERE sm.token_records_present > 0) AS token_sessions_present,
                avg(sm.input_tokens + sm.output_tokens)              AS avg_tokens_per_session,
                avg(sm.duration_ms)                                  AS avg_session_duration_ms,
                count(sm.duration_ms)                                AS duration_present,
                coalesce(sum(sm.tool_error_count), 0)                AS tool_error_count,
                coalesce(sum(sm.tool_status_known_count), 0)         AS tool_status_known_count
            FROM v_session_metrics sm
            {_clause(where)}
        """)
        async with self._engine.connect() as conn:
            row = (await conn.execute(sql, params)).one()

        m = row._mapping
        session_count = int(m["session_count"])
        return OverviewTotals(
            session_count=session_count,
            model_call_count=int(m["model_call_count"]),
            tool_call_count=int(m["tool_call_count"]),
            total_input_tokens=m["total_input_tokens"],
            total_output_tokens=m["total_output_tokens"],
            token_coverage=Coverage(int(m["token_sessions_present"]), session_count),
            avg_tokens_per_session=(
                float(m["avg_tokens_per_session"])
                if m["avg_tokens_per_session"] is not None
                else None
            ),
            avg_session_duration_ms=(
                float(m["avg_session_duration_ms"])
                if m["avg_session_duration_ms"] is not None
                else None
            ),
            duration_coverage=Coverage(int(m["duration_present"]), session_count),
            tool_error_count=int(m["tool_error_count"]),
            tool_status_known_count=int(m["tool_status_known_count"]),
        )

    async def activity(self, filters: DashboardFilters) -> list[ActivityPoint]:
        where, params = _session_predicates(filters)
        sql = text(f"""
            SELECT
                (sm.started_at AT TIME ZONE 'UTC')::date AS day,
                sm.data_source_id,
                count(*)                        AS session_count,
                coalesce(sum(sm.model_call_count), 0) AS model_call_count,
                coalesce(sum(sm.tool_call_count), 0)  AS tool_call_count,
                sum(sm.input_tokens)            AS input_tokens,
                sum(sm.output_tokens)           AS output_tokens,
                coalesce(sum(sm.token_records_present), 0) AS token_records_present,
                coalesce(sum(sm.token_records_total), 0)   AS token_records_total
            FROM v_session_metrics sm
            {_clause([*where, "sm.started_at IS NOT NULL"])}
            GROUP BY 1, 2
            ORDER BY 1, 2
        """)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(sql, params)).all()

        return [
            ActivityPoint(
                day=r._mapping["day"],
                data_source_id=int(r._mapping["data_source_id"]),
                session_count=int(r._mapping["session_count"]),
                model_call_count=int(r._mapping["model_call_count"]),
                tool_call_count=int(r._mapping["tool_call_count"]),
                input_tokens=r._mapping["input_tokens"],
                output_tokens=r._mapping["output_tokens"],
                token_coverage=_coverage(r, "token_records_present", "token_records_total"),
            )
            for r in rows
        ]

    async def tool_usage(self, filters: DashboardFilters) -> list[ToolUsagePoint]:
        where, params = _session_predicates(filters)
        sql = text(f"""
            SELECT tu.tool_id, tu.tool_name, tu.data_source_id,
                   tu.call_count, tu.error_count, tu.status_known_count
            FROM v_tool_usage tu
            WHERE EXISTS (
                SELECT 1 FROM v_session_metrics sm
                {_clause([*where, "sm.data_source_id = tu.data_source_id"])}
            )
            ORDER BY tu.call_count DESC, tu.tool_name
        """)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(sql, params)).all()

        return [
            ToolUsagePoint(
                tool_id=int(r._mapping["tool_id"]),
                tool_name=str(r._mapping["tool_name"]),
                data_source_id=int(r._mapping["data_source_id"]),
                call_count=int(r._mapping["call_count"]),
                error_count=int(r._mapping["error_count"]),
                status_known_count=int(r._mapping["status_known_count"]),
            )
            for r in rows
        ]

    async def model_usage(self, filters: DashboardFilters) -> list[ModelUsagePoint]:
        where, params = _session_predicates(filters)
        sql = text(f"""
            SELECT mu.*
            FROM v_model_usage mu
            WHERE EXISTS (
                SELECT 1 FROM v_session_metrics sm
                {_clause([*where, "sm.data_source_id = mu.data_source_id"])}
            )
            ORDER BY mu.call_count DESC, mu.model_name NULLS LAST
        """)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(sql, params)).all()

        return [
            ModelUsagePoint(
                model_id=r._mapping["model_id"],
                model_name=r._mapping["model_name"],
                provider_name=r._mapping["provider_name"],
                data_source_id=int(r._mapping["data_source_id"]),
                call_count=int(r._mapping["call_count"]),
                input_tokens=r._mapping["input_tokens"],
                output_tokens=r._mapping["output_tokens"],
                token_coverage=_coverage(r, "token_records_present", "token_records_total"),
                cache_read_tokens=r._mapping["cache_read_tokens"],
                cache_coverage=_coverage(r, "cache_records_present", "token_records_total"),
            )
            for r in rows
        ]

    async def import_quality(self, filters: DashboardFilters) -> list[ImportQualityPoint]:
        where: list[str] = []
        params: dict[str, Any] = {}
        if filters.data_source_id is not None:
            where.append("iq.data_source_id = :data_source_id")
            params["data_source_id"] = filters.data_source_id
        if filters.import_run_id is not None:
            where.append("iq.import_run_id = :import_run_id")
            params["import_run_id"] = filters.import_run_id

        sql = text(f"""
            SELECT iq.* FROM v_import_quality iq
            {_clause(where)}
            ORDER BY iq.created_at DESC, iq.import_run_id DESC
        """)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(sql, params)).all()

        return [
            ImportQualityPoint(
                import_run_id=int(r._mapping["import_run_id"]),
                data_source_id=int(r._mapping["data_source_id"]),
                status=str(r._mapping["status"]),
                records_read=int(r._mapping["records_read"]),
                records_imported=int(r._mapping["records_imported"]),
                records_duplicate=int(r._mapping["records_duplicate"]),
                records_rejected=int(r._mapping["records_rejected"]),
                issue_count=int(r._mapping["issue_count"]),
                fields_missing=dict(r._mapping["fields_missing"] or {}),
            )
            for r in rows
        ]
