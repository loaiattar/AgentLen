"""The migration and the metadata must describe the same schema, both ways."""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Engine, insert, inspect, select, text

from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.tables import ALL_TABLES, metadata
from alembic import command
from tests.integration.conftest import requires_postgres
from tests.integration.test_schema import _provenance

pytestmark = requires_postgres


def _config(engine: Engine) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return cfg


def test_upgrade_then_downgrade_round_trip(engine: Engine) -> None:
    """`upgrade head` then `downgrade base` leaves no table behind.

    Required by DATA_MODEL.md §8. A downgrade that silently no-ops is the
    usual way this breaks, so the assertion is on the resulting schema, not
    on the command exiting zero.
    """
    cfg = _config(engine)

    command.upgrade(cfg, "head")
    after_upgrade = set(inspect(engine).get_table_names())
    for table in ALL_TABLES:
        assert table.name in after_upgrade, f"{table.name} missing after upgrade"

    command.downgrade(cfg, "base")
    after_downgrade = set(inspect(engine).get_table_names())
    leftovers = {t.name for t in ALL_TABLES} & after_downgrade
    assert not leftovers, f"downgrade left tables behind: {sorted(leftovers)}"

    command.upgrade(cfg, "head")


def test_migration_matches_metadata(engine: Engine) -> None:
    """No drift between tables.py and the migration.

    This is the test that stops the classic failure mode: someone edits
    tables.py, forgets the revision, and the schema silently diverges from
    the code that queries it.
    """
    command.upgrade(_config(engine), "head")

    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn, opts={"compare_type": True, "compare_server_default": True}
        )
        diff = compare_metadata(ctx, metadata)

    assert diff == [], f"tables.py and the migration disagree: {diff}"


def test_pending_index_is_partial(engine: Engine) -> None:
    """The import-queue index covers only pending rows.

    A full index here would grow with every historical import while the queue
    only ever scans the pending ones.
    """
    command.upgrade(_config(engine), "head")

    with engine.connect() as conn:
        ddl = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_import_run_pending'")
        ).scalar_one()

    assert "WHERE" in ddl.upper(), f"index is not partial: {ddl}"
    assert "pending" in ddl


def _agent(conn: Connection, name: str, version: str | None = None) -> int:
    return conn.execute(
        insert(t.agent).values(name=name, version=version).returning(t.agent.c.id)
    ).scalar_one()


def test_0004_merges_agents_duplicated_by_a_null_version(clean_db: Connection) -> None:
    """Before 0004, every import stored ('claude-code', NULL) again (issue #137).

    The upgrade keeps the oldest row of each (name, version) group, re-points
    the sessions of the other rows at it, and only then can add the stricter
    constraint. Distinct versions and distinct names are left alone.
    """
    cfg = _config(clean_db.engine)
    command.downgrade(cfg, "0003")

    p = _provenance(clean_db)
    duplicates = [_agent(clean_db, "claude-code") for _ in range(3)]
    versioned = _agent(clean_db, "claude-code", "1.0")
    codex = _agent(clean_db, "codex")
    for index, agent_id in enumerate([*duplicates, versioned, codex]):
        clean_db.execute(
            insert(t.session).values(
                data_source_id=p["data_source_id"],
                import_run_id=p["import_run_id"],
                raw_record_id=p["raw_record_id"],
                external_id=f"s{index}",
                agent_id=agent_id,
            )
        )
    clean_db.commit()

    command.upgrade(cfg, "head")

    # The fixture's transaction is closed by the commit: read on a new connection.
    with clean_db.engine.connect() as conn:
        agents = conn.execute(
            select(t.agent.c.id, t.agent.c.name, t.agent.c.version).order_by(t.agent.c.id)
        ).all()
        sessions = dict(conn.execute(select(t.session.c.external_id, t.session.c.agent_id)).all())
    survivor = duplicates[0]
    assert agents == [
        (survivor, "claude-code", None),
        (versioned, "claude-code", "1.0"),
        (codex, "codex", None),
    ]
    assert sessions == {
        "s0": survivor,
        "s1": survivor,
        "s2": survivor,
        "s3": versioned,
        "s4": codex,
    }
