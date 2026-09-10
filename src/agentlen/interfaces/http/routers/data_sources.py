"""Data source routes (API.md §2).

The first half of the import journey: declaring where data comes from, before
`files.py` (issue #50's other half) accepts an upload against one of these.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from agentlen.application.dto.persistence import DataSourceRecord
from agentlen.application.errors import ConflictError
from agentlen.interfaces.http.dependencies import UnitOfWorkDep
from agentlen.interfaces.http.schemas.data_sources import DataSourceCreateIn, DataSourceOut

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


def _to_out(record: DataSourceRecord) -> DataSourceOut:
    assert record.created_at is not None  # always set by the database on insert
    return DataSourceOut(
        id=record.id,
        slug=record.slug,
        name=record.name,
        description=record.description,
        url=record.url,
        license=record.license,
        dataset_version=record.dataset_version,
        retrieved_at=record.retrieved_at,
        created_at=record.created_at,
    )


@router.get(
    "",
    response_model=list[DataSourceOut],
    summary="Every declared data source, with its version and retrieval date",
)
async def list_data_sources(uow: UnitOfWorkDep) -> list[DataSourceOut]:
    async with uow:
        records = await uow.data_sources.list()
    return [_to_out(r) for r in records]


@router.post(
    "",
    response_model=DataSourceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Declare a new data source",
    responses={409: {"description": "A data source with this slug already exists."}},
)
async def create_data_source(body: DataSourceCreateIn, uow: UnitOfWorkDep) -> DataSourceOut:
    async with uow:
        if await uow.data_sources.get_by_slug(body.slug) is not None:
            raise ConflictError(
                f"Un data source avec le slug '{body.slug}' existe déjà.",
                details={"slug": body.slug},
            )

        new_id = await uow.data_sources.create(
            slug=body.slug,
            name=body.name,
            description=body.description,
            url=body.url,
            license=body.license,
            dataset_version=body.dataset_version,
            retrieved_at=body.retrieved_at,
        )
        await uow.commit()
        record = await uow.data_sources.get_by_id(new_id)

    assert record is not None  # just created, in the same transaction
    return _to_out(record)
