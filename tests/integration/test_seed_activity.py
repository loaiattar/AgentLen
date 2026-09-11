"""`make seed` gives the activity series something to draw (#200).

The sample has no flat timestamp on its lines: only its tool calls are dated
(`emitted_at`). Imported with the seed's own mapping, each session must still
land on the day of its earliest call, read here straight from the file.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
from sqlalchemy import Connection, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agentlen.application.dto.dashboard import DashboardFilters
from agentlen.application.use_cases.run_import import RunImport
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.read_models.sql import SqlDashboardQueries
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from agentlen.interfaces.cli.seed import SAMPLE_FILE, _ensure_data_source, _ensure_mapping
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


@pytest.fixture
async def seeded_engine(database_url: str, clean_db: Connection) -> AsyncIterator[AsyncEngine]:
    """An engine on a database holding the sample, imported with the seed mapping.

    The same steps as `make seed`, minus the file storage and the job queue:
    the file is read where it lies, and the import runs in-process.
    """
    engine = create_async_engine(to_async_url(database_url))
    source_id = await _ensure_data_source(engine)
    mapping_id = await _ensure_mapping(engine, data_source_id=source_id)
    async with engine.begin() as conn:
        file_id = (
            await conn.execute(
                insert(t.file_upload)
                .values(
                    original_name=SAMPLE_FILE.name,
                    storage_path=str(SAMPLE_FILE),
                    format="jsonl",
                    size_bytes=SAMPLE_FILE.stat().st_size,
                    content_hash="b" * 64,
                )
                .returning(t.file_upload.c.id)
            )
        ).scalar_one()
    uow = SqlAlchemyUnitOfWork(engine)
    async with uow:
        run_id = await uow.import_runs.create(
            data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
        )
        await uow.commit()
    report = await RunImport(uow, PolarsRecordReader()).execute(run_id)
    assert report.records_rejected == 0
    yield engine
    await engine.dispose()


def _earliest_tool_call_per_session() -> dict[str, datetime]:
    earliest: dict[str, datetime] = {}
    for line in SAMPLE_FILE.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        for tool in record["tools"]:
            at = datetime.fromisoformat(tool["emitted_at"])
            earliest[record["session_id"]] = min(at, earliest.get(record["session_id"], at))
    return earliest


async def test_every_seeded_session_is_dated_by_its_earliest_call(
    seeded_engine: AsyncEngine,
) -> None:
    async with seeded_engine.connect() as conn:
        rows = await conn.execute(select(t.session.c.external_id, t.session.c.started_at))
        started = {external_id: at for external_id, at in rows.all()}

    assert started == _earliest_tool_call_per_session()


async def test_the_seed_fills_the_activity_series(seeded_engine: AsyncEngine) -> None:
    queries = SqlDashboardQueries(seeded_engine)

    points = await queries.activity(DashboardFilters())
    expected = Counter(at.date() for at in _earliest_tool_call_per_session().values())

    assert points, "the activity series is empty after the seed"
    assert {p.day: p.session_count for p in points} == expected
    # Every session is on the series, so /metrics/activity has nothing to warn about.
    overview = await queries.overview(DashboardFilters())
    assert sum(p.session_count for p in points) == overview.session_count
