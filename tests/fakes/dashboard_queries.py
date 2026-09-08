"""In-memory `DashboardQueries`, written from the spec rather than from the SQL.

Two jobs:

1. It lets use-case tests run without Postgres.
2. It is the **independent reference** the integration tests compare the SQL
   views against. That only means something if it was written from
   `DATA_MODEL.md` §7 and the metric registry, not transliterated from the
   view definitions — a reference that mirrors the implementation proves the
   two agree, not that either is right.

Records are plain dicts, the shape the tables hold.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from agentlen.application.dto.dashboard import (
    ActivityPoint,
    DashboardFilters,
    ImportQualityPoint,
    ModelUsagePoint,
    OverviewTotals,
    ToolUsagePoint,
)
from agentlen.domain.model.metrics import Coverage


def _mean(values: list[float]) -> float | None:
    """None on an empty set — an average of nothing is unknown, not zero."""
    return sum(values) / len(values) if values else None


def _total(values: list[int | None]) -> int | None:
    """Sum of the known values; None when nothing was known at all.

    Mirrors SQL's SUM: it skips NULLs, and over an all-NULL set it yields NULL.
    """
    known = [v for v in values if v is not None]
    return sum(known) if known else None


@dataclass
class InMemoryDashboardQueries:
    """Aggregates the same numbers as the views, in Python."""

    sessions: list[dict[str, Any]] = field(default_factory=list)
    model_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    import_runs: list[dict[str, Any]] = field(default_factory=list)
    import_issues: list[dict[str, Any]] = field(default_factory=list)

    # -- filtering ---------------------------------------------------------

    def _matching_sessions(self, f: DashboardFilters) -> list[dict[str, Any]]:
        kept = []
        for s in self.sessions:
            if f.data_source_id is not None and s["data_source_id"] != f.data_source_id:
                continue
            if f.agent_id is not None and s.get("agent_id") != f.agent_id:
                continue
            if f.import_run_id is not None and s.get("import_run_id") != f.import_run_id:
                continue
            started: datetime | None = s.get("started_at")
            if f.date_from is not None and (started is None or started < f.date_from):
                continue
            if f.date_to is not None and (started is None or started > f.date_to):
                continue
            if f.model_id is not None and not any(
                c["session_id"] == s["id"] and c.get("model_id") == f.model_id
                for c in self.model_calls
            ):
                continue
            if f.tool_id is not None and not any(
                c["session_id"] == s["id"] and c.get("tool_id") == f.tool_id
                for c in self.tool_calls
            ):
                continue
            kept.append(s)
        return kept

    def _calls_of(self, items: list[dict[str, Any]], ids: set[int]) -> list[dict[str, Any]]:
        return [c for c in items if c["session_id"] in ids]

    # -- queries -----------------------------------------------------------

    async def overview(self, filters: DashboardFilters) -> OverviewTotals:
        sessions = self._matching_sessions(filters)
        ids = {s["id"] for s in sessions}
        mcalls = self._calls_of(self.model_calls, ids)
        tcalls = self._calls_of(self.tool_calls, ids)

        per_session_tokens: list[float] = []
        sessions_with_tokens = 0
        for s in sessions:
            own = [c for c in mcalls if c["session_id"] == s["id"]]
            known = [c for c in own if c.get("input_tokens") is not None]
            if known:
                sessions_with_tokens += 1
            # One value per SESSION, not per call: the registry defines the
            # metric as AVG(SUM(input + output) GROUP BY session). Averaging
            # per call would weight a session with many small calls the same
            # as one with a few large ones.
            session_input = _total([c.get("input_tokens") for c in own])
            session_output = _total([c.get("output_tokens") for c in own])
            # SQL propagates NULL through the addition: if either side is
            # entirely unknown the session drops out of the average.
            if session_input is not None and session_output is not None:
                per_session_tokens.append(float(session_input + session_output))

        durations = [float(s["duration_ms"]) for s in sessions if s.get("duration_ms") is not None]

        return OverviewTotals(
            session_count=len(sessions),
            model_call_count=len(mcalls),
            tool_call_count=len(tcalls),
            total_input_tokens=_total([c.get("input_tokens") for c in mcalls]),
            total_output_tokens=_total([c.get("output_tokens") for c in mcalls]),
            token_coverage=Coverage(sessions_with_tokens, len(sessions)),
            avg_tokens_per_session=_mean(per_session_tokens),
            avg_session_duration_ms=_mean(durations),
            duration_coverage=Coverage(len(durations), len(sessions)),
            tool_error_count=sum(1 for c in tcalls if c.get("status") == "error"),
            tool_status_known_count=sum(1 for c in tcalls if c.get("status") in ("ok", "error")),
        )

    async def activity(self, filters: DashboardFilters) -> list[ActivityPoint]:
        sessions = [s for s in self._matching_sessions(filters) if s.get("started_at")]
        buckets: dict[tuple[date, int], list[dict[str, Any]]] = defaultdict(list)
        for s in sessions:
            buckets[(s["started_at"].date(), s["data_source_id"])].append(s)

        points = []
        for (day, source), group in sorted(buckets.items()):
            ids = {s["id"] for s in group}
            mcalls = self._calls_of(self.model_calls, ids)
            tcalls = self._calls_of(self.tool_calls, ids)
            points.append(
                ActivityPoint(
                    day=day,
                    data_source_id=source,
                    session_count=len(group),
                    model_call_count=len(mcalls),
                    tool_call_count=len(tcalls),
                    input_tokens=_total([c.get("input_tokens") for c in mcalls]),
                    output_tokens=_total([c.get("output_tokens") for c in mcalls]),
                    token_coverage=Coverage(
                        sum(1 for c in mcalls if c.get("input_tokens") is not None), len(mcalls)
                    ),
                )
            )
        return points

    async def tool_usage(self, filters: DashboardFilters) -> list[ToolUsagePoint]:
        sources = {s["data_source_id"] for s in self._matching_sessions(filters)}
        by_session = {s["id"]: s for s in self.sessions}

        buckets: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for c in self.tool_calls:
            session = by_session.get(c["session_id"])
            if session is None or session["data_source_id"] not in sources:
                continue
            buckets[(c["tool_id"], session["data_source_id"])].append(c)

        points = [
            ToolUsagePoint(
                tool_id=tool_id,
                tool_name=calls[0]["tool_name"],
                data_source_id=source,
                call_count=len(calls),
                error_count=sum(1 for c in calls if c.get("status") == "error"),
                status_known_count=sum(1 for c in calls if c.get("status") in ("ok", "error")),
            )
            for (tool_id, source), calls in buckets.items()
        ]
        return sorted(points, key=lambda p: (-p.call_count, p.tool_name))

    async def model_usage(self, filters: DashboardFilters) -> list[ModelUsagePoint]:
        sources = {s["data_source_id"] for s in self._matching_sessions(filters)}
        by_session = {s["id"]: s for s in self.sessions}

        buckets: dict[tuple[int | None, int], list[dict[str, Any]]] = defaultdict(list)
        for c in self.model_calls:
            session = by_session.get(c["session_id"])
            if session is None or session["data_source_id"] not in sources:
                continue
            buckets[(c.get("model_id"), session["data_source_id"])].append(c)

        points = [
            ModelUsagePoint(
                model_id=model_id,
                model_name=calls[0].get("model_name"),
                provider_name=calls[0].get("provider_name"),
                data_source_id=source,
                call_count=len(calls),
                input_tokens=_total([c.get("input_tokens") for c in calls]),
                output_tokens=_total([c.get("output_tokens") for c in calls]),
                token_coverage=Coverage(
                    sum(1 for c in calls if c.get("input_tokens") is not None), len(calls)
                ),
                cache_read_tokens=_total([c.get("cache_read_tokens") for c in calls]),
                cache_coverage=Coverage(
                    sum(1 for c in calls if c.get("cache_read_tokens") is not None), len(calls)
                ),
            )
            for (model_id, source), calls in buckets.items()
        ]
        return sorted(points, key=lambda p: (-p.call_count, p.model_name or ""))

    async def import_quality(self, filters: DashboardFilters) -> list[ImportQualityPoint]:
        runs = self.import_runs
        if filters.data_source_id is not None:
            runs = [r for r in runs if r["data_source_id"] == filters.data_source_id]
        if filters.import_run_id is not None:
            runs = [r for r in runs if r["id"] == filters.import_run_id]

        return [
            ImportQualityPoint(
                import_run_id=r["id"],
                data_source_id=r["data_source_id"],
                status=r["status"],
                records_read=r["records_read"],
                records_imported=r["records_imported"],
                records_duplicate=r["records_duplicate"],
                records_rejected=r["records_rejected"],
                issue_count=sum(1 for i in self.import_issues if i["import_run_id"] == r["id"]),
                fields_missing=dict(r.get("fields_missing") or {}),
            )
            for r in sorted(runs, key=lambda r: r["id"], reverse=True)
        ]
