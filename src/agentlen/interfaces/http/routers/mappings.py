"""Mapping routes (API.md §4).

The mapping is the central artefact (MAPPING_CONTRACT.md §1): what lets an
unknown source be imported by configuration, never by code. Reuses the
`mapping_validator` and `MappingRepository` already exercised by
`RunImport`/`PreviewImport` (#43, #46, #51) — nothing here reimplements
validation or storage.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from agentlen.application.errors import NotFoundError
from agentlen.application.use_cases.save_mapping import SaveMapping
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services import mapping_validator
from agentlen.interfaces.http.dependencies import UnitOfWorkDep
from agentlen.interfaces.http.pagination import Paginated, paginate
from agentlen.interfaces.http.schemas.common import Page
from agentlen.interfaces.http.schemas.mappings import (
    MappingCreateIn,
    MappingDocumentIn,
    MappingOut,
    MappingValidateOut,
    ValidationErrorOut,
)

router = APIRouter(prefix="/mappings", tags=["mappings"])


def _to_domain(body: MappingDocumentIn, *, name: str, version: int) -> Mapping:
    """Placeholder id: in-batch correlation only (ADR-012), discarded on save."""
    from uuid import uuid4

    return Mapping(
        id=uuid4(),
        name=name,
        version=version,
        source_format=body.source_format,
        entities=tuple(
            EntityMapping(
                target=e.target,
                natural_key=tuple(e.natural_key),
                iterate=e.iterate,
                parent=e.parent,
                fields=tuple(
                    FieldRule(
                        target=f.target,
                        source=f.source,
                        required=f.required,
                        operators=tuple(f.operators),
                    )
                    for f in e.fields
                ),
            )
            for e in body.entities
        ),
    )


def _to_out(row: dict[str, Any]) -> MappingOut:
    return MappingOut(
        id=row["id"],
        data_source_id=row["data_source_id"],
        name=row["name"],
        version=row["version"],
        source_format=row["source_format"],
        status=row["status"],
        entities=row["document"]["entities"],
        created_at=row["created_at"],
    )


@router.get(
    "", response_model=Page[MappingOut], summary="List mappings, filterable by source and status"
)
async def list_mappings(
    uow: UnitOfWorkDep,
    params: Paginated,
    data_source_id: Annotated[int | None, Query(description="Restrict to one source.")] = None,
    status_: Annotated[
        str | None, Query(alias="status", description="Restrict to one lifecycle status.")
    ] = None,
) -> Page[MappingOut]:
    async with uow:
        rows = await uow.mappings.list_records(
            data_source_id=data_source_id, status=status_, limit=params.limit, offset=params.offset
        )
        total = await uow.mappings.count(data_source_id=data_source_id, status=status_)

    return paginate([_to_out(r) for r in rows], total, params)


@router.post(
    "",
    response_model=MappingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save a mapping — validated before write, 422 with every error otherwise",
)
async def create_mapping(body: MappingCreateIn, uow: UnitOfWorkDep) -> MappingOut:
    mapping = _to_domain(body, name=body.name, version=1)
    new_id = await SaveMapping(uow).execute(mapping, data_source_id=body.data_source_id)
    async with uow:
        row = await uow.mappings.get_by_id(new_id)

    assert row is not None  # just created, in the same transaction
    return _to_out(row)


@router.post(
    "/validate",
    response_model=MappingValidateOut,
    summary="Validate a document without saving it — nothing is written",
)
async def validate_mapping(body: MappingDocumentIn) -> MappingValidateOut:
    mapping = _to_domain(body, name="", version=1)
    errors = mapping_validator.validate(mapping)
    return MappingValidateOut(
        valid=not errors,
        errors=[
            ValidationErrorOut(code=e.code, field_path=e.field_path, message=e.message)
            for e in errors
        ],
    )


@router.get("/{mapping_id}", response_model=MappingOut, summary="The full document")
async def get_mapping(mapping_id: int, uow: UnitOfWorkDep) -> MappingOut:
    async with uow:
        row = await uow.mappings.get_by_id(mapping_id)
    if row is None:
        raise NotFoundError("Mapping", mapping_id)
    return _to_out(row)


@router.put(
    "/{mapping_id}",
    response_model=MappingOut,
    summary="Create version N+1 — the previous version becomes 'superseded'",
)
async def update_mapping(
    mapping_id: int, body: MappingDocumentIn, uow: UnitOfWorkDep
) -> MappingOut:
    new_mapping = _to_domain(body, name="", version=1)
    new_id = await SaveMapping(uow).execute(
        new_mapping, data_source_id=None, previous_mapping_id=mapping_id
    )
    async with uow:
        row = await uow.mappings.get_by_id(new_id)

    assert row is not None  # just created, in the same transaction
    return _to_out(row)
