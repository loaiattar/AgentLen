"""Integration-test fixtures: a real, throwaway Postgres 16.

These tests deliberately use a real database rather than SQLite. The things
being checked here — IDENTITY columns, partial indexes, JSONB, CHECK
constraints, deferred FK ordering — either behave differently on SQLite or do
not exist there, so a SQLite pass would prove nothing about production.

The whole module skips if Docker is unavailable, so `pytest tests/unit` on a
machine without Docker stays green.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection, Engine, create_engine, text

from agentlen.infrastructure.persistence.engine import to_sync_url

try:  # testcontainers moved this module; support both layouts
    from testcontainers.community.postgres import PostgresContainer
except ImportError:  # pragma: no cover
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        PostgresContainer = None  # type: ignore[assignment,misc]

_HAS_TESTCONTAINERS = PostgresContainer is not None


def _docker_available() -> bool:
    if not _HAS_TESTCONTAINERS:
        return False
    import shutil
    import subprocess

    docker = shutil.which("docker")
    if docker is None:
        return False
    return (
        subprocess.run(  # noqa: S603 - resolved absolute path, no shell, no user input
            [docker, "info"], capture_output=True, timeout=30, check=False
        ).returncode
        == 0
    )


requires_postgres = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker unavailable — integration tests need a throwaway Postgres",
)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A Postgres 16 for the whole test session.

    Honours DATABASE_URL when it is already set (CI provides a service
    container), otherwise starts one via testcontainers.
    """
    preset = os.environ.get("TEST_DATABASE_URL")
    if preset:
        yield to_sync_url(preset)
        return

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    eng = create_engine(database_url, future=True)
    yield eng
    eng.dispose()


@pytest.fixture
def clean_db(engine: Engine) -> Iterator[Connection]:
    """A connection to a database migrated to head, emptied between tests.

    TRUNCATE ... RESTART IDENTITY CASCADE rather than re-running the
    migrations for every test: same isolation, a fraction of the runtime.
    """
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(cfg, "head")

    with engine.begin() as conn:
        names = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
        ]
        if names:
            conn.execute(text(f"TRUNCATE {', '.join(names)} RESTART IDENTITY CASCADE"))

    with engine.begin() as conn:
        yield conn
