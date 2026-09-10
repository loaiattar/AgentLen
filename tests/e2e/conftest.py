"""Fixtures for HTTP-level tests.

Most of these tests need no database: the app is built, driven through an ASGI
transport in-process, and asserted on. Only readiness and version genuinely
touch Postgres, and they reuse the throwaway container from the integration
fixtures rather than starting a second one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.interfaces.http.app import create_app

# Re-exported so the postgres container is shared with tests/integration
# instead of a second one being started for this package.
from tests.integration.conftest import (  # noqa: F401
    database_url,
    engine,
    requires_postgres,
)

#: A port nothing listens on: the cheapest honest way to simulate "database down".
UNREACHABLE_URL = "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/agentlen"


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
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def live_engine(database_url: str) -> AsyncIterator[AsyncEngine]:  # noqa: F811
    """An async engine on the migrated test database."""
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")

    eng = create_async_engine(to_async_url(database_url))
    yield eng
    await eng.dispose()


@pytest.fixture
async def live_client(live_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """A client on an app wired to the real, migrated database."""
    app = create_app(engine=live_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
