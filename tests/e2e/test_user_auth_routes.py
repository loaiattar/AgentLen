"""Full HTTP flow for /auth/* against a migrated database.

Distinct from tests/e2e/test_auth.py, which covers the app-wide `X-API-Key`
gate. Every request here still carries that header too (`live_client` sends
it on every call) — these tests are about the *second*, per-person layer on
top of it.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agentlen.interfaces.http.app import create_app
from tests.e2e.conftest import UNREACHABLE_URL
from tests.integration.conftest import requires_postgres


async def _register(client: AsyncClient, *, email: str, password: str) -> object:
    return await client.post("/api/v1/auth/register", json={"email": email, "password": password})


@requires_postgres
async def test_register_creates_a_user(live_client: AsyncClient) -> None:
    response = await _register(
        live_client, email="alice@example.com", password="a-strong-passphrase"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["id"] is not None
    assert "password" not in body
    assert "password_hash" not in body


@requires_postgres
async def test_register_rejects_an_invalid_email(live_client: AsyncClient) -> None:
    response = await _register(live_client, email="not-an-email", password="a-strong-passphrase")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_EMAIL"


@requires_postgres
async def test_register_rejects_a_duplicate_email(live_client: AsyncClient) -> None:
    first = await _register(live_client, email="dup@example.com", password="a-strong-passphrase")
    assert first.status_code == 201

    second = await _register(live_client, email="dup@example.com", password="another-passphrase")

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


@requires_postgres
async def test_password_is_never_stored_in_clear(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    await _register(live_client, email="hashed@example.com", password="a-strong-passphrase")

    async with live_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT password_hash FROM users WHERE email = :email"),
                {"email": "hashed@example.com"},
            )
        ).one()

    assert row.password_hash != "a-strong-passphrase"
    # bcrypt's own format marker — proof it went through the real hasher, not
    # a pass-through.
    assert row.password_hash.startswith("$2")


@requires_postgres
async def test_login_with_valid_credentials_returns_a_token(live_client: AsyncClient) -> None:
    await _register(live_client, email="login-ok@example.com", password="a-strong-passphrase")

    response = await live_client.post(
        "/api/v1/auth/login",
        json={"email": "login-ok@example.com", "password": "a-strong-passphrase"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "login-ok@example.com"
    assert "password" not in body["user"]


@requires_postgres
async def test_login_rejects_the_wrong_password(live_client: AsyncClient) -> None:
    await _register(live_client, email="login-bad@example.com", password="a-strong-passphrase")

    response = await live_client.post(
        "/api/v1/auth/login",
        json={"email": "login-bad@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@requires_postgres
async def test_login_rejects_an_unknown_account(live_client: AsyncClient) -> None:
    response = await live_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@requires_postgres
async def test_protected_route_without_a_token_is_401(live_client: AsyncClient) -> None:
    response = await live_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@requires_postgres
async def test_protected_route_with_a_valid_token_returns_the_user(
    live_client: AsyncClient,
) -> None:
    await _register(live_client, email="me@example.com", password="a-strong-passphrase")
    login = await live_client.post(
        "/api/v1/auth/login", json={"email": "me@example.com", "password": "a-strong-passphrase"}
    )
    token = login.json()["token"]

    response = await live_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


@requires_postgres
async def test_logout_invalidates_the_token(live_client: AsyncClient) -> None:
    await _register(live_client, email="logout@example.com", password="a-strong-passphrase")
    login = await live_client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "a-strong-passphrase"},
    )
    token = login.json()["token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    logout_response = await live_client.post("/api/v1/auth/logout", headers=auth_header)
    assert logout_response.status_code == 204

    after_logout = await live_client.get("/api/v1/auth/me", headers=auth_header)
    assert after_logout.status_code == 401


async def test_register_missing_password_is_a_400_not_a_500(client: AsyncClient) -> None:
    """422 is reserved for business validation (API.md §1); a malformed body
    is remapped to 400, same as everywhere else in the API — checked before
    the (unreachable, in this fixture) database is ever touched."""
    response = await client.post("/api/v1/auth/register", json={"email": "alice@example.com"})

    assert response.status_code == 400


#: 255 characters: one past the schema limit, otherwise a well-formed address.
TOO_LONG_EMAIL = "a" * 64 + "@" + "b" * 186 + ".com"
#: 37 characters but 74 bytes: passes a character count, not bcrypt's byte limit.
TOO_LONG_PASSWORD = "é" * 37


@pytest.mark.parametrize("path", ["/api/v1/auth/register", "/api/v1/auth/login"])
@pytest.mark.parametrize(
    ("body", "field_path"),
    [
        ({"email": TOO_LONG_EMAIL, "password": "a-strong-passphrase"}, "body.email"),
        ({"email": "a@" + "a." * 25_000 + "@", "password": "a-strong-passphrase"}, "body.email"),
        ({"email": "alice@example.com", "password": TOO_LONG_PASSWORD}, "body.password"),
        ({"email": "alice@example.com", "password": "x" * 50_000}, "body.password"),
    ],
)
async def test_over_long_credentials_are_a_400_before_any_use_case(
    client: AsyncClient, path: str, body: dict[str, str], field_path: str
) -> None:
    """Issue #190: unauthenticated routes bound their input in the schema.

    `client` has no reachable database, so a 400 here proves the request was
    refused before the use case — and the e-mail pattern — ever ran.
    """
    response = await client.post(path, json=body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "MALFORMED_REQUEST"
    assert error["field_path"] == field_path


def test_credential_limits_are_published_in_the_contract() -> None:
    spec = create_app(engine=create_async_engine(UNREACHABLE_URL)).openapi()
    schemas = spec["components"]["schemas"]

    for name in ("RegisterIn", "LoginIn"):
        properties = schemas[name]["properties"]
        assert properties["email"]["maxLength"] == 254
        assert properties["password"]["maxLength"] == 72


async def test_protected_route_still_needs_the_app_api_key() -> None:
    """The per-user session sits on top of X-API-Key, not instead of it.

    No database involved: the request must be rejected by `ApiKeyMiddleware`
    before it ever reaches the `/auth/me` dependency, so this runs even
    without Docker (same "unreachable engine" trick as tests/e2e/conftest.py).
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    unreachable = create_async_engine("postgresql+asyncpg://nobody:nobody@127.0.0.1:1/agentlen")
    app = create_app(engine=unreachable)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")  # no X-API-Key header

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
