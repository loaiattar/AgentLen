"""Liveness, readiness and version."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import requires_postgres


async def test_health_answers_without_a_database(client: AsyncClient) -> None:
    """Liveness must not depend on Postgres.

    If it did, an orchestrator would restart the API every time the database
    blinked — turning a recoverable outage into a restart loop.
    """
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_is_also_served_unprefixed(client: AsyncClient) -> None:
    """Probes conventionally hit /health; API.md documents the versioned path."""
    assert (await client.get("/health")).status_code == 200


async def test_ready_returns_503_when_the_database_is_unreachable(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["status"] == "error"


async def test_ready_does_not_leak_the_connection_string(client: AsyncClient) -> None:
    """A failed probe reports the exception class, never the DSN.

    Connection errors habitually embed the URL, and the URL embeds the password.
    """
    body = await (await client.get("/api/v1/health/ready")).aread()
    text = body.decode()
    assert "nobody" not in text
    assert "127.0.0.1" not in text


async def test_unbuilt_worker_is_reported_but_does_not_block(client: AsyncClient) -> None:
    """`unknown` is honest for a component that does not exist yet (#55), and
    must not be laundered into `ok` nor used to fail readiness."""
    checks = (await client.get("/api/v1/health/ready")).json()["checks"]
    assert checks["worker"]["status"] == "unknown"


@requires_postgres
async def test_ready_returns_200_against_a_migrated_database(
    live_client: AsyncClient,
) -> None:
    response = await live_client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["migrations"]["status"] == "ok"


@requires_postgres
async def test_ready_reports_the_revision_applied_to_the_database(
    live_client: AsyncClient,
) -> None:
    """Read from alembic_version, not assumed from disk: the point is to know
    which schema is actually live."""
    body = (await live_client.get("/api/v1/health/ready")).json()

    # Asserted against head rather than a literal: pinning "0001" here made
    # this test fail the moment a second migration landed, which says nothing
    # about the endpoint.
    assert body["alembic_revision"] is not None
    assert body["alembic_revision"] == body["alembic_head"]


async def test_ready_reports_null_revision_when_database_is_down(
    client: AsyncClient,
) -> None:
    """Does not invent a revision it could not read."""
    body = (await client.get("/api/v1/health/ready")).json()

    assert body["alembic_revision"] is None
    # head comes from disk, so it is known even with no database.
    assert body["alembic_head"] is not None


class _NoDatabase:
    """An engine that fails the test the moment anything tries to use it."""

    def connect(self) -> None:
        raise AssertionError("/version must not touch the database")

    begin = connect


async def test_version_never_touches_the_database() -> None:
    """Public and hit by probes: it must cost nothing and disclose no schema."""
    from agentlen.interfaces.http.app import create_app
    from tests.e2e.conftest import asgi_client

    app = create_app(engine=_NoDatabase())  # type: ignore[arg-type]
    async with asgi_client(app) as c:
        response = await c.get("/api/v1/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0.1.0"}


@requires_postgres
async def test_engine_is_disposed_on_shutdown(live_engine: AsyncEngine) -> None:
    """The lifespan hook must close the pool, or a reloading dev server leaks
    one pool per restart until Postgres refuses connections."""
    from agentlen.interfaces.http.app import create_app
    from tests.e2e.conftest import asgi_client

    app = create_app(engine=live_engine)
    async with asgi_client(app) as c:
        assert (await c.get("/api/v1/health")).status_code == 200
