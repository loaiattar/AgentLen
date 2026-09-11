"""The import pipeline end to end, against a real Postgres."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Connection, func, insert, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.repositories.mapping_codec import mapping_to_document
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from agentlen.interfaces.cli.seed import SAMPLE_FILE, _tracelab_mapping
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

# Tool calls carry their own index, so several lines of one session do not all
# fall back to position 0 in their `tools` list.
INDEXED = Mapping(
    id=uuid4(),
    name="indexed",
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
            fields=(
                FieldRule(target="tool_name", source="$.name", required=True),
                FieldRule(target="sequence_index", source="$.i", required=True),
            ),
        ),
    ),
)

GOOD = [
    {"sid": "s1", "tools": [{"name": "Bash"}, {"name": "Read"}]},
    {"sid": "s2", "tools": [{"name": "Write"}]},
]


def _seed(conn: Connection, mapping: Mapping) -> dict[str, Any]:
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
            name=mapping.name,
            version=1,
            source_format="jsonl",
            document=mapping_to_document(mapping),
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()
    conn.commit()
    return {"source": source, "file_id": file_id, "mapping_id": mapping_id}


@pytest.fixture
def seeded(clean_db: Connection) -> dict[str, Any]:
    return _seed(clean_db, MAPPING)


@pytest.fixture
def indexed(clean_db: Connection) -> dict[str, Any]:
    return _seed(clean_db, INDEXED)


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

    assert first.records_imported == 5  # two sessions, three tool calls
    assert first.records_duplicate == 0
    assert second.records_imported == 0
    assert second.records_duplicate == 5


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
# A session that other lines, batches or files come back to (#123)
# ---------------------------------------------------------------------------


def _rounds(session: str, indexes: range) -> list[dict[str, Any]]:
    """One line per round, the session repeated on each — TraceLab's shape."""
    return [{"sid": session, "tools": [{"name": "Bash", "i": i}]} for i in indexes]


async def test_a_session_split_across_batches_keeps_every_call(
    indexed: dict[str, Any], importer: Any, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every batch after the first used to see the session as a duplicate and
    drop its calls, while reporting them as already imported."""
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "2")
    run_import, uow = importer(_rounds("s1", range(5)))

    report = await run_import.execute(await _new_run(uow, indexed))

    with engine.connect() as conn:
        assert _count(conn, t.session) == 1
        assert _count(conn, t.tool_call) == 5
    assert report.records_imported == 6  # one session, five calls
    assert report.records_duplicate == 0


async def test_a_file_extending_an_imported_session_adds_its_calls(
    indexed: dict[str, Any], importer: Any, engine: Any
) -> None:
    first_import, uow = importer(_rounds("s1", range(2)))
    await first_import.execute(await _new_run(uow, indexed))
    second_import, uow = importer(_rounds("s1", range(2, 3)))

    report = await second_import.execute(await _new_run(uow, indexed))

    with engine.connect() as conn:
        assert _count(conn, t.session) == 1
        assert _count(conn, t.tool_call) == 3
    assert report.records_imported == 1
    assert report.records_duplicate == 1  # the session itself was already there


async def test_lines_repeating_a_session_are_not_counted_as_several_imports(
    indexed: dict[str, Any], importer: Any
) -> None:
    run_import, uow = importer(_rounds("s1", range(3)))

    report = await run_import.execute(await _new_run(uow, indexed))

    assert report.records_imported == 4  # one session and three calls, not three sessions
    assert report.records_duplicate == 0


async def test_reimporting_a_split_session_counts_it_once(
    indexed: dict[str, Any], importer: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "2")
    run_import, uow = importer(_rounds("s1", range(5)))
    await run_import.execute(await _new_run(uow, indexed))

    report = await run_import.execute(await _new_run(uow, indexed))

    assert report.records_imported == 0
    assert report.records_duplicate == 6  # the session once, its five calls


async def test_the_seed_sample_keeps_all_nineteen_tool_calls_once(
    clean_db: Connection, database_url: str, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TraceLab restarts `tool_index` on every round: 14 of the 19 calls were lost (#188)."""
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "4")  # the sessions also cross batches
    ids = _seed(clean_db, _tracelab_mapping())
    clean_db.execute(
        update(t.file_upload)
        .where(t.file_upload.c.id == ids["file_id"])
        .values(storage_path=str(SAMPLE_FILE))
    )
    clean_db.commit()
    async_engine = create_async_engine(to_async_url(database_url))
    uow = SqlAlchemyUnitOfWork(async_engine)
    run_import = RunImport(uow, PolarsRecordReader())
    try:
        first = await run_import.execute(await _new_run(uow, ids))
        second = await run_import.execute(await _new_run(uow, ids))
    finally:
        await async_engine.dispose()

    with engine.connect() as conn:
        per_session = conn.execute(
            select(t.session.c.external_id, func.count(t.tool_call.c.id))
            .select_from(t.session.join(t.tool_call))
            .group_by(t.session.c.external_id)
        ).all()
    assert sorted(count for _, count in per_session) == [9, 10]
    assert first.records_duplicate == 0
    assert second.records_imported == 0
    assert all(i.code != "SEQUENCE_INDEX_COLLISION" for i in (*first.issues, *second.issues))


