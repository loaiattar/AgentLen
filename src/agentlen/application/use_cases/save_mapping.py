"""Validate mappings before creating immutable persisted versions."""

from __future__ import annotations

from dataclasses import replace

from agentlen.application.errors import ConflictError, MappingInvalidError, NotFoundError
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.model.mapping import Mapping
from agentlen.domain.services import mapping_validator


def _validate(mapping: Mapping) -> None:
    errors = mapping_validator.validate(mapping)
    if errors:
        raise MappingInvalidError(
            [{"code": e.code, "field_path": e.field_path, "message": e.message} for e in errors]
        )


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
        if previous_mapping_id is None:
            # Validated before the transaction is even opened. On the create
            # path the caller supplies the real name and version, so there is
            # nothing to resolve first — and an invalid document must come back
            # 422 without a database round trip, which is what
            # `test_creating_an_invalid_mapping_is_422_before_touching_the_database`
            # pins down by running against an unreachable database. The version
            # path cannot do the same: it has to read the previous row to know
            # what it is validating. See the comment on `_validate(next_mapping)`.
            _validate(mapping)
        async with self._uow as uow:
            if previous_mapping_id is None:
                if (
                    data_source_id is None
                    or await uow.data_sources.get_by_id(data_source_id) is None
                ):
                    raise NotFoundError("DataSource", data_source_id)
                if await uow.mappings.name_exists(data_source_id=data_source_id, name=mapping.name):
                    raise ConflictError(
                        f"Un mapping nommé '{mapping.name}' existe déjà pour cette source.",
                        details={"name": mapping.name, "data_source_id": data_source_id},
                    )
                mapping_id = await uow.mappings.save(mapping, data_source_id=data_source_id)
            else:
                current = await uow.mappings.get_by_id_for_update(previous_mapping_id)
                if current is None:
                    raise NotFoundError("Mapping", previous_mapping_id)
                if current["status"] != "active":
                    latest = await uow.mappings.latest_version(
                        data_source_id=int(current["data_source_id"]), name=str(current["name"])
                    )
                    raise ConflictError(
                        "Seul un mapping actif peut être versionné.",
                        details={
                            "mapping_id": previous_mapping_id,
                            "status": current["status"],
                            "name": current["name"],
                            "version": current["version"],
                            "latest_version": latest,
                        },
                    )
                current_data_source_id = int(current["data_source_id"])
                if data_source_id is not None and data_source_id != current_data_source_id:
                    raise ConflictError(
                        "Un mapping versionné ne peut pas changer de source de données.",
                        details={
                            "data_source_id": data_source_id,
                            "expected_data_source_id": current_data_source_id,
                        },
                    )
                name = str(current["name"])
                current_version = int(current["version"])
                # The version is derived from the highest one stored under this
                # name, never from the row the caller happened to name. Two PUTs
                # against v1 both computed v1 + 1 and the second violated
                # `uq_mapping_name_version` — an unhandled IntegrityError, so a
                # 500 on an ordinary double click.
                #
                # Naming a superseded version is refused rather than quietly
                # rebased onto the newest one: the caller was editing a document
                # that someone has since replaced, and silently versioning it
                # would overwrite that work without anyone noticing.
                next_mapping = replace(
                    mapping,
                    name=name,
                    version=current_version + 1,
                )
                # Validated only now, and on `next_mapping`. The caller cannot
                # know the name or the version of the version it is creating,
                # so `update_mapping` passes placeholders (`name=""`,
                # `version=1`); validating before this `replace` checked the
                # placeholders rather than the real values, and turned a
                # `PUT /mappings/{unknown id}` carrying an invalid document
                # into a 422 where the caller should see a 404.
                _validate(next_mapping)
                await uow.mappings.supersede(previous_mapping_id)
                mapping_id = await uow.mappings.save(
                    next_mapping, data_source_id=current_data_source_id
                )
            await uow.commit()
        return mapping_id
