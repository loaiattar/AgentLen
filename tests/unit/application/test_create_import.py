from __future__ import annotations

from uuid import uuid4

import pytest

from agentlen.application.errors import ConflictError, ImportInvalidError
from agentlen.application.use_cases.create_import import CreateImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from tests.fakes.repositories import InMemoryUnitOfWork


def _mapping(*, source_format: str = "jsonl") -> Mapping:
    return Mapping(
        id=uuid4(),
        name=f"mapping-{uuid4().hex}",
        version=1,
        source_format=source_format,
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(FieldRule(target="external_id", source="$.id"),),
            ),
        ),
    )


async def _seed(
    uow: InMemoryUnitOfWork, *, mapping_source: int | None = None, mapping_format: str = "jsonl"
) -> tuple[int, int, int]:
    async with uow as transaction:
        source_id = await transaction.data_sources.create(slug="source", name="Source")
        file_record = await transaction.file_uploads.create(
            original_name="source.jsonl",
            storage_path="stored/source.jsonl",
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        mapping_id = await transaction.mappings.save(
            _mapping(source_format=mapping_format),
            data_source_id=mapping_source or source_id,
        )
        await transaction.commit()
    return source_id, file_record.id, mapping_id


async def test_create_import_enqueues_a_coherent_pending_run() -> None:
    uow = InMemoryUnitOfWork()
    source_id, file_id, mapping_id = await _seed(uow)

    created = await CreateImport(uow).execute(
        data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
    )

    assert created.status == "pending"
    assert (await uow.import_runs.get(created.import_run_id))["status"] == "pending"


async def test_create_import_rejects_a_mapping_from_another_source() -> None:
    uow = InMemoryUnitOfWork()
    async with uow as transaction:
        other_source = await transaction.data_sources.create(slug="other", name="Other")
        await transaction.commit()
    source_id, file_id, mapping_id = await _seed(uow, mapping_source=other_source)

    with pytest.raises(ImportInvalidError):
        await CreateImport(uow).execute(
            data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
        )


async def test_create_import_rejects_a_non_active_mapping() -> None:
    uow = InMemoryUnitOfWork()
    source_id, file_id, mapping_id = await _seed(uow)
    await uow.mappings.supersede(mapping_id)

    with pytest.raises(ImportInvalidError) as caught:
        await CreateImport(uow).execute(
            data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
        )

    assert caught.value.details["status"] == "superseded"


async def test_create_import_rejects_a_different_file_format() -> None:
    uow = InMemoryUnitOfWork()
    source_id, file_id, mapping_id = await _seed(uow, mapping_format="csv")

    with pytest.raises(ImportInvalidError) as caught:
        await CreateImport(uow).execute(
            data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
        )

    assert caught.value.details["mapping_format"] == "csv"
    assert caught.value.details["file_format"] == "jsonl"


async def test_same_file_and_mapping_cannot_be_enqueued_twice() -> None:
    uow = InMemoryUnitOfWork()
    source_id, file_id, mapping_id = await _seed(uow)
    first = await CreateImport(uow).execute(
        data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
    )

    with pytest.raises(ConflictError) as caught:
        await CreateImport(uow).execute(
            data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
        )

    assert caught.value.details["import_run_id"] == first.import_run_id
    assert len(uow._store.import_runs) == 1
