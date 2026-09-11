"""Alembic environment.

Reads the database URL from the environment rather than alembic.ini, so no
credentials are ever committed. Targets the metadata defined in
``infrastructure/persistence/tables.py`` — that module stays the single
source of truth for the schema, and autogenerate diffs against it.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from agentlen.infrastructure.persistence.engine import get_database_url, to_sync_url
from agentlen.infrastructure.persistence.tables import metadata
from alembic import context

config = context.config

if config.config_file_name is not None:
    # `disable_existing_loggers` defaults to True, which switches off every
    # logger created before this line — including the application's own, since
    # they exist as soon as their module is imported. Migrations run in-process
    # here (the test fixtures, `seed`), so the default left `agentlen.worker`
    # silent for the rest of the process: `pytest -q` over the whole suite was
    # red because one worker test could no longer see its own log record, while
    # the same test passed alone.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# A caller (the test suite, a script) may have set the URL programmatically
# on the Config; that wins. Otherwise fall back to the environment.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", to_sync_url(get_database_url()))
else:
    config.set_main_option(
        "sqlalchemy.url", to_sync_url(config.get_main_option("sqlalchemy.url", ""))
    )

target_metadata = metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting — used to version the DDL."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
