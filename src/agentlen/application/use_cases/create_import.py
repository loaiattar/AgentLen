"""Validate and enqueue one coherent import run."""

from __future__ import annotations

from dataclasses import dataclass

from agentlen.application.errors import ConflictError, ImportInvalidError, NotFoundError
from agentlen.application.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreatedImport:
    import_run_id: int
    status: str = "pending"


class CreateImport:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, *, data_source_id: int, file_upload_id: int, mapping_id: int
    ) -> CreatedImport:
        async with self._uow as uow:
            if await uow.data_sources.get_by_id(data_source_id) is None:
                raise NotFoundError("DataSource", data_source_id)
            stored_file = await uow.file_uploads.get_by_id(file_upload_id)
            if stored_file is None:
                raise NotFoundError("FileUpload", file_upload_id)
            mapping = await uow.mappings.get_by_id(mapping_id)
            if mapping is None:
                raise NotFoundError("Mapping", mapping_id)

            if mapping["data_source_id"] != data_source_id:
                raise ImportInvalidError(
                    "Le mapping appartient à une autre source de données.",
                    details={
                        "data_source_id": data_source_id,
                        "mapping_data_source_id": mapping["data_source_id"],
                        "mapping_id": mapping_id,
                    },
                )
            if mapping["status"] != "active":
                raise ImportInvalidError(
                    "Seul un mapping actif peut être utilisé pour un import.",
                    details={"mapping_id": mapping_id, "status": mapping["status"]},
                )
            if mapping["source_format"] != stored_file.format:
                raise ImportInvalidError(
                    "Le format du mapping ne correspond pas au format du fichier.",
                    details={
                        "mapping_id": mapping_id,
                        "mapping_format": mapping["source_format"],
                        "file_upload_id": file_upload_id,
                        "file_format": stored_file.format,
                    },
                )

            previous = await uow.import_runs.get_by_file_and_mapping(
                file_upload_id=file_upload_id, mapping_id=mapping_id
            )
            if previous is not None:
                raise ConflictError(
                    "Ce fichier a déjà été importé avec ce mapping.",
                    details={
                        "file_upload_id": file_upload_id,
                        "mapping_id": mapping_id,
                        "import_run_id": previous["id"],
                        "status": previous["status"],
                    },
                )

            run_id = await uow.import_runs.create(
                data_source_id=data_source_id,
                file_upload_id=file_upload_id,
                mapping_id=mapping_id,
            )
            await uow.commit()
        return CreatedImport(import_run_id=run_id)
