"""Refuse an incoherent import before it is queued.

`POST /imports` used to check only that the three identifiers existed. Each
resource being valid on its own says nothing about them going together: a
mapping belonging to another source, a superseded one, or one written for
another file format were all accepted, and the run was then attributed to one
source while being read with another's rules.

That matters more than it looks. `session` is unique on
`(data_source_id, external_id)`, so the source is part of a session's identity
— importing under the wrong one deduplicates in the wrong namespace, and the
rows land under a provenance that is simply false.
"""

from __future__ import annotations

from typing import Any

from agentlen.application.errors import (
    ConflictError,
    ImportRequestInvalidError,
    NotFoundError,
)
from agentlen.application.ports.unit_of_work import UnitOfWork

#: Statuses that make a second run of the same file with the same mapping
#: pointless rather than useful. `failed`, `partial` and `cancelled` are left
#: out on purpose: re-running after a failure is the recovery path, and the
#: import engine is idempotent, so replaying costs a scan and writes nothing
#: that is already there.
BLOCKING_STATUSES = frozenset({"pending", "running", "succeeded"})


class CreateImport:
    """Validate the request, then queue the run."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, data_source_id: int, file_upload_id: int, mapping_id: int) -> int:
        async with self._uow as uow:
            if await uow.data_sources.get_by_id(data_source_id) is None:
                raise NotFoundError("DataSource", data_source_id)

            file_upload = await uow.file_uploads.get_by_id(file_upload_id)
            if file_upload is None:
                raise NotFoundError("FileUpload", file_upload_id)

            mapping = await uow.mappings.get_by_id(mapping_id)
            if mapping is None:
                raise NotFoundError("Mapping", mapping_id)

            _check_same_source(mapping, data_source_id)
            _check_active(mapping)
            _check_format(mapping, file_upload.format)
            await _check_not_already_run(uow, file_upload_id, mapping_id)

            run_id = await uow.import_runs.create(
                data_source_id=data_source_id,
                file_upload_id=file_upload_id,
                mapping_id=mapping_id,
            )
            await uow.commit()
        return run_id


def _check_same_source(mapping: dict[str, Any], data_source_id: int) -> None:
    mapping_source = int(mapping["data_source_id"])
    if mapping_source != data_source_id:
        raise ImportRequestInvalidError(
            "MAPPING_SOURCE_MISMATCH",
            f"Le mapping '{mapping['name']}' appartient à la source "
            f"{mapping_source}, pas à la source {data_source_id}.",
            details={
                "mapping_id": int(mapping["id"]),
                "mapping_data_source_id": mapping_source,
                "data_source_id": data_source_id,
            },
        )


def _check_active(mapping: dict[str, Any]) -> None:
    status = str(mapping["status"])
    if status != "active":
        raise ImportRequestInvalidError(
            "MAPPING_NOT_ACTIVE",
            f"Le mapping '{mapping['name']}' v{mapping['version']} est "
            f"'{status}' : une version remplacée ne peut pas servir à un "
            f"nouvel import.",
            details={"mapping_id": int(mapping["id"]), "status": status},
        )


def _check_format(mapping: dict[str, Any], file_format: str) -> None:
    mapping_format = str(mapping["source_format"])
    if mapping_format != file_format:
        raise ImportRequestInvalidError(
            "MAPPING_FORMAT_MISMATCH",
            f"Le mapping lit du '{mapping_format}', le fichier est du '{file_format}'.",
            details={"mapping_format": mapping_format, "file_format": file_format},
        )


async def _check_not_already_run(uow: UnitOfWork, file_upload_id: int, mapping_id: int) -> None:
    """API.md §1: 409 when this file has already been imported with this mapping.

    Bounded to `BLOCKING_STATUSES`. Sending the same body twice used to queue
    two runs, which is the case this closes. But refusing every repeat would
    also remove the recovery path — a run killed mid-import leaves `failed`,
    and the operator has to be able to launch it again.
    """
    for run_id in await uow.file_uploads.import_run_ids(file_upload_id):
        run = await uow.import_runs.get(run_id)
        if run is None:
            continue
        if int(run["mapping_id"]) == mapping_id and str(run["status"]) in BLOCKING_STATUSES:
            raise ConflictError(
                f"Ce fichier a déjà été importé avec ce mapping (run {run_id}, "
                f"statut '{run['status']}').",
                details={
                    "import_run_id": run_id,
                    "status": str(run["status"]),
                    "mapping_id": mapping_id,
                },
            )