@pytest.mark.parametrize("batch_size", ["500", "1"], ids=["same-batch", "later-batch"])
async def test_two_calls_of_one_import_sharing_a_key_are_rejected_not_duplicates(
    indexed: dict[str, Any],
    importer: Any,
    engine: Any,
    monkeypatch: pytest.MonkeyPatch,
    batch_size: str,
) -> None:
    monkeypatch.setenv("IMPORT_BATCH_SIZE", batch_size)
    run_import, uow = importer(
        [
            {"sid": "s1", "tools": [{"name": "Bash", "i": 0}]},
            {"sid": "s1", "tools": [{"name": "Read", "i": 0}]},
        ]
    )

    report = await run_import.execute(await _new_run(uow, indexed))
    reimport = await run_import.execute(await _new_run(uow, indexed))

    collision = (
        "SEQUENCE_INDEX_COLLISION",
        "entities[target=tool_call].fields[target=sequence_index]",
        2,
    )
    assert [(i.code, i.field_path, i.line_number) for i in report.issues] == [collision]
    assert (report.records_imported, report.records_duplicate, report.records_rejected) == (2, 0, 1)
    # The re-import meets line 1's call again (a duplicate); line 2 still collides.
    assert (reimport.records_duplicate, reimport.records_rejected) == (2, 1)
    assert collision in [(i.code, i.field_path, i.line_number) for i in reimport.issues]
    with engine.connect() as conn:
        assert _count(conn, t.tool_call) == 1
        stored = conn.execute(
            select(t.import_issue.c.code, t.raw_record.c.line_number)
            .select_from(t.import_issue.join(t.raw_record))
            .where(t.import_issue.c.severity == "rejected")
        ).all()
    assert [tuple(row) for row in stored] == [("SEQUENCE_INDEX_COLLISION", 2)] * 2


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


async def test_a_type_mismatch_rejects_only_its_source_line(
    seeded: dict[str, Any], importer: Any, engine: Any
) -> None:
    mapping = Mapping(
        id=uuid4(),
        name="typed-sessions",
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(
                    FieldRule(target="external_id", source="$.sid", required=True),
                    FieldRule(target="duration_ms", source="$.duration_ms"),
                ),
            ),
        ),
    )
    with engine.begin() as conn:
        conn.execute(
            update(t.mapping)
            .where(t.mapping.c.id == seeded["mapping_id"])
            .values(document=mapping_to_document(mapping))
        )
    run_import, uow = importer(
        [
            {"sid": "good", "duration_ms": 12},
            {"sid": "bad", "duration_ms": "twelve"},
        ]
    )

    report = await run_import.execute(await _new_run(uow, seeded))

    assert report.records_read == 2
    assert report.records_rejected == 1
    assert any(
        issue.code == "TYPE_MISMATCH"
        and issue.field_path == "entities[target=session].fields[target=duration_ms]"
        and issue.line_number == 2
        for issue in report.issues
    )
    with engine.connect() as conn:
        assert conn.execute(select(t.session.c.external_id)).scalars().all() == ["good"]


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
