"""Fixtures for HTTP-level tests.

Most of these tests need no database: the app is built, driven through an ASGI
transport in-process, and asserted on. Only readiness and version genuinely
touch Postgres, and they reuse the throwaway container from the integration
fixtures rather than starting a second one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.interfaces.http.app import create_app
from tests.conftest import AUTH_HEADERS

# Re-exported so the postgres container is shared with tests/integration
# instead of a second one being started for this package.
from tests.integration.conftest import (  # noqa: F401
    database_url,
    engine,
    requires_postgres,
)

#: A port nothing listens on: the cheapest honest way to simulate "database down".
UNREACHABLE_URL = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/agentlen"


def asgi_client(
    app: Any,
    *,
    raise_app_exceptions: bool = True,
    base_url: str = "http://test",
) -> AsyncClient:
    """HTTP client that presents the test API key on every request."""
    transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
    return AsyncClient(transport=transport, base_url=base_url, headers=AUTH_HEADERS)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """A client on an app with no reachable database.

    Correct for every route that must answer without one — which is most of
    them, and all of the error-handling behaviour.
    """
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    # Starlette's ServerErrorMiddleware sends the 500 response *and* re-raises
    # the original exception (so an ASGI server can still log/crash on it).
    # httpx's default would re-raise that instead of returning the response.
    async with asgi_client(app, raise_app_exceptions=False) as c:
        yield c


@pytest.fixture
async def live_engine(database_url: str) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    """An async engine on the migrated test database, emptied before each test.

    The emptying is what makes these tests independent of the order they run
    in. Without it, several tests that assert on an empty database passed only
    because an earlier file happened to leave one behind — and two test modules
    carried their own `TRUNCATE` in a `finally` to keep that arrangement
    standing. Those are gone; cleaning belongs to the fixture that hands out
    the database, not to whoever used it last.

    Before rather than after: a test that fails midway still leaves the next
    one a clean database, and the rows it left behind stay inspectable.

    `TRUNCATE ... RESTART IDENTITY CASCADE` over re-running the migrations —
    the same isolation for a fraction of the runtime, and it matches what
    `clean_db` does for the integration suite.
    """
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")

    eng = create_async_engine(to_async_url(database_url))
    async with eng.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        )
        names = [r[0] for r in rows]
        if names:
            await conn.execute(text(f"TRUNCATE {', '.join(names)} RESTART IDENTITY CASCADE"))

    yield eng
    await eng.dispose()


@pytest.fixture
async def live_client(live_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """A client on an app wired to the real, migrated database."""
    app = create_app(engine=live_engine)
    async with asgi_client(app) as c:
        yield c
