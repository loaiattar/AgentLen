"""The shared pagination contract every list route will inherit."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.pagination import MAX_LIMIT, Paginated, paginate
from agentlen.interfaces.http.schemas.common import Page

from .conftest import UNREACHABLE_URL

ROWS = [f"row-{i}" for i in range(500)]


@pytest.fixture
async def paged_client() -> AsyncIterator[AsyncClient]:
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))

    async def listing(params: Paginated) -> Page[str]:
        window = ROWS[params.offset : params.offset + params.limit]
        return paginate(window, total=len(ROWS), params=params)

    app.router.add_api_route("/things", listing, methods=["GET"])
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_defaults_to_fifty_from_the_start(paged_client: AsyncClient) -> None:
    body = (await paged_client.get("/things")).json()

    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 50
    assert body["items"][0] == "row-0"


async def test_total_ignores_the_window(paged_client: AsyncClient) -> None:
    """`total` counts every match, so the front can render a pager without a
    second request."""
    body = (await paged_client.get("/things?limit=10&offset=100")).json()

    assert body["total"] == 500
    assert len(body["items"]) == 10
    assert body["items"][0] == "row-100"


async def test_limit_above_the_ceiling_is_rejected(paged_client: AsyncClient) -> None:
    """Without a ceiling, `?limit=1000000` is a denial-of-service primitive that
    costs the caller one request."""
    response = await paged_client.get(f"/things?limit={MAX_LIMIT + 1}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_REQUEST"


@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "offset=-1"])
async def test_nonsense_windows_are_rejected(paged_client: AsyncClient, query: str) -> None:
    assert (await paged_client.get(f"/things?{query}")).status_code == 400


async def test_offset_past_the_end_returns_an_empty_page_not_an_error(
    paged_client: AsyncClient,
) -> None:
    """Paging past the end is a normal outcome of a concurrent delete, not a
    client mistake."""
    body = (await paged_client.get("/things?offset=9999")).json()

    assert body["items"] == []
    assert body["total"] == 500
