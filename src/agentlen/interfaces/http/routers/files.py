"""File routes (API.md §2).

The second half of #50: an uploaded file becomes a `file_upload` row, then a
profile the mapping agent can read — on top of `/data-sources`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status

from agentlen.application.errors import NotFoundError
from agentlen.application.use_cases.profile_file import ProfileFile, ProfileFileCommand
from agentlen.application.use_cases.upload_file import UploadFile as UploadFileUseCase
from agentlen.application.use_cases.upload_file import UploadResult
from agentlen.domain.model.profile import FileProfile
from agentlen.interfaces.http.dependencies import FileProfilerDep, FileStorageDep, UnitOfWorkDep
from agentlen.interfaces.http.ids import EntityId
from agentlen.interfaces.http.schemas.files import FieldProfileOut, FileProfileOut, FileUploadOut
from agentlen.interfaces.http.upload_stream import read_file_part

router = APIRouter(prefix="/files", tags=["files"])

#: The body is read by hand (see `create_file`), so FastAPI no longer derives
#: it from a parameter: it is declared here for the OpenAPI document.
_UPLOAD_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}


def _to_upload_out(result: UploadResult) -> FileUploadOut:
    return FileUploadOut(
        id=result.id,
        original_name=result.original_name,
        format=result.format,
        size_bytes=result.size_bytes,
        content_hash=result.content_hash,
        already_seen=result.already_seen,
        previous_import_run_ids=result.previous_import_run_ids,
    )


def _to_profile_out(profile: FileProfile) -> FileProfileOut:
    return FileProfileOut(
        file_id=profile.file_id,
        record_count=profile.record_count,
        sampled_records=profile.sampled_records,
        fields=[
            FieldProfileOut(
                path=f.path,
                types=list(f.types),
                null_ratio=f.null_ratio,
                distinct_ratio=f.distinct_ratio,
                min=f.min_value,
                max=f.max_value,
                examples=list(f.examples),
            )
            for f in profile.fields
        ],
    )


@router.post(
    "",
    response_model=FileUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Deposit a file (multipart/form-data)",
    openapi_extra=_UPLOAD_BODY,
)
async def create_file(
    request: Request, storage: FileStorageDep, uow: UnitOfWorkDep
) -> FileUploadOut:
    # Not an `UploadFile` parameter: FastAPI only calls the route once the whole
    # body sits in a temporary file, so an oversized upload would already be on
    # disk when refused. The body is streamed straight into the storage instead.
    original_name, chunks = await read_file_part(request, max_bytes=storage.max_bytes)
    use_case = UploadFileUseCase(storage, uow)
    result = await use_case.execute(chunks, original_name=original_name or "upload")
    return _to_upload_out(result)


@router.get("/{file_id}", response_model=FileUploadOut, summary="A file's metadata")
async def get_file(file_id: EntityId, uow: UnitOfWorkDep) -> FileUploadOut:
    async with uow:
        record = await uow.file_uploads.get_by_id(file_id)
        if record is None:
            raise NotFoundError("FileUpload", file_id)
        runs = await uow.file_uploads.import_run_ids(file_id)

    return FileUploadOut(
        id=record.id,
        original_name=record.original_name,
        format=record.format,
        size_bytes=record.size_bytes,
        content_hash=record.content_hash,
        # `already_seen` describes an upload: true only when `POST /files`
        # reused a file stored before. Reading metadata uploads nothing, so it
        # is false here. It used to be constant `True`, which made a brand-new
        # file look like a duplicate as soon as the page reloaded. Import
        # history lives in `previous_import_run_ids`, on both routes.
        already_seen=False,
        previous_import_run_ids=runs,
    )


@router.post(
    "/{file_id}/profile",
    response_model=FileProfileOut,
    summary="Profile a stored file: types, cardinality, null ratio, examples",
)
async def profile_file(
    file_id: EntityId, profiler: FileProfilerDep, uow: UnitOfWorkDep
) -> FileProfileOut:
    async with uow:
        record = await uow.file_uploads.get_by_id(file_id)
    if record is None:
        raise NotFoundError("FileUpload", file_id)

    use_case = ProfileFile(profiler)
    profile = await use_case.execute(
        ProfileFileCommand(file_id=file_id, path=record.storage_path, format=record.format)
    )
    return _to_profile_out(profile)
