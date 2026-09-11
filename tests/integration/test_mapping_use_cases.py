from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from sqlalchemy import insert, select

from agentlen.application.use_cases.save_mapping import SaveMapping
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

from .conftest import requires_postgres

pytestmark = requires_postgres


async def test_new_version_supersedes_old_row_and_keeps_document_portable(
    clean_db, database_url
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(to_async_url(database_url))
    async with engine.begin() as conn:
        source_id = (
            await conn.execute(
                insert(t.data_source)
                .values(slug="versions", name="Versions")
                .returning(t.data_source.c.id)
            )
        ).scalar_one()
    mapping = Mapping(
        id=uuid4(),
        name="portable",
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(FieldRule(target="external_id", source="$.id"),),
            ),
        ),
    )
    use_case = SaveMapping(SqlAlchemyUnitOfWork(engine))
    first_id = await use_case.execute(mapping, data_source_id=source_id)
    second_id = await use_case.execute(
        replace(mapping, name="ignored", version=99),
        data_source_id=source_id,
        previous_mapping_id=first_id,
    )
    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    select(t.mapping)
                    .where(t.mapping.c.id.in_([first_id, second_id]))
                    .order_by(t.mapping.c.id)
                )
            )
            .mappings()
            .all()
        )
    await engine.dispose()

    assert [(row["version"], row["status"]) for row in rows] == [
        (1, "superseded"),
        (2, "active"),
    ]
    assert "provider" not in str(rows[1]["document"]).lower()
    assert "model" not in str(rows[1]["document"]).lower()
