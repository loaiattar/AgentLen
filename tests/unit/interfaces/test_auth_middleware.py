"""API-key middleware and CORS (issue #17)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.infrastructure.config.settings import Settings
from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.auth import UNAUTHORIZED_MESSAGE

UNREACHABLE_URL = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/agentlen"

CONFIGURED_KEY = "test-api-key-must-not-leak"


def _settings() -> Settings:
    return Settings(api_key=CONFIGURED_KEY, origins="http://localhost:5173")


@pytest.fixture
async def app_client() -> AsyncIterator[AsyncClient]:
    app = create_app(
        engine=create_async_engine(UNREACHABLE_URL),
        settings=_settings(),
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _unauthorized(body: object) -> None:
    assert isinstance(body, dict)
    error = body["error"]
    assert error["code"] == "UNAUTHORIZED"
    assert error["message"] == UNAUTHORIZED_MESSAGE
    assert "field_path" in error
    assert "details" in error


async def test_sessions_without_header_is_401(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/v1/sessions")
    assert response.status_code == 401
    _unauthorized(response.json())


async def test_sessions_with_the_wrong_key_is_401(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/v1/sessions", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
    _unauthorized(response.json())


async def test_health_is_public(app_client: AsyncClient) -> None:
    for path in ("/health", "/api/v1/health"):
        response = await app_client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


async def test_version_is_public(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


async def test_metrics_definitions_accepts_the_configured_key(app_client: AsyncClient) -> None:
    """A protected route that needs no database: auth is the only gate."""
    response = await app_client.get(
        "/api/v1/metrics/definitions",
        headers={"X-API-Key": CONFIGURED_KEY},
    )
    assert response.status_code == 200
    assert "definitions" in response.json()


async def test_empty_configured_key_rejects_every_protected_route() -> None:
    app = create_app(
        engine=create_async_engine(UNREACHABLE_URL),
        settings=Settings(api_key="", origins="http://localhost:5173"),
    )
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/metrics/definitions",
            headers={"X-API-Key": ""},
        )
    assert response.status_code == 401


async def test_cors_preflight_from_the_dev_origin(app_client: AsyncClient) -> None:
    response = await app_client.options(
        "/api/v1/sessions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    allowed_methods = response.headers["access-control-allow-methods"].upper()
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        assert method in allowed_methods
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-api-key" in allowed_headers
    assert "content-type" in allowed_headers


async def test_unauthorized_response_still_carries_cors_headers(
    app_client: AsyncClient,
) -> None:
    response = await app_client.get(
        "/api/v1/sessions",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_the_api_key_is_never_logged(
    app_client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="agentlen.http.auth"):
        await app_client.get("/api/v1/sessions", headers={"X-API-Key": "wrong-key-value"})
        await app_client.get("/api/v1/sessions", headers={"X-API-Key": CONFIGURED_KEY})

    text = caplog.text
    assert CONFIGURED_KEY not in text
    assert "wrong-key-value" not in text


async def test_settings_repr_does_not_include_the_key() -> None:
    settings = Settings(api_key=CONFIGURED_KEY, origins="http://localhost:5173")
    dumped = repr(settings)
    assert CONFIGURED_KEY not in dumped
    assert "api_key" not in dumped
