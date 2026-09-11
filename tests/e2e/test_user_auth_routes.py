"""Full HTTP flow for /auth/* against a migrated database.

Distinct from tests/e2e/test_auth.py, which covers the app-wide `X-API-Key`
gate. Every request here still carries that header too (`live_client` sends
it on every call) — these tests are about the *second*, per-person layer on
top of it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher
from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.dependencies import get_clock, get_password_hasher
from tests.e2e.conftest import asgi_client
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
    assert "dup@example.com" not in second.text, "the error must not echo the address"


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


@requires_postgres
async def test_session_token_is_stored_only_as_its_sha256(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    credentials = {"email": "digest@example.com", "password": "a-strong-passphrase"}
    await _register(live_client, **credentials)
    token = (await live_client.post("/api/v1/auth/login", json=credentials)).json()["token"]

    async with live_engine.connect() as conn:
        stored = (await conn.execute(text("SELECT token_hash FROM user_session"))).scalars().all()

    assert stored == [hashlib.sha256(token.encode("utf-8")).hexdigest()]


class _MovableClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


@requires_postgres
async def test_expired_session_is_refused_then_purged_by_the_next_login(
    live_engine: AsyncEngine,
) -> None:
    clock = _MovableClock(datetime(2026, 9, 11, 12, 0, tzinfo=UTC))
    app = create_app(engine=live_engine)
    app.dependency_overrides[get_clock] = lambda: clock
    credentials = {"email": "expiry@example.com", "password": "a-strong-passphrase"}

    async with asgi_client(app) as client:
        await _register(client, **credentials)
        old = (await client.post("/api/v1/auth/login", json=credentials)).json()["token"]
        clock.current += timedelta(days=31)
        refused = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"})
        await client.post("/api/v1/auth/login", json=credentials)

    async with live_engine.connect() as conn:
        sessions = (await conn.execute(text("SELECT count(*) FROM user_session"))).scalar_one()

    assert refused.status_code == 401
    assert sessions == 1, "the expired session must be purged, only the new one left"


class _SpyHasher(BcryptPasswordHasher):
    def __init__(self) -> None:
        self.verified: list[str | None] = []

    async def verify(self, password: str, password_hash: str | None) -> bool:
        self.verified.append(password_hash)
        return await super().verify(password, password_hash)


@requires_postgres
async def test_login_for_an_unknown_account_still_runs_bcrypt(live_engine: AsyncEngine) -> None:
    spy = _SpyHasher()
    app = create_app(engine=live_engine)
    app.dependency_overrides[get_password_hasher] = lambda: spy

    async with asgi_client(app) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "whatever-password"},
        )

    assert response.status_code == 401
    assert spy.verified == [None], "the dummy-hash verification must run"


async def test_register_missing_password_is_a_400_not_a_500(client: AsyncClient) -> None:
    """422 is reserved for business validation (API.md §1); a malformed body
    is remapped to 400, same as everywhere else in the API — checked before
    the (unreachable, in this fixture) database is ever touched."""
    response = await client.post("/api/v1/auth/register", json={"email": "alice@example.com"})

    assert response.status_code == 400


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
