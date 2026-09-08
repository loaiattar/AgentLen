"""The four indicators and their missing-value policies.

No database: the rules being checked here are product decisions, not SQL. If
one of them needed Postgres to be tested, that would be a sign the definition
had leaked into the query.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentlen.application.dto.dashboard import DashboardFilters
from agentlen.application.use_cases.query_dashboard import (
    QueryDashboardOverview,
    QueryMetricDefinitions,
)
from agentlen.domain.services import metric_registry
from tests.fakes.dashboard_queries import InMemoryDashboardQueries

DAY = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
ALL = DashboardFilters()


def build(sessions, model_calls=(), tool_calls=()):  # type: ignore[no-untyped-def]
    return QueryDashboardOverview(
        InMemoryDashboardQueries(
            sessions=list(sessions),
            model_calls=list(model_calls),
            tool_calls=list(tool_calls),
        )
    )


def by_key(metrics):  # type: ignore[no-untyped-def]
    return {m.key: m for m in metrics}


async def test_returns_exactly_the_registered_indicators() -> None:
    """Four is the brief's minimum; the registry is the single source of truth."""
    metrics = await build([]).execute(ALL)

    assert [m.key for m in metrics] == [d.key for d in metric_registry.all_definitions()]
    assert len(metrics) == 4


async def test_registry_is_fully_mapped() -> None:
    """Adding a definition without a mapping must fail loudly, not silently
    produce an indicator that is always null."""
    sessions = [{"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 10}]
    metrics = by_key(await build(sessions).execute(ALL))

    for definition in metric_registry.all_definitions():
        assert definition.key in metrics
        assert metrics[definition.key].unit == definition.unit


# ---------------------------------------------------------------------------
# The three rules the issue calls out
# ---------------------------------------------------------------------------


async def test_session_without_tokens_is_excluded_not_counted_as_zero() -> None:
    sessions = [
        {"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 100},
        {"id": 2, "data_source_id": 1, "started_at": DAY, "duration_ms": 100},
    ]
    calls = [
        {"session_id": 1, "input_tokens": 100, "output_tokens": 20},
        {"session_id": 2, "input_tokens": None, "output_tokens": None},
    ]
    tokens = by_key(await build(sessions, calls).execute(ALL))["avg_tokens_per_session"]

    # 120 from session 1 alone. Averaging in session 2 as 0 would give 60.
    assert tokens.value == 120
    assert tokens.coverage.present == 1
    assert tokens.coverage.total == 2
    assert tokens.coverage.ratio == 0.5


async def test_session_without_duration_is_excluded_not_counted_as_zero_ms() -> None:
    sessions = [
        {"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 4000},
        {"id": 2, "data_source_id": 1, "started_at": DAY, "duration_ms": None},
    ]
    duration = by_key(await build(sessions).execute(ALL))["avg_session_duration_ms"]

    # 4000, not 2000.
    assert duration.value == 4000
    assert duration.coverage.ratio == 0.5


async def test_unknown_tool_status_does_not_affect_the_error_rate() -> None:
    sessions = [{"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 1}]
    calls = [
        {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "ok"},
        {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "error"},
        {"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "unknown"},
    ]
    rate = by_key(await build(sessions, tool_calls=calls).execute(ALL))["tool_error_rate"]

    # 1 error over 2 calls with a known status — not 1/3.
    assert rate.value == 0.5
    assert rate.coverage.present == 2
    assert rate.coverage.total == 3


# ---------------------------------------------------------------------------
# Absent is not zero, at the edges
# ---------------------------------------------------------------------------


async def test_no_data_at_all_yields_null_averages_not_zero() -> None:
    metrics = by_key(await build([]).execute(ALL))

    assert metrics["session_count"].value == 0  # a count really is zero
    assert metrics["avg_tokens_per_session"].value is None
    assert metrics["avg_session_duration_ms"].value is None
    assert metrics["tool_error_rate"].value is None


async def test_tool_error_rate_is_null_when_no_status_is_known() -> None:
    """Not 0.0 — "no errors observed" and "no outcome reported" are different
    claims, and only one of them is good news."""
    sessions = [{"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 1}]
    calls = [{"session_id": 1, "tool_id": 1, "tool_name": "Bash", "status": "unknown"}]
    rate = by_key(await build(sessions, tool_calls=calls).execute(ALL))["tool_error_rate"]

    assert rate.value is None
    assert rate.coverage.ratio == 0.0


async def test_session_count_is_always_fully_covered() -> None:
    sessions = [
        {"id": i, "data_source_id": 1, "started_at": DAY, "duration_ms": None} for i in range(3)
    ]
    count = by_key(await build(sessions).execute(ALL))["session_count"]

    assert count.value == 3
    assert count.coverage.ratio == 1.0


async def test_filters_narrow_the_scope() -> None:
    sessions = [
        {"id": 1, "data_source_id": 1, "started_at": DAY, "duration_ms": 10},
        {"id": 2, "data_source_id": 2, "started_at": DAY, "duration_ms": 20},
    ]
    metrics = by_key(await build(sessions).execute(DashboardFilters(data_source_id=2)))

    assert metrics["session_count"].value == 1
    assert metrics["avg_session_duration_ms"].value == 20


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------


def test_every_definition_states_its_missing_value_policy() -> None:
    """The "definition accessible" requirement: a reader must be able to see
    what the number does when the data is absent."""
    for definition in QueryMetricDefinitions.execute():
        assert definition.missing_policy.strip()
        assert definition.formula.strip()
        assert definition.scope.strip()
        assert definition.comparability in ("cross_source", "per_source_only")


@pytest.mark.parametrize(
    "key", ["session_count", "avg_tokens_per_session", "avg_session_duration_ms", "tool_error_rate"]
)
def test_the_four_required_indicators_are_registered(key: str) -> None:
    assert metric_registry.get(key).key == key
