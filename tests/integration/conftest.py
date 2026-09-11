"""Integration-test fixtures: a real, throwaway Postgres 16.

These tests deliberately use a real database rather than SQLite. The things
being checked here — IDENTITY columns, partial indexes, JSONB, CHECK
constraints, deferred FK ordering — either behave differently on SQLite or do
not exist there, so a SQLite pass would prove nothing about production.

A test that needs this database is marked `integration`. It runs when
`TEST_DATABASE_URL` names a database or Docker can start one, and skips
otherwise, so `pytest tests/unit` on a bare machine stays green. The marking
and the skip live in `tests/conftest.py`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Mapping

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


def database_available(
    env: Mapping[str, str] = os.environ,
    docker_available: Callable[[], bool] = _docker_available,
) -> bool:
    """Whether `database_url` can yield a database.

    The two sources the fixture itself uses, in the same order: a preset
    `TEST_DATABASE_URL` needs no Docker at all, so Docker is only probed
    when that variable is absent.
    """
    return bool(env.get("TEST_DATABASE_URL")) or docker_available()


#: The explicit spelling of the `integration` marker, kept for the modules and
#: parameters that already use it. `tests/conftest.py` also adds the marker to
#: any test whose fixtures reach `database_url` (a forgotten marker used to
#: turn a skip into an error) and skips marked tests when no database exists.
requires_postgres = pytest.mark.integration


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
def empty_database(engine: Engine) -> None:
    """The test database migrated to head, with every table emptied.

    The one cleanup every database test goes through: `clean_db` here and
    `live_engine` in the e2e suite both depend on it. It runs before the test
    rather than after, so a test starts from an empty database whatever ran
    before it, including a test that crashed half-way. Being function-scoped,
    it runs once per test even when a test asks for both fixtures, so data
    seeded through one of them is not wiped by the other.

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


@pytest.fixture
def clean_db(engine: Engine, empty_database: None) -> Iterator[Connection]:
    """A connection to the migrated, emptied test database."""
    with engine.begin() as conn:
        yield conn
