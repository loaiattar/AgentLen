"""Database URL resolution and engine construction.

Kept deliberately small. The full 12-factor settings module arrives with the
AI configuration work (issue #49); until then this reads the one variable the
persistence layer needs, so nothing has to be rewritten when that lands.
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

DEFAULT_DATABASE_URL = "postgresql+asyncpg://agentlen:agentlen@localhost:5432/agentlen"

#: Alembic runs migrations synchronously; the application runs async.
#: One URL is configured, and the driver is swapped as needed.
ASYNC_DRIVER = "postgresql+asyncpg"
SYNC_DRIVER = "postgresql+psycopg"


def get_database_url() -> str:
    """The configured database URL, in its async form."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def to_sync_url(url: str) -> str:
    """Rewrite a URL to the synchronous driver, for Alembic."""
    for prefix in (ASYNC_DRIVER, "postgresql+asyncpg", "postgresql"):
        if url.startswith(prefix + "://"):
            return SYNC_DRIVER + url[len(prefix) :]
    return url


def to_async_url(url: str) -> str:
    """Rewrite a URL to the asyncpg driver, for the application."""
    for prefix in (SYNC_DRIVER, "postgresql+psycopg2", "postgresql"):
        if url.startswith(prefix + "://"):
            return ASYNC_DRIVER + url[len(prefix) :]
    return url


def create_engine(url: str | None = None, *, echo: bool = False) -> AsyncEngine:
    """Build the application's async engine."""
    return create_async_engine(to_async_url(url or get_database_url()), echo=echo)
