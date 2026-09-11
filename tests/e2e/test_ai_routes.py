"""AI mapping HTTP flow, entirely through FakeAnalyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import insert, select

from agentlen.application.dto.mapping_document import document_to_mapping
from agentlen.application.errors import AnalyzerError
from agentlen.domain.model.mapping import MappingProposal
from agentlen.infrastructure.ai.fake_adapter import FakeAnalyzer
from agentlen.infrastructure.config.settings import AISettings
from agentlen.infrastructure.persistence import tables as t
from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.dependencies import get_analyzer_factory, get_provider_status

from .conftest import asgi_client, requires_postgres


@pytest.fixture
async def ai_client(live_engine, tmp_path: Path):
    source_file = tmp_path / "sample.jsonl"
    source_file.write_text(json.dumps({"session_id": "one", "agent": "test"}) + "\n")
    async with live_engine.begin() as conn:
        source_id = (
            await conn.execute(
                insert(t.data_source)
                .values(slug="ai-test", name="AI test")
                .returning(t.data_source.c.id)
            )
        ).scalar_one()
        file_id = (
            await conn.execute(
                insert(t.file_upload)
                .values(
                    original_name="sample.jsonl",
                    storage_path=str(source_file),
                    format="jsonl",
                    size_bytes=source_file.stat().st_size,
                    content_hash="f" * 64,
                )
                .returning(t.file_upload.c.id)
            )
        ).scalar_one()

    app = create_app(engine=live_engine)
    app.dependency_overrides[get_analyzer_factory] = lambda: (
        lambda provider, model: FakeAnalyzer(
            AISettings(provider=provider or "fake", model=model or "fake-test")
        )
    )
    app.dependency_overrides[get_provider_status] = lambda: {
        "active": {"provider": "fake", "model": "fake-test"},
        "available": [
            {"provider": "anthropic", "configured": False},
            {"provider": "fake", "configured": True},
        ],
    }
    async with asgi_client(app, base_url="http://test/api/v1") as client:
        yield client, live_engine, file_id, source_id, app


@requires_postgres
async def test_complete_fake_proposal_flow(ai_client):
    client, engine, file_id, source_id, _ = ai_client
    providers = (await client.get("ai/providers")).json()
    assert providers["active"] == {"provider": "fake", "model": "fake-test"}
    assert providers["available"][0] == {"provider": "anthropic", "configured": False}
    assert "key" not in json.dumps(providers).lower()

    response = await client.post(
        "mappings/proposals",
        json={"file_id": file_id, "data_source_id": source_id, "provider": None, "model": None},
    )
    assert response.status_code == 200
    proposal = response.json()
    assert proposal["validation"]["valid"] is True
    assert proposal["ambiguities"]
    assert proposal["unmapped_fields"]

    fetched = (await client.get(f"mappings/proposals/{proposal['proposal_id']}")).json()
    assert fetched == proposal

    refined = await client.post(
        f"mappings/proposals/{proposal['proposal_id']}/messages",
        json={"message": "Conserve les champs non mappés."},
    )
    assert refined.status_code == 200
    async with engine.connect() as conn:
        messages = (
            (
                await conn.execute(
                    select(t.mapping_proposal_message)
                    .where(
                        t.mapping_proposal_message.c.mapping_proposal_id == proposal["proposal_id"]
                    )
                    .order_by(t.mapping_proposal_message.c.turn_index)
                )
            )
            .mappings()
            .all()
        )
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Conserve les champs non mappés."

    document = proposal["mapping"]
    document["entities"][0]["fields"][0]["target"] = "does_not_exist"
    patched = await client.patch(f"mappings/proposals/{proposal['proposal_id']}", json=document)
    assert patched.status_code == 200
    body = patched.json()
    assert body["validation"]["valid"] is False
    assert body["validation"]["errors"][0]["field_path"]
    assert "ambiguities" in body and "unmapped_fields" in body


@requires_postgres
async def test_provider_failure_is_502(ai_client):
    client, _, file_id, _, app = ai_client

    class FailingAnalyzer(FakeAnalyzer):
        async def run_agent_loop(self, profile, tool_executor, hint=None):
            raise AnalyzerError("Réponse fournisseur non conforme")

    app.dependency_overrides[get_analyzer_factory] = lambda: (
        lambda provider, model: FailingAnalyzer()
    )
    response = await client.post("mappings/proposals", json={"file_id": file_id})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ANALYZER_FAILED"


@requires_postgres
async def test_invalid_analyzer_proposal_is_an_editable_200(ai_client):
    client, _, file_id, _, app = ai_client
    invalid = MappingProposal(
        mapping=document_to_mapping(
            {
                "name": "invalid",
                "source_format": "jsonl",
                "entities": [
                    {
                        "target": "session",
                        "natural_key": ["external_id"],
                        "fields": [{"target": "not_a_field", "source": "$.id"}],
                    }
                ],
            }
        ),
        rationale=(),
        ambiguities=(),
        unmapped_fields=(),
        analyzer_descriptor={
            "provider": "fake",
            "model": "invalid-fixture",
            "prompt_version": "test",
        },
    )

    class InvalidAnalyzer(FakeAnalyzer):
        async def run_agent_loop(self, profile, tool_executor, hint=None):
            return invalid

    app.dependency_overrides[get_analyzer_factory] = lambda: (
        lambda provider, model: InvalidAnalyzer()
    )
    response = await client.post("mappings/proposals", json={"file_id": file_id})
    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["valid"] is False
    assert body["validation"]["errors"][0]["field_path"]
    assert body["ambiguities"] == []
    assert body["unmapped_fields"] == []


@requires_postgres
async def test_unknown_proposal_is_404(ai_client):
    client, *_ = ai_client
    response = await client.get("mappings/proposals/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
