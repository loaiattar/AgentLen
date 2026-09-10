"""Validate mappings before creating immutable persisted versions."""

from __future__ import annotations

from dataclasses import replace

from agentlen.application.errors import ConflictError, MappingInvalidError, NotFoundError
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.model.mapping import Mapping
from agentlen.domain.services import mapping_validator


class SaveMapping:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self,
        mapping: Mapping,
        *,
        data_source_id: int | None,
        previous_mapping_id: int | None = None,
    ) -> int:
        errors = mapping_validator.validate(mapping)
        if errors:
            raise MappingInvalidError(
                [{"code": e.code, "field_path": e.field_path, "message": e.message} for e in errors]
            )
        async with self._uow as uow:
            if previous_mapping_id is None:
                if (
                    data_source_id is None
                    or await uow.data_sources.get_by_id(data_source_id) is None
                ):
                    raise NotFoundError("DataSource", data_source_id)
                existing = await uow.mappings.list_records(
                    data_source_id=data_source_id, limit=1000, offset=0
                )
                if any(row["name"] == mapping.name for row in existing):
                    raise ConflictError(
                        f"Un mapping nommé '{mapping.name}' existe déjà pour cette source.",
                        details={"name": mapping.name, "data_source_id": data_source_id},
                    )
                mapping_id = await uow.mappings.save(mapping, data_source_id=data_source_id)
            else:
                current = await uow.mappings.get_by_id(previous_mapping_id)
                if current is None:
                    raise NotFoundError("Mapping", previous_mapping_id)
                current_data_source_id = int(current["data_source_id"])
                if data_source_id is not None and data_source_id != current_data_source_id:
                    raise ConflictError(
                        "Un mapping versionné ne peut pas changer de source de données.",
                        details={
                            "data_source_id": data_source_id,
                            "expected_data_source_id": current_data_source_id,
                        },
                    )
                next_mapping = replace(
                    mapping,
                    name=str(current["name"]),
                    version=int(current["version"]) + 1,
                )
                await uow.mappings.supersede(previous_mapping_id)
                mapping_id = await uow.mappings.save(
                    next_mapping, data_source_id=current_data_source_id
                )
            await uow.commit()
        return mapping_id
