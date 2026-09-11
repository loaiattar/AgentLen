"""Data source routes (API.md §2)."""

from __future__ import annotations

from httpx import AsyncClient

from agentlen.interfaces.http.pagination import MAX_LIMIT
from tests.integration.conftest import requires_postgres


@requires_postgres
async def test_list_is_empty_before_any_source_is_declared(live_client: AsyncClient) -> None:
    response = await live_client.get("/api/v1/data-sources")

    assert response.status_code == 200
    assert response.json() == []


@requires_postgres
async def test_creating_a_source_returns_201_with_the_full_record(
    live_client: AsyncClient,
) -> None:
    response = await live_client.post(
        "/api/v1/data-sources",
        json={
            "slug": "tracelab",
            "name": "TraceLab",
            "url": "https://github.com/uw-syfi/TraceLab",
            "license": "MIT",
            "dataset_version": "v0.0.1",
            "retrieved_at": "2026-09-07",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "tracelab"
    assert body["dataset_version"] == "v0.0.1"
    assert body["retrieved_at"] == "2026-09-07"
    assert body["id"] is not None
    assert body["created_at"] is not None


@requires_postgres
async def test_created_source_appears_in_the_list(live_client: AsyncClient) -> None:
    await live_client.post("/api/v1/data-sources", json={"slug": "swe-chat", "name": "SWE-chat"})

    response = await live_client.get("/api/v1/data-sources")

    slugs = {s["slug"] for s in response.json()}
    assert "swe-chat" in slugs


@requires_postgres
async def test_list_is_a_bounded_bare_array_that_reports_its_total(
    live_client: AsyncClient,
) -> None:
    """A documented exception to the page envelope (API.md §1): still an array,
    so existing consumers keep working, but windowed and counted."""
    for slug in ("window-a", "window-b", "window-c"):
        await live_client.post("/api/v1/data-sources", json={"slug": slug, "name": slug})

    full = await live_client.get("/api/v1/data-sources")
    total = int(full.headers["x-total-count"])
    assert total == len(full.json()) >= 3

    page = await live_client.get("/api/v1/data-sources", params={"limit": 2, "offset": 1})
    assert page.json() == full.json()[1:3]
    assert page.headers["x-total-count"] == str(total)


async def test_list_limit_above_the_ceiling_is_rejected(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/data-sources?limit={MAX_LIMIT + 1}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_REQUEST"


@requires_postgres
async def test_duplicate_slug_is_rejected_with_409(live_client: AsyncClient) -> None:
    body = {"slug": "duplicate-me", "name": "First"}
    first = await live_client.post("/api/v1/data-sources", json=body)
    assert first.status_code == 201

    second = await live_client.post(
        "/api/v1/data-sources", json={"slug": "duplicate-me", "name": "Second attempt"}
    )

    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["details"]["slug"] == "duplicate-me"


@requires_postgres
async def test_missing_required_field_is_a_400_not_a_500(live_client: AsyncClient) -> None:
    """422 is reserved for business validation (API.md §1) — a malformed
    request body is remapped to 400, same as everywhere else in the API."""
    response = await live_client.post("/api/v1/data-sources", json={"slug": "no-name"})

    assert response.status_code == 400


async def test_list_answers_the_shared_error_envelope_when_the_database_is_down(
    client: AsyncClient,
) -> None:
    """No database at all -> the generic 500 handler, same envelope as everywhere else."""
    response = await client.get("/api/v1/data-sources")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
