"""A preview must leave a real database byte-for-byte unchanged.

The in-memory test asserts the same thing, but only the real database can prove
that no repository quietly opened a transaction and committed — an in-memory
double cannot fail that way, so on its own it would not be evidence.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Connection, insert, text
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.use_cases.preview_import import PreviewImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes.file_reader import InMemoryFileReader
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres

PATH = "memory://sample"
RECORDS = [
    {"sid": "a", "tools": [{"name": "Bash"}, {"name": "Read"}]},
    {"sid": "b", "tools": [{"name": "Write"}]},
    {"tools": [{"name": "Bash"}]},
]

MAPPING = Mapping(
    id=uuid4(),
    name="m",
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


def _row_counts(conn: Connection) -> dict[str, int]:
    """Every table in the schema, not a chosen few — the assertion is that
    *nothing* moved."""
    names = [
        r[0]
        for r in conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        )
    ]
    return {
        # noqa justified: the name comes from pg_tables, never from input, and
        # it is quoted. There is no way to reach this from a request.
        n: conn.execute(text(f'SELECT count(*) FROM "{n}"')).scalar_one()  # noqa: S608
        for n in names
    }


@pytest.fixture
def seeded(clean_db: Connection) -> dict[str, Any]:
    conn = clean_db
    source = conn.execute(
        insert(t.data_source).values(slug="tracelab", name="TraceLab").returning(t.data_source.c.id)
    ).scalar_one()
    file_id = conn.execute(
        insert(t.file_upload)
        .values(
            original_name="s.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        .returning(t.file_upload.c.id)
    ).scalar_one()
    from agentlen.infrastructure.persistence.repositories.mapping_codec import (
        mapping_to_document,
    )

    mapping_id = conn.execute(
        insert(t.mapping)
        .values(
            data_source_id=source,
            name="m",
            version=1,
            source_format="jsonl",
            document=mapping_to_document(MAPPING),
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()
    conn.commit()
    return {"file_id": file_id, "mapping_id": mapping_id}


@pytest.fixture
async def preview(database_url: str) -> AsyncIterator[PreviewImport]:
    engine = create_async_engine(to_async_url(database_url))
    yield PreviewImport(SqlAlchemyUnitOfWork(engine), InMemoryFileReader({PATH: RECORDS}))
    await engine.dispose()


async def test_a_preview_changes_no_row_count_anywhere(
    seeded: dict[str, Any], preview: PreviewImport, engine: Any
) -> None:
    with engine.connect() as conn:
        before = _row_counts(conn)

    result = await preview.execute(file_id=seeded["file_id"], mapping_id=seeded["mapping_id"])

    with engine.connect() as conn:
        after = _row_counts(conn)

    assert result.sampled == 3
    assert result.would_import["session"] == 2
    assert before == after, {
        name: (before[name], after[name]) for name in before if before[name] != after[name]
    }


async def test_the_preview_still_reports_what_it_would_do(
    seeded: dict[str, Any], preview: PreviewImport
) -> None:
    """Writing nothing must not mean reporting nothing."""
    result = await preview.execute(file_id=seeded["file_id"], mapping_id=seeded["mapping_id"])

    assert result.would_import["tool_call"] == 3
    assert result.would_reject == 1
    assert any(i.severity == "rejected" for i in result.issues)
    assert any(e.target == "session" and e.rows for e in result.entities)
