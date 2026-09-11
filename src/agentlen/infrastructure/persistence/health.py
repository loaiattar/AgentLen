"""Database readiness probing for GET /health/ready.

Kept out of the HTTP layer so the same check can be reused by the worker and
the CLI. Never raises: a probe that throws would turn "the database is down"
into a 500, and readiness endpoints exist precisely to report that condition
calmly.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

#: Repository root, from this file: src/agentlen/infrastructure/persistence/ -> up 4.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class DatabaseHealth:
    """Outcome of one readiness probe."""

    reachable: bool
    current_revision: str | None = None
    head_revision: str | None = None
    error: str | None = None

    @property
    def migrations_up_to_date(self) -> bool:
        """True only when we know both revisions and they agree.

        Unknown is not treated as fine: an API serving queries against a schema
        it cannot verify is exactly the situation readiness should flag.
        """
        if self.current_revision is None or self.head_revision is None:
            return False
        return self.current_revision == self.head_revision

    @property
    def is_ready(self) -> bool:
        return self.reachable and self.migrations_up_to_date


@lru_cache(maxsize=1)
def head_revision() -> str | None:
    """The newest revision on disk, per the alembic/ directory.

    Read once per process: the scripts ship with the build and do not change
    under a running server, so re-parsing them on every probe is pure cost.
    """
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config(str(_PROJECT_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(_PROJECT_ROOT / "alembic"))
        return ScriptDirectory.from_config(config).get_current_head()
    except Exception:  # noqa: BLE001 - a probe never raises
        return None


async def check_database(engine: AsyncEngine) -> DatabaseHealth:
    """Probe connectivity and compare the applied revision against head."""
    head = head_revision()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            current = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        # Only the exception class is surfaced; the message can carry the DSN,
        # and the DSN carries the password.
        return DatabaseHealth(reachable=False, head_revision=head, error=type(exc).__name__)

    return DatabaseHealth(reachable=True, current_revision=current, head_revision=head)
