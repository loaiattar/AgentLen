"""Fixtures for the acceptance suite.

Re-exported rather than redefined: the throwaway Postgres is shared with the
integration package instead of a third container being started, and the HTTP
clients are the same ones the end-to-end tests drive — an acceptance test that
built its own app would be proving its own wiring.
"""

from __future__ import annotations

from tests.e2e.conftest import (  # noqa: F401
    client,
    live_client,
    live_engine,
)
from tests.integration.conftest import (  # noqa: F401
    clean_db,
    database_url,
    engine,
    requires_postgres,
)
