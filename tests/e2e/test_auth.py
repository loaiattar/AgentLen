"""Authenticated GET /sessions against a migrated database (issue #17)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.conftest import requires_postgres


@requires_postgres
async def test_sessions_with_the_configured_key_is_200(live_client: AsyncClient) -> None:
    response = await live_client.get("/api/v1/sessions")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
