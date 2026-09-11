"""The four chart routes and, above all, the drill-down contract.

Every point must carry filters that, replayed, select exactly the rows behind
it. `GET /sessions` does not exist yet (#59), so the replay is verified through
the same port the session list will use — which is what actually proves the
filter names and values select the right subset.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.dto.dashboard import DashboardFilters
from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.dependencies import get_dashboard_queries
from agentlen.interfaces.http.routers.metrics import UNDATED_SESSIONS_WARNING
from tests.e2e.conftest import UNREACHABLE_URL, asgi_client
from tests.fakes.dashboard_queries import InMemoryDashboardQueries

DAY_1 = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
DAY_2 = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)

# Two sources on purpose: source 1 reports cache figures, source 2 never does.
SESSIONS = [
    {"id": 1, "data_source_id": 1, "import_run_id": 10, "started_at": DAY_1, "duration_ms": 100},
    {"id": 2, "data_source_id": 1, "import_run_id": 10, "started_at": DAY_2, "duration_ms": 200},
    {"id": 3, "data_source_id": 2, "import_run_id": 20, "started_at": DAY_2, "duration_ms": 300},
]
MODEL_CALLS = [
    {
        "session_id": 1,
        "model_id": 1,
        "model_name": "m1",
        "provider_name": "anthropic",
        "input_tokens": 100,
        "output_tokens": 10,
        "cache_read_tokens": 5,
    },
    {
        "session_id": 2,
        "model_id": 1,
        "model_name": "m1",
        "provider_name": "anthropic",
        "input_tokens": 200,
        "output_tokens": 20,
        "cache_read_tokens": 7,
    },
    {
        "session_id": 3,
        "model_id": 2,
        "model_name": "m2",
        "provider_name": "openai",
        "input_tokens": 300,
        "output_tokens": 30,
        "cache_read_tokens": None,
    },
]
TOOL_CALLS = [
    {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "ok"},
    {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "error"},
    {"session_id": 2, "tool_id": 1, "tool_name": "Bash", "status": "unknown"},
    {"session_id": 3, "tool_id": 2, "tool_name": "Read", "status": "ok"},
]
IMPORT_RUNS = [
    {
        "id": 10,
        "data_source_id": 1,
        "status": "partial",
        "records_read": 100,
        "records_imported": 90,
        "records_duplicate": 7,
        "records_rejected": 3,
        "fields_missing": {"model_call.cache_read_tokens": 4},
    },
    {
        "id": 20,
        "data_source_id": 2,
        "status": "succeeded",
        "records_read": 0,
        "records_imported": 0,
        "records_duplicate": 0,
        "records_rejected": 0,
        "fields_missing": {},
    },
]


def reference() -> InMemoryDashboardQueries:
    return InMemoryDashboardQueries(
        sessions=list(SESSIONS),
        model_calls=list(MODEL_CALLS),
        tool_calls=list(TOOL_CALLS),
        import_runs=list(IMPORT_RUNS),
    )


@pytest.fixture
async def charts() -> AsyncIterator[AsyncClient]:
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_dashboard_queries] = reference
    async with asgi_client(app) as c:
        yield c


ROUTES = ["activity", "tools", "models", "quality"]


# ---------------------------------------------------------------------------
# The drill-down contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("route", ROUTES)
async def test_every_point_carries_non_empty_filters(charts: AsyncClient, route: str) -> None:
    body = (await charts.get(f"/api/v1/metrics/{route}")).json()

    assert body["points"], f"/{route} returned no points"
    for point in body["points"]:
        assert point["filters"], f"a point of /{route} has no drill-down filters"


async def test_tool_point_filters_select_exactly_that_point(charts: AsyncClient) -> None:
    """Replaying a point's filters must return the sessions behind it.

    `GET /sessions` lands in #59, so the replay goes through the same port that
    endpoint will use. What is being checked is the part that can actually be
    wrong: that the names and values narrow to the right subset.
    """
    points = (await charts.get("/api/v1/metrics/tools")).json()["points"]
    bash = next(p for p in points if p["label"] == "Bash")

    assert bash["filters"] == {"tool_id": 1, "data_source_id": 1}

    replayed = await reference().overview(DashboardFilters(**bash["filters"]))
    # Sessions 1 and 2 used Bash and belong to source 1; session 3 used Read.
    assert replayed.session_count == 2
    assert replayed.tool_call_count == 3
    assert replayed.tool_error_count == bash["error_count"]


async def test_activity_point_filters_bound_the_day(charts: AsyncClient) -> None:
    """A daily point is a date, but the session list filters on instants — so
    the point carries the interval, not the date."""
    points = (await charts.get("/api/v1/metrics/activity")).json()["points"]
    first = points[0]

    assert first["filters"]["date_from"].startswith(first["day"])
    replayed = await reference().overview(
        DashboardFilters(
            data_source_id=first["filters"]["data_source_id"],
            date_from=datetime.fromisoformat(first["filters"]["date_from"]),
            date_to=datetime.fromisoformat(first["filters"]["date_to"]),
        )
    )
    assert replayed.session_count == first["session_count"]


async def test_active_filters_are_carried_into_every_point(charts: AsyncClient) -> None:
    """A point clicked on a filtered chart must stay filtered when replayed."""
    body = (await charts.get("/api/v1/metrics/tools?data_source_id=1")).json()

    assert body["filters_applied"] == {"data_source_id": 1}
    for point in body["points"]:
        assert point["filters"]["data_source_id"] == 1


# ---------------------------------------------------------------------------
# Comparability
# ---------------------------------------------------------------------------


async def test_cache_across_sources_produces_a_warning(charts: AsyncClient) -> None:
    """`cache_read_tokens` is per_source_only: source 2 never reports it, so a
    figure spanning both sources means "the sources that bothered"."""
    body = (await charts.get("/api/v1/metrics/models")).json()

    assert body["warnings"], "aggregating cache across sources produced no warning"
    assert "cache" in body["warnings"][0].lower()


async def test_no_warning_once_a_single_source_is_selected(charts: AsyncClient) -> None:
    body = (await charts.get("/api/v1/metrics/models?data_source_id=1")).json()

    assert body["warnings"] == []


# ---------------------------------------------------------------------------
# Sessions the activity series cannot place (#200)
# ---------------------------------------------------------------------------


async def _activity(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_dashboard_queries] = lambda: InMemoryDashboardQueries(
        sessions=sessions
    )
    async with asgi_client(app) as c:
        body: dict[str, Any] = (await c.get("/api/v1/metrics/activity")).json()
    return body


def _session_started(session_id: int, started_at: datetime | None) -> dict[str, Any]:
    return {"id": session_id, "data_source_id": 1, "import_run_id": 10, "started_at": started_at}


async def test_activity_says_so_when_no_session_has_a_date() -> None:
    """An empty series over undated sessions is not "no activity"."""
    body = await _activity([_session_started(1, None), _session_started(2, None)])

    assert body["points"] == []
    assert body["warnings"] == [UNDATED_SESSIONS_WARNING.format(undated=2, total=2)]


async def test_activity_counts_the_undated_sessions_it_leaves_out() -> None:
    body = await _activity([_session_started(1, DAY_1), _session_started(2, None)])

    assert [p["session_count"] for p in body["points"]] == [1]
    assert body["warnings"] == [UNDATED_SESSIONS_WARNING.format(undated=1, total=2)]


async def test_activity_has_no_warning_when_every_session_is_dated(charts: AsyncClient) -> None:
    body = (await charts.get("/api/v1/metrics/activity")).json()

    assert body["points"]
    assert body["warnings"] == []


async def test_activity_has_no_warning_when_there_is_nothing_to_date() -> None:
    body = await _activity([])

    assert body["points"] == []
    assert body["warnings"] == []


async def test_source_without_cache_reports_null_not_zero(charts: AsyncClient) -> None:
    body = (await charts.get("/api/v1/metrics/models?data_source_id=2")).json()
    point = body["points"][0]

    assert point["cache_read_tokens"] is None
    assert point["cache_coverage"]["ratio"] == 0.0
    # The tokens it *does* report are unaffected.
    assert point["input_tokens"] == 300


# ---------------------------------------------------------------------------
# Values, against the reference
# ---------------------------------------------------------------------------


async def test_tool_error_ratio_excludes_unknown_status(charts: AsyncClient) -> None:
    points = (await charts.get("/api/v1/metrics/tools")).json()["points"]
    bash = next(p for p in points if p["label"] == "Bash")

    # 3 Bash calls, one of them 'unknown': 1 error over 2 known, not 1/3.
    assert bash["call_count"] == 3
    assert bash["error_ratio"] == 0.5
    assert bash["coverage"] == {"present": 2, "total": 3, "ratio": 2 / 3}


async def test_quality_reports_null_ratio_on_an_empty_import(charts: AsyncClient) -> None:
    """A rejection ratio over zero records read is undefined, not 0."""
    points = (await charts.get("/api/v1/metrics/quality")).json()["points"]
    empty = next(p for p in points if p["import_run_id"] == 20)

    assert empty["records_read"] == 0
    assert empty["rejection_ratio"] is None


async def test_quality_surfaces_missing_fields(charts: AsyncClient) -> None:
    points = (await charts.get("/api/v1/metrics/quality")).json()["points"]
    partial = next(p for p in points if p["import_run_id"] == 10)

    assert partial["rejection_ratio"] == 0.03
    assert partial["fields_missing"] == {"model_call.cache_read_tokens": 4}


@pytest.mark.parametrize("route", ROUTES)
async def test_every_route_accepts_the_documented_filter_set(
    charts: AsyncClient, route: str
) -> None:
    """The same seven filters as GET /sessions, or the drill-down breaks."""
    query = (
        "data_source_id=1&agent_id=1&model_id=1&tool_id=1&import_run_id=10"
        "&date_from=2026-01-01T00:00:00Z&date_to=2026-12-31T00:00:00Z"
    )
    response = await charts.get(f"/api/v1/metrics/{route}?{query}")

    assert response.status_code == 200
    assert set(response.json()["filters_applied"]) == {
        "data_source_id",
        "agent_id",
        "model_id",
        "tool_id",
        "import_run_id",
        "date_from",
        "date_to",
    }


async def test_definitions_document_the_chart_indicators_too(charts: AsyncClient) -> None:
    """Every number the API returns must be findable in /metrics/definitions."""
    keys = {
        d["key"] for d in (await charts.get("/api/v1/metrics/definitions")).json()["definitions"]
    }

    assert {"cache_read_tokens", "import_rejection_ratio"} <= keys


async def test_overview_still_returns_exactly_four(charts: AsyncClient) -> None:
    """Documenting a chart figure must not add a fifth tile to the header."""
    body = (await charts.get("/api/v1/metrics/overview")).json()

    assert len(body["metrics"]) == 4
