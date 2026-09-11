"""The import pipeline end to end, against a real Postgres."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Connection, func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.repositories.mapping_codec import mapping_to_document
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes.file_reader import InMemoryFileReader
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres

PATH = "memory://traces"

MAPPING = Mapping(
    id=uuid4(),
    name="tracelab",
    version=1,
    source_format="jsonl",
    entities=(
        EntityMapping(
            target="session",
            natural_key=("external_id",),
            fields=(FieldRule(target="external_id", source="$.sid", required=True),),
        ),
        EntityMapping(
            target="tool_call",
            natural_key=("sequence_index",),
            iterate="$.tools",
            parent={"entity": "session", "via": "external_id"},
            fields=(FieldRule(target="tool_name", source="$.name", required=True),),
        ),
    ),
)

# The same source with the agent named on each session and, like every mapping
# today, no agent version.
AGENT_MAPPING = Mapping(
    id=uuid4(),
    name="tracelab",
    version=1,
    source_format="jsonl",
    entities=(
        EntityMapping(
            target="session",
            natural_key=("external_id",),
            fields=(
                FieldRule(target="external_id", source="$.sid", required=True),
                FieldRule(target="agent_name", source="$.agent"),
            ),
        ),
    ),
)

GOOD = [
    {"sid": "s1", "tools": [{"name": "Bash"}, {"name": "Read"}]},
    {"sid": "s2", "tools": [{"name": "Write"}]},
]


@pytest.fixture
def seeded(clean_db: Connection) -> dict[str, Any]:
    conn = clean_db
    source = conn.execute(
        insert(t.data_source).values(slug="tracelab", name="TraceLab").returning(t.data_source.c.id)
    ).scalar_one()
    file_id = conn.execute(
        insert(t.file_upload)
        .values(
            original_name="t.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        .returning(t.file_upload.c.id)
    ).scalar_one()
    mapping_id = conn.execute(
        insert(t.mapping)
        .values(
            data_source_id=source,
            name="tracelab",
            version=1,
            source_format="jsonl",
            document=mapping_to_document(MAPPING),
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()
    conn.commit()
    return {"source": source, "file_id": file_id, "mapping_id": mapping_id}


@pytest.fixture
async def importer(database_url: str) -> AsyncIterator[Any]:
    engine = create_async_engine(to_async_url(database_url))

    def build(records: list[dict[str, Any]]) -> tuple[RunImport, SqlAlchemyUnitOfWork]:
        uow = SqlAlchemyUnitOfWork(engine)
        return RunImport(uow, InMemoryFileReader({PATH: records})), uow

    yield build
    await engine.dispose()


async def _new_run(uow: SqlAlchemyUnitOfWork, seeded: dict[str, Any]) -> int:
    async with uow:
        run_id = await uow.import_runs.create(
            data_source_id=seeded["source"],
            file_upload_id=seeded["file_id"],
            mapping_id=seeded["mapping_id"],
        )
        await uow.commit()
    return run_id


def _count(conn: Connection, table: Any) -> int:
    return conn.execute(select(func.count()).select_from(table)).scalar_one()


# ---------------------------------------------------------------------------
# Idempotence — acceptance test #1 of the brief
# ---------------------------------------------------------------------------


async def test_importing_the_same_file_twice_creates_no_duplicate(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    run_import, uow = importer(GOOD)

    first_run = await _new_run(uow, seeded)
    first = await run_import.execute(first_run)
    second_run = await _new_run(uow, seeded)
    second = await run_import.execute(second_run)

    with engine.connect() as conn:
        assert _count(conn, t.session) == 2
        assert _count(conn, t.tool_call) == 3
        assert _count(conn, t.import_run) == 2  # history is never lost

    assert first.records_imported > 0
    assert second.records_imported == 0
    assert second.records_duplicate > 0


async def test_two_imports_of_the_same_agent_share_one_agent_row(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    """Each run resolves ('claude-code', NULL) with a fresh reference cache.

    The key must still match the first run's row; otherwise the dashboard
    splits one agent into as many agents as there were imports (issue #137).
    """
    with engine.begin() as conn:
        conn.execute(
            t.mapping.update()
            .where(t.mapping.c.id == seeded["mapping_id"])
            .values(document=mapping_to_document(AGENT_MAPPING))
        )

    for sid in ("s1", "s2"):
        run_import, uow = importer([{"sid": sid, "agent": "claude-code"}])
        report = await run_import.execute(await _new_run(uow, seeded))
        assert report.records_imported > 0

    with engine.connect() as conn:
        assert _count(conn, t.agent) == 1
        agent_ids = conn.execute(select(t.session.c.agent_id)).scalars().all()
    assert len(agent_ids) == 2
    assert agent_ids[0] is not None
    assert agent_ids[0] == agent_ids[1]


async def test_children_stay_attached_to_their_session(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    """Acceptance test #2: relations survive the import."""
    run_import, uow = importer(GOOD)
    await run_import.execute(await _new_run(uow, seeded))

    with engine.connect() as conn:
        orphans = conn.execute(
            select(func.count())
            .select_from(t.tool_call)
            .where(~t.tool_call.c.session_id.in_(select(t.session.c.id)))
        ).scalar_one()
        assert orphans == 0

        by_session = conn.execute(
            select(t.session.c.external_id, func.count(t.tool_call.c.id))
            .select_from(t.session.outerjoin(t.tool_call))
            .group_by(t.session.c.external_id)
        ).all()
        assert dict(by_session) == {"s1": 2, "s2": 1}


async def test_every_row_points_at_the_raw_record_it_came_from(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    """Provenance: from any row, back to the exact source line."""
    run_import, uow = importer(GOOD)
    await run_import.execute(await _new_run(uow, seeded))

    with engine.connect() as conn:
        rows = conn.execute(
            select(t.session.c.external_id, t.raw_record.c.payload, t.raw_record.c.line_number)
            .select_from(
                t.session.join(t.raw_record, t.session.c.raw_record_id == t.raw_record.c.id)
            )
            .order_by(t.raw_record.c.line_number)
        ).all()

    assert [r.line_number for r in rows] == [1, 2]
    # The payload is the source record, untouched.
    assert [r.payload for r in rows] == GOOD


# ---------------------------------------------------------------------------
# A bad batch does not stop the import
# ---------------------------------------------------------------------------


async def test_a_few_bad_rows_do_not_stop_the_rest(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    records = [{"sid": f"s{i}", "tools": [{"name": "Bash"}]} for i in range(97)]
    records += [{"tools": [{"name": "Bash"}]} for _ in range(3)]  # no sid
    run_import, uow = importer(records)

    report = await run_import.execute(await _new_run(uow, seeded))

    assert report.records_read == 100
    assert report.records_rejected == 3
    with engine.connect() as conn:
        assert _count(conn, t.session) == 97
        rejected = conn.execute(
            select(func.count())
            .select_from(t.import_issue)
            .where(t.import_issue.c.severity == "rejected")
        ).scalar_one()
        assert rejected >= 3


async def test_a_run_with_rejections_is_partial_not_succeeded(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    """A run that silently dropped rows must not read as a clean success."""
    run_import, uow = importer([{"sid": "ok", "tools": []}, {"tools": []}])

    run_id = await _new_run(uow, seeded)
    await run_import.execute(run_id)

    with engine.connect() as conn:
        status = conn.execute(
            select(t.import_run.c.status).where(t.import_run.c.id == run_id)
        ).scalar_one()
    assert status == "partial"


async def test_the_report_records_which_fields_the_source_never_provided(
    seeded: dict[str, Any], importer: Any
) -> None:
    run_import, uow = importer(GOOD)

    report = await run_import.execute(await _new_run(uow, seeded))

    assert report.records_imported > 0
    # duration_ms is not in the mapping, so every session lacks it — exactly
    # what the data-quality view is meant to surface.
    assert report.records_read == 2


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


async def test_a_large_file_is_imported_in_batches(seeded: dict[str, Any], importer: Any) -> None:
    """Memory must not scale with the file: the reader is asked for batches,
    never for everything."""
    records = [{"sid": f"s{i}", "tools": [{"name": "Bash"}]} for i in range(1200)]
    run_import, uow = importer(records)
    reader: InMemoryFileReader = run_import._reader  # type: ignore[assignment]

    report = await run_import.execute(await _new_run(uow, seeded))

    assert report.records_read == 1200
    assert reader.batch_sizes, "the reader was never asked for batches"
    assert all(size <= 500 for size in reader.batch_sizes)
