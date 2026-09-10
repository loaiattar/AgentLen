"""File routes (API.md §2).

The second half of #50: an uploaded file becomes a `file_upload` row, then a
profile the mapping agent can read — on top of `/data-sources`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, status
from fastapi import UploadFile as HttpUploadFile

from agentlen.application.errors import NotFoundError
from agentlen.application.use_cases.profile_file import ProfileFile, ProfileFileCommand
from agentlen.application.use_cases.upload_file import UploadFile as UploadFileUseCase
from agentlen.application.use_cases.upload_file import UploadResult
from agentlen.domain.model.profile import FileProfile
from agentlen.interfaces.http.dependencies import FileProfilerDep, FileStorageDep, UnitOfWorkDep
from agentlen.interfaces.http.schemas.files import FieldProfileOut, FileProfileOut, FileUploadOut

router = APIRouter(prefix="/files", tags=["files"])

#: Matches LocalFileStorage's own read granularity — no reason for the two
#: layers to disagree on how much of the upload sits in memory at once.
_CHUNK_SIZE = 1024 * 1024


async def _chunks(upload: HttpUploadFile) -> AsyncIterator[bytes]:
    while chunk := await upload.read(_CHUNK_SIZE):
        yield chunk


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
)
async def create_file(
    file: HttpUploadFile, storage: FileStorageDep, uow: UnitOfWorkDep
) -> FileUploadOut:
    use_case = UploadFileUseCase(storage, uow)
    result = await use_case.execute(_chunks(file), original_name=file.filename or "upload")
    return _to_upload_out(result)


@router.get("/{file_id}", response_model=FileUploadOut, summary="A file's metadata")
async def get_file(file_id: int, uow: UnitOfWorkDep) -> FileUploadOut:
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
        already_seen=len(runs) > 0,
        previous_import_run_ids=runs,
    )


@router.post(
    "/{file_id}/profile",
    response_model=FileProfileOut,
    summary="Profile a stored file: types, cardinality, null ratio, examples",
)
async def profile_file(
    file_id: int, profiler: FileProfilerDep, uow: UnitOfWorkDep
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
