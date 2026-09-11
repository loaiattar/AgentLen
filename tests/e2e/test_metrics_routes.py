"""GET /metrics/definitions and GET /metrics/overview.

Most of these run with the read side swapped for the in-memory double through
`dependency_overrides` — which is also the proof that the DI wiring from #42 is
genuinely overridable. Two tests hit a real Postgres, to check the SQL path and
the route agree.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.dependencies import get_dashboard_queries
from agentlen.interfaces.http.routers.metrics import CACHE_CROSS_SOURCE_WARNING
from tests.e2e.conftest import UNREACHABLE_URL, asgi_client
from tests.fakes.dashboard_queries import InMemoryDashboardQueries
from tests.integration.conftest import requires_postgres

DAY = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)

SESSIONS = [
    {"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 4000},
    {"id": 2, "data_source_id": 1, "started_at": DAY, "duration_ms": None},
]
MODEL_CALLS = [
    {"session_id": 1, "input_tokens": 100, "output_tokens": 20},
    {"session_id": 2, "input_tokens": None, "output_tokens": None},
]
TOOL_CALLS = [
    {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "ok"},
    {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "error"},
    {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "unknown"},
]


@pytest.fixture
async def stub_client() -> AsyncIterator[AsyncClient]:
    """An app whose read side is the in-memory double."""
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_dashboard_queries] = lambda: InMemoryDashboardQueries(
        sessions=list(SESSIONS), model_calls=list(MODEL_CALLS), tool_calls=list(TOOL_CALLS)
    )
    async with asgi_client(app) as c:
        yield c


def by_key(body):  # type: ignore[no-untyped-def]
    return {m["key"]: m for m in body["metrics"]}


# ---------------------------------------------------------------------------
# Definitions — served from the registry, no database involved
# ---------------------------------------------------------------------------


async def test_definitions_needs_no_database(client: AsyncClient) -> None:
    """`client` has an unreachable engine on purpose: an indicator's definition
    is a product decision, not a query result, so the front can render the
    "how is this computed?" affordance before anything is imported."""
    response = await client.get("/api/v1/metrics/definitions")

    assert response.status_code == 200
    keys = {d["key"] for d in response.json()["definitions"]}
    # At least the headline four; the chart routes add their own definitions.
    assert {
        "session_count",
        "avg_tokens_per_session",
        "avg_session_duration_ms",
        "tool_error_rate",
    } <= keys


async def test_every_definition_is_readable(client: AsyncClient) -> None:
    for definition in (await client.get("/api/v1/metrics/definitions")).json()["definitions"]:
        assert definition["missing_policy"].strip()
        assert definition["formula"].strip()
        assert definition["comparability"] in ("cross_source", "per_source_only")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


async def test_overview_returns_the_four_indicators_with_coverage(
    stub_client: AsyncClient,
) -> None:
    response = await stub_client.get("/api/v1/metrics/overview")

    assert response.status_code == 200
    metrics = by_key(response.json())
    assert set(metrics) == {
        "session_count",
        "avg_tokens_per_session",
        "avg_session_duration_ms",
        "tool_error_rate",
    }
    for metric in metrics.values():
        assert set(metric["coverage"]) == {"present", "total", "ratio"}


async def test_missing_data_is_null_with_partial_coverage_never_zero(
    stub_client: AsyncClient,
) -> None:
    """The rule the whole project turns on, at the API boundary."""
    metrics = by_key((await stub_client.get("/api/v1/metrics/overview")).json())

    # Session 2 has no tokens and no duration: excluded, not averaged in as 0.
    assert metrics["avg_tokens_per_session"]["value"] == 120
    assert metrics["avg_tokens_per_session"]["coverage"]["ratio"] == 0.5
    assert metrics["avg_session_duration_ms"]["value"] == 4000
    assert metrics["avg_session_duration_ms"]["coverage"]["ratio"] == 0.5

    # The 'unknown' tool call is out of the denominator: 1/2, not 1/3.
    assert metrics["tool_error_rate"]["value"] == 0.5
    assert metrics["tool_error_rate"]["coverage"]["present"] == 2
    assert metrics["tool_error_rate"]["coverage"]["total"] == 3


async def test_empty_scope_has_null_coverage_ratios() -> None:
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_dashboard_queries] = lambda: InMemoryDashboardQueries()
    async with asgi_client(app) as client:
        response = await client.get("/api/v1/metrics/overview")

    assert response.status_code == 200
    metrics = by_key(response.json())
    assert all(metric["coverage"]["ratio"] is None for metric in metrics.values())


def _models_app(*, cache_by_source: dict[int, bool]):  # type: ignore[no-untyped-def]
    """One session and one model call per source, cache reported or not."""
    sessions = [
        {"id": source, "data_source_id": source, "started_at": DAY, "duration_ms": 1000}
        for source in cache_by_source
    ]
    calls = [
        {
            "session_id": source,
            "model_id": source,
            "model_name": f"m{source}",
            "provider_name": f"p{source}",
            "input_tokens": 10,
            "output_tokens": 1,
            "cache_read_tokens": 5 if has_cache else None,
        }
        for source, has_cache in cache_by_source.items()
    ]
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_dashboard_queries] = lambda: InMemoryDashboardQueries(
        sessions=sessions, model_calls=calls, tool_calls=[]
    )
    return app


async def test_cache_warning_fires_when_the_sources_disagree() -> None:
    """The case the warning exists for: one source reports cache, another does not.

    A total spanning both then means "the sources that bothered", not "all of
    them", and the front has to say so rather than let the number stand alone.
    """
    async with asgi_client(_models_app(cache_by_source={1: True, 2: False})) as client:
        body = (await client.get("/api/v1/metrics/models")).json()

    assert body["warnings"] == [CACHE_CROSS_SOURCE_WARNING]


async def test_cache_warning_stays_silent_when_every_source_reports_cache() -> None:
    """The bug this pins.

    The condition tested "at least one source has cache", so a scope where every
    source reported cache at full coverage was still told the figures were
    incomparable — which is false, and sends the reader filtering by source for
    nothing. What makes them incomparable is the sources *disagreeing*.
    """
    async with asgi_client(_models_app(cache_by_source={1: True, 2: True})) as client:
        body = (await client.get("/api/v1/metrics/models")).json()

    assert body["points"], "les deux sources doivent produire un point"
    assert all(p["coverage"]["present"] > 0 for p in body["points"])
    assert body["warnings"] == []


async def test_cache_warning_stays_silent_when_no_source_reports_cache() -> None:
    """Nothing to compare is not the same thing as something incomparable."""
    async with asgi_client(_models_app(cache_by_source={1: False, 2: False})) as client:
        body = (await client.get("/api/v1/metrics/models")).json()

    assert body["warnings"] == []


async def test_cache_warning_stays_silent_on_a_single_source() -> None:
    """One source is always comparable with itself."""
    async with asgi_client(_models_app(cache_by_source={1: True})) as client:
        body = (await client.get("/api/v1/metrics/models")).json()

    assert body["warnings"] == []


async def test_filters_are_echoed_for_drill_down(stub_client: AsyncClient) -> None:
    """API.md §6: the echoed filters must be replayable on GET /sessions."""
    body = (await stub_client.get("/api/v1/metrics/overview?data_source_id=1")).json()

    assert body["filters_applied"] == {"data_source_id": 1}


async def test_unknown_filter_value_is_rejected_with_the_envelope(
    stub_client: AsyncClient,
) -> None:
    response = await stub_client.get("/api/v1/metrics/overview?data_source_id=abc")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_REQUEST"


# ---------------------------------------------------------------------------
# Against a real database
# ---------------------------------------------------------------------------


@requires_postgres
async def test_overview_against_an_empty_database(live_client: AsyncClient) -> None:
    """An empty database is not an error: zero sessions, and averages that are
    unavailable rather than zero."""
    response = await live_client.get("/api/v1/metrics/overview")

    assert response.status_code == 200
    metrics = by_key(response.json())
    assert metrics["session_count"]["value"] == 0
    assert metrics["avg_tokens_per_session"]["value"] is None
    assert metrics["avg_session_duration_ms"]["value"] is None
    assert metrics["tool_error_rate"]["value"] is None


@requires_postgres
async def test_overview_accepts_every_documented_filter(live_client: AsyncClient) -> None:
    """The filter names must match those of GET /sessions, or the drill-down
    contract silently stops narrowing."""
    query = (
        "data_source_id=1&agent_id=1&model_id=1&tool_id=1&import_run_id=1"
        "&date_from=2026-01-01T00:00:00Z&date_to=2026-12-31T00:00:00Z"
    )
    response = await live_client.get(f"/api/v1/metrics/overview?{query}")

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
