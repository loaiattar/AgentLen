"""Fixtures for the cross-implementation contract suite.

Re-exports the throwaway-Postgres fixtures rather than starting a second
container. `tests/__init__.py` exists so pytest names this package's conftest
`tests.integration.conftest` — the same name the explicit import below
produces. Without it the module is loaded twice under two names, each with its
own session-scoped fixture, and two containers start per run.
"""

from tests.integration.conftest import (  # noqa: F401
    clean_db,
    database_url,
    empty_database,
    engine,
    requires_postgres,
)
