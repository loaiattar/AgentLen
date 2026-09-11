"""The application engine: configuration that keeps trace content out of logs."""

from __future__ import annotations

from agentlen.infrastructure.persistence.engine import create_engine


async def test_the_engine_hides_bound_parameters_in_errors() -> None:
    """A DBAPI error otherwise renders `[parameters: ...]`, and the parameters
    of a raw_record insert are the trace payload. Building the engine opens no
    connection, so this needs no database."""
    engine = create_engine("postgresql://agentlen:agentlen@localhost:5432/agentlen")
    try:
        assert engine.sync_engine.hide_parameters is True
    finally:
        await engine.dispose()
