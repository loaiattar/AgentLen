"""Shared HTTP test credentials, and the rule deciding which tests need Postgres.

The API key is a fixture value, not a production secret. It is injected into
the environment so `create_app()` without an explicit `settings=` still
protects routes the same way the process does in CI.
"""

from __future__ import annotations

from functools import cache

import pytest

TEST_API_KEY = "test-api-key"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}

#: The fixture every database fixture ends at (`engine`, `clean_db`, `live_engine`...).
DATABASE_FIXTURE = "database_url"


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every test that reaches the database as `integration`.

    Derived from the fixture closure, so a module that forgets
    `requires_postgres` is still marked. `tryfirst` puts this ahead of `-m`
    deselection, which is what makes `-m "not integration"` a reliable way to
    run only the tests that need no database.
    """
    for item in items:
        needs_database = DATABASE_FIXTURE in getattr(item, "fixturenames", ())
        if needs_database and item.get_closest_marker("integration") is None:
            item.add_marker(pytest.mark.integration)


@cache
def _database_available() -> bool:
    # Imported here so that collecting tests which need no database never
    # probes Docker, and the probe runs at most once per session.
    from tests.integration.conftest import database_available

    return database_available()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip an `integration` test only when no database can be had at all."""
    if item.get_closest_marker("integration") is not None and not _database_available():
        pytest.skip("no test database: set TEST_DATABASE_URL or make Docker available")


@pytest.fixture(autouse=True)
def configure_http_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
