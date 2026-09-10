"""HTTP exploration against a migrated Postgres, including chart replay."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text, update

from agentlen.infrastructure.persistence import tables as t
from agentlen.interfaces.http.app import create_app
from tests.e2e.conftest import asgi_client
from tests.integration.conftest import clean_db, requires_postgres  # noqa: F401
from tests.integration.test_read_models import dataset  # noqa: F401


@pytest.mark.parametrize(
    "path",
    [
        "sessions?limit=10000",
        "sessions?limit=0",
        "sessions?offset=-1",
        "sessions?status=invalid",
        "sessions/nope",
        "records/nope",
    ],
)
async def test_invalid_requests(client, path):
    response = await client.get("/api/v1/" + path)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_REQUEST"


@pytest.fixture
async def exploration_dataset(dataset, live_engine):  # noqa: F811
    try:
        yield dataset
    finally:
        # Other HTTP tests expect an empty database; the imported fixture commits.
        async with live_engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE data_source, file_upload, provider, agent, tool, repository "
                    "RESTART IDENTITY CASCADE"
                )
            )


@requires_postgres
async def test_exploration_and_drill_down(exploration_dataset, live_engine):
    ref, sources = exploration_dataset
    app = create_app(engine=live_engine)
    async with asgi_client(app, base_url="http://test/api/v1") as client:
        response = await client.get(
            "sessions",
            params={"data_source_id": sources["tracelab"], "date_from": "2026-01-01", "limit": 2},
        )
        assert response.status_code == 200
        page = response.json()
        assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)
        assert len(page["items"]) == 2
        assert page["items"][0]["duration_ms"] is None
        assert (await client.get("sessions?offset=100")).json()["total"] == 4
        assert (await client.get("sessions?offset=100")).json()["items"] == []
        sid = ref.sessions[0]["id"]
        detail = (await client.get(f"sessions/{sid}")).json()
        assert [c["sequence_index"] for c in detail["model_calls"]] == [0, 1, 2]
        assert [c["sequence_index"] for c in detail["tool_calls"]] == [0, 1, 2, 3, 4]
        raw_id = detail["session"]["raw_record_id"]
        payload = {"original": ["é", None, False, 0, {"nested": "untouched"}]}
        async with live_engine.begin() as conn:
            await conn.execute(
                update(t.raw_record)
                .where(t.raw_record.c.id == raw_id)
                .values(payload=payload, line_number=42)
            )
            await conn.execute(
                update(t.session).where(t.session.c.id == sid).values(outcome="error")
            )
            for table, index, hour in [
                (t.model_call, 0, 10),
                (t.tool_call, 0, 9),
                (t.model_call, 1, 11),
            ]:
                await conn.execute(
                    update(table)
                    .where(table.c.session_id == sid, table.c.sequence_index == index)
                    .values(started_at=datetime(2026, 8, 1, hour, tzinfo=UTC))
                )
        raw = (await client.get(f"records/{raw_id}")).json()
        assert raw["payload"] == payload
        assert raw["line_number"] == 42
        events = (await client.get(f"sessions/{sid}/timeline")).json()
        assert [e["type"] for e in events[:3]] == ["tool_call", "model_call", "model_call"]
        assert len(events) == 8
        assert all(e["event"]["started_at"] is None for e in events[3:])
        assert [(e["event"]["sequence_index"], e["type"]) for e in events[3:]] == [
            (1, "tool_call"),
            (2, "model_call"),
            (2, "tool_call"),
            (3, "tool_call"),
            (4, "tool_call"),
        ]
        for params in (
            {},
            {"status": "error"},
            {"tool_id": ref.tool_calls[1]["tool_id"]},
            {"date_from": "2026-08-02"},
            {"agent_id": ref.sessions[0]["agent_id"]},
        ):
            points = (await client.get("metrics/tools", params=params)).json()["points"]
            for point in points:
                replay = await client.get("sessions", params=point["filters"])
                assert replay.status_code == 200
                ids = [s["id"] for s in replay.json()["items"]]
                async with live_engine.connect() as conn:
                    calls = (
                        await conn.execute(
                            select(t.tool_call).where(
                                t.tool_call.c.session_id.in_(ids),
                                t.tool_call.c.tool_id == point["tool_id"],
                            )
                        )
                    ).all()
                assert len(calls) == point["call_count"]
        filters = {
            "data_source_id": sources["tracelab"],
            "agent_id": ref.sessions[0]["agent_id"],
            "import_run_id": ref.sessions[0]["import_run_id"],
            "model_id": ref.model_calls[0]["model_id"],
            "tool_id": ref.tool_calls[0]["tool_id"],
            "date_from": "2026-08-01",
            "date_to": "2026-08-02",
            "status": "error",
        }
        selected = (await client.get("sessions", params=filters)).json()
        assert [s["id"] for s in selected["items"]] == [sid]
        for key in ("data_source_id", "agent_id", "import_run_id", "model_id", "tool_id"):
            assert (await client.get("sessions", params={**filters, key: 99999})).json()[
                "total"
            ] == 0
        assert (await client.get("sessions", params={**filters, "status": "completed"})).json()[
            "total"
        ] == 0
        for path in ("sessions/99999", "sessions/99999/timeline", "records/99999"):
            response = await client.get(path)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "NOT_FOUND"
        empty_sid = ref.sessions[1]["id"]
        assert (await client.get(f"sessions/{empty_sid}")).json()["tool_calls"] == []


def test_openapi_shares_all_eight_filters():
    paths = create_app().openapi()["paths"]
    expected = {
        "data_source_id",
        "agent_id",
        "model_id",
        "tool_id",
        "import_run_id",
        "date_from",
        "date_to",
        "status",
    }
    for route in (
        "sessions",
        "metrics/overview",
        "metrics/activity",
        "metrics/tools",
        "metrics/models",
        "metrics/quality",
    ):
        names = {p["name"] for p in paths[f"/api/v1/{route}"]["get"]["parameters"]}
        assert expected <= names
