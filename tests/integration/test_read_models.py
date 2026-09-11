"""The SQL views must agree with an independently written reference.

The dataset below is small and deliberately awkward: a session whose token data
is entirely absent, a session with no duration, a source with no cache metrics,
and — the case that matters most — a session with both model calls and tool
calls, which is what makes a naive join over-count.

Every assertion compares the SQL views against `InMemoryDashboardQueries`,
written from DATA_MODEL.md rather than from the view definitions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agentlen.application.dto.dashboard import DashboardFilters
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.read_models import SqlDashboardQueries
from tests.fakes.dashboard_queries import InMemoryDashboardQueries
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres

DAY_1 = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
DAY_2 = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


@pytest.fixture
def dataset(clean_db):  # type: ignore[no-untyped-def]
    """A controlled fixture, mirrored into the in-memory reference."""
    conn = clean_db
    ref = InMemoryDashboardQueries()

    sources = {}
    for slug in ("tracelab", "swe-chat"):
        sources[slug] = conn.execute(
            insert(t.data_source).values(slug=slug, name=slug).returning(t.data_source.c.id)
        ).scalar_one()

    file_id = conn.execute(
        insert(t.file_upload)
        .values(
            original_name="s.jsonl",
            storage_path="/srv/s.jsonl",
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        .returning(t.file_upload.c.id)
    ).scalar_one()
    mapping_id = conn.execute(
        insert(t.mapping)
        .values(
            data_source_id=sources["tracelab"],
            name="m",
            version=1,
            source_format="jsonl",
            document={},
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()

    runs = {}
    for slug in ("tracelab", "swe-chat"):
        run_id = conn.execute(
            insert(t.import_run)
            .values(
                data_source_id=sources[slug],
                file_upload_id=file_id,
                mapping_id=mapping_id,
                status="partial",
                records_read=100,
                records_imported=90,
                records_duplicate=7,
                records_rejected=3,
                fields_missing={"model_call.cache_read_tokens": 100},
            )
            .returning(t.import_run.c.id)
        ).scalar_one()
        runs[slug] = run_id
        ref.import_runs.append(
            {
                "id": run_id,
                "data_source_id": sources[slug],
                "status": "partial",
                "records_read": 100,
                "records_imported": 90,
                "records_duplicate": 7,
                "records_rejected": 3,
                "fields_missing": {"model_call.cache_read_tokens": 100},
            }
        )

    record_id = conn.execute(
        insert(t.raw_record)
        .values(
            import_run_id=runs["tracelab"],
            line_number=1,
            payload={},
            content_hash="b" * 64,
        )
        .returning(t.raw_record.c.id)
    ).scalar_one()

    agent_id = conn.execute(
        insert(t.agent).values(name="claude-code", version="1").returning(t.agent.c.id)
    ).scalar_one()
    provider_id = conn.execute(
        insert(t.provider).values(name="anthropic").returning(t.provider.c.id)
    ).scalar_one()
    model_id = conn.execute(
        insert(t.model).values(provider_id=provider_id, name="model-x").returning(t.model.c.id)
    ).scalar_one()
    tool_ids = {
        name: conn.execute(insert(t.tool).values(name=name).returning(t.tool.c.id)).scalar_one()
        for name in ("Bash", "Read")
    }

    def add_session(slug, external, started, duration):  # type: ignore[no-untyped-def]
        sid = conn.execute(
            insert(t.session)
            .values(
                data_source_id=sources[slug],
                import_run_id=runs[slug],
                raw_record_id=record_id,
                external_id=external,
                agent_id=agent_id,
                started_at=started,
                duration_ms=duration,
            )
            .returning(t.session.c.id)
        ).scalar_one()
        ref.sessions.append(
            {
                "id": sid,
                "data_source_id": sources[slug],
                "import_run_id": runs[slug],
                "agent_id": agent_id,
                "started_at": started,
                "duration_ms": duration,
            }
        )
        return sid

    def add_model_call(sid, idx, inp, out, cache):  # type: ignore[no-untyped-def]
        conn.execute(
            insert(t.model_call).values(
                session_id=sid,
                raw_record_id=record_id,
                model_id=model_id,
                sequence_index=idx,
                input_tokens=inp,
                output_tokens=out,
                cache_read_tokens=cache,
                status="ok",
            )
        )
        ref.model_calls.append(
            {
                "session_id": sid,
                "model_id": model_id,
                "model_name": "model-x",
                "provider_name": "anthropic",
                "input_tokens": inp,
                "output_tokens": out,
                "cache_read_tokens": cache,
            }
        )

    def add_tool_call(sid, idx, name, status):  # type: ignore[no-untyped-def]
        conn.execute(
            insert(t.tool_call).values(
                session_id=sid,
                raw_record_id=record_id,
                tool_id=tool_ids[name],
                sequence_index=idx,
                status=status,
            )
        )
        ref.tool_calls.append(
            {
                "session_id": sid,
                "tool_id": tool_ids[name],
                "tool_name": name,
                "status": status,
            }
        )

    # A — the fan-out shape: 3 model calls AND 5 tool calls on one session.
    a = add_session("tracelab", "a", DAY_1, 5_000)
    for i, (inp, out) in enumerate([(100, 10), (200, 20), (300, 30)]):
        add_model_call(a, i, inp, out, cache=5)
    for i, status in enumerate(["ok", "ok", "error", "unknown", "ok"]):
        add_tool_call(a, i, "Bash" if i % 2 == 0 else "Read", status)

    # B — token data entirely absent: must be excluded, never counted as zero.
    b = add_session("tracelab", "b", DAY_1, 7_000)
    add_model_call(b, 0, None, None, cache=None)

    # C — no duration: excluded from the duration average.
    c = add_session("tracelab", "c", DAY_2, None)
    add_model_call(c, 0, 50, 5, cache=None)

    # D — a second source, with no cache metrics at all.
    d = add_session("swe-chat", "d", DAY_2, 1_000)
    add_model_call(d, 0, 40, 4, cache=None)
    add_tool_call(d, 0, "Bash", "ok")

    conn.commit()
    return ref, sources


@pytest.fixture
async def sql_queries(database_url: str) -> AsyncEngine:  # type: ignore[misc]
    engine = create_async_engine(to_async_url(database_url))
    yield SqlDashboardQueries(engine)
    await engine.dispose()


ALL = DashboardFilters()


async def test_overview_matches_the_reference(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    ref, _ = dataset
    assert await sql_queries.overview(ALL) == await ref.overview(ALL)


async def test_token_totals_are_not_inflated_by_tool_calls(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    """The regression guard for DATA_MODEL.md §7's join.

    Session A has 3 model calls (600 input tokens) and 5 tool calls. Joining
    both children in one query would report 3000.
    """
    ref, _ = dataset
    got = await sql_queries.overview(ALL)

    assert got.total_input_tokens == 100 + 200 + 300 + 50 + 40
    assert got.total_input_tokens == (await ref.overview(ALL)).total_input_tokens


async def test_a_session_without_tokens_is_excluded_never_zero(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    ref, sources = dataset
    f = DashboardFilters(data_source_id=sources["tracelab"])
    got = await sql_queries.overview(f)

    assert got.token_coverage.total == 3  # A, B, C
    assert got.token_coverage.present == 2  # B contributed nothing
    assert got.token_coverage.ratio < 1.0
    assert got == await ref.overview(f)


async def test_a_session_without_duration_is_excluded_never_zero(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    ref, sources = dataset
    f = DashboardFilters(data_source_id=sources["tracelab"])
    got = await sql_queries.overview(f)

    assert got.avg_session_duration_ms == 6_000.0  # (5000 + 7000) / 2, C excluded
    assert got.duration_coverage.present == 2
    assert got.duration_coverage.total == 3
    assert got == await ref.overview(f)


async def test_unknown_tool_status_leaves_the_denominator(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    ref, sources = dataset
    f = DashboardFilters(data_source_id=sources["tracelab"])
    got = await sql_queries.overview(f)

    assert got.tool_call_count == 5
    assert got.tool_status_known_count == 4  # the 'unknown' call is out
    assert got.tool_error_rate == 1 / 4  # not 1/5
    assert got == await ref.overview(f)


async def test_a_source_without_cache_metrics_reports_null_not_zero(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    """`per_source_only` in practice: swe-chat has no cache data at all."""
    ref, sources = dataset
    f = DashboardFilters(data_source_id=sources["swe-chat"])
    points = await sql_queries.model_usage(f)

    assert len(points) == 1
    assert points[0].cache_read_tokens is None
    assert points[0].cache_coverage.ratio == 0.0
    assert points == await ref.model_usage(f)


@pytest.mark.parametrize("query", ["activity", "tool_usage", "model_usage", "import_quality"])
async def test_every_view_matches_the_reference(dataset, sql_queries, query) -> None:  # type: ignore[no-untyped-def]
    ref, _ = dataset
    assert await getattr(sql_queries, query)(ALL) == await getattr(ref, query)(ALL)


async def test_filters_narrow_consistently(dataset, sql_queries) -> None:  # type: ignore[no-untyped-def]
    ref, sources = dataset
    for f in (
        DashboardFilters(data_source_id=sources["tracelab"]),
        DashboardFilters(date_from=DAY_2),
        DashboardFilters(date_to=DAY_1),
    ):
        assert await sql_queries.overview(f) == await ref.overview(f), f
        assert await sql_queries.activity(f) == await ref.activity(f), f


def test_every_view_keeps_data_source_id(clean_db) -> None:  # type: ignore[no-untyped-def]
    """Without it, a `per_source_only` metric cannot be kept per source.

    Uses `clean_db` so the schema is migrated by this test's own fixture rather
    than by whichever test happened to run before it.
    """
    from sqlalchemy import text

    for view in (
        "v_session_metrics",
        "v_daily_activity",
        "v_tool_usage",
        "v_model_usage",
        "v_import_quality",
    ):
        columns = {
            row[0]
            for row in clean_db.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :view"),
                {"view": view},
            )
        }
        assert columns, f"{view} does not exist"
        assert "data_source_id" in columns, f"{view} lost data_source_id"
