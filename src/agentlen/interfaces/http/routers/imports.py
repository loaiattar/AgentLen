"""Import routes (API.md §5).

`POST /imports` only creates the `import_run` row in `pending` — exactly what
`interfaces/cli/seed.py` does by hand. The worker (issue #55, `PostgresJobQueue`
+ `ImportWorker`, already running via `docker compose up`) claims it and calls
`RunImport` itself; nothing here re-implements that loop.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from agentlen.application.errors import NotFoundError
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.application.use_cases.create_import import CreateImport
from agentlen.application.use_cases.preview_import import PreviewImport
from agentlen.interfaces.http.dependencies import FileReaderDep, UnitOfWorkDep
from agentlen.interfaces.http.pagination import Paginated, paginate
from agentlen.interfaces.http.schemas.common import Page
from agentlen.interfaces.http.schemas.imports import (
    DataSourceRefOut,
    FileRefOut,
    ImportCreateIn,
    ImportCreateOut,
    ImportIssueOut,
    ImportPreviewIn,
    ImportPreviewOut,
    ImportReportOut,
    ImportStatusOut,
    MappingRefOut,
    PreviewEntitiesOut,
    PreviewIssueOut,
)

router = APIRouter(prefix="/imports", tags=["imports"])


async def _to_status_out(row: dict[str, Any], uow: UnitOfWork) -> ImportStatusOut:
    """Three reads on the already-open unit of work: no SQL view joins these
    three tables, and it is not worth one for three scalars (see README)."""
    data_source = await uow.data_sources.get_by_id(row["data_source_id"])
    file_upload = await uow.file_uploads.get_by_id(row["file_upload_id"])
    mapping = await uow.mappings.get(row["mapping_id"])
    assert data_source is not None
    assert file_upload is not None
    assert mapping is not None

    return ImportStatusOut(
        id=row["id"],
        status=row["status"],
        data_source=DataSourceRefOut(id=data_source.id, slug=data_source.slug),
        file=FileRefOut(id=file_upload.id, original_name=file_upload.original_name),
        # `mapping.id` is the domain's in-batch UUID (ADR-012), not the
        # persisted id — the run row already holds the real one.
        mapping=MappingRefOut(id=row["mapping_id"], name=mapping.name, version=mapping.version),
        report=ImportReportOut(
            records_read=row["records_read"],
            records_imported=row["records_imported"],
            records_duplicate=row["records_duplicate"],
            records_rejected=row["records_rejected"],
            fields_missing=row.get("fields_missing"),
        ),
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
    )


@router.post(
    "/preview",
    response_model=ImportPreviewOut,
    summary="Dry-run: transform sampled records, write nothing",
)
async def preview_import(
    body: ImportPreviewIn, reader: FileReaderDep, uow: UnitOfWorkDep
) -> ImportPreviewOut:
    use_case = PreviewImport(uow, reader)
    result = await use_case.execute(
        file_id=body.file_id, mapping_id=body.mapping_id, sample_size=body.sample_size
    )
    return ImportPreviewOut(
        sampled=result.sampled,
        would_import=result.would_import,
        would_reject=result.would_reject,
        entities=[PreviewEntitiesOut(target=e.target, rows=e.rows) for e in result.entities],
        issues=[
            PreviewIssueOut(
                line_number=i.line_number,
                severity=i.severity,
                code=i.code,
                message=i.message,
                field_path=i.field_path,
            )
            for i in result.issues
        ],
    )


@router.post(
    "",
    response_model=ImportCreateOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch an import (asynchronous — poll GET /imports/{id})",
)
async def create_import(body: ImportCreateIn, uow: UnitOfWorkDep) -> ImportCreateOut:
    result = await CreateImport(uow).execute(
        data_source_id=body.data_source_id,
        file_upload_id=body.file_upload_id,
        mapping_id=body.mapping_id,
    )
    return ImportCreateOut(import_run_id=result.import_run_id, status=result.status)


@router.get("", response_model=Page[ImportStatusOut], summary="Import history, most recent first")
async def list_imports(params: Paginated, uow: UnitOfWorkDep) -> Page[ImportStatusOut]:
    async with uow:
        rows = await uow.import_runs.list(limit=params.limit, offset=params.offset)
        total = await uow.import_runs.count()
        items = [await _to_status_out(row, uow) for row in rows]

    return paginate(items, total, params)


@router.get("/{import_run_id}", response_model=ImportStatusOut, summary="Status and full report")
async def get_import(import_run_id: int, uow: UnitOfWorkDep) -> ImportStatusOut:
    async with uow:
        row = await uow.import_runs.get(import_run_id)
        if row is None:
            raise NotFoundError("ImportRun", import_run_id)
        return await _to_status_out(row, uow)


@router.get(
    "/{import_run_id}/issues",
    response_model=Page[ImportIssueOut],
    summary="Rejections, duplicates and warnings, paginated",
)
async def list_import_issues(
    import_run_id: int,
    params: Paginated,
    uow: UnitOfWorkDep,
    severity: Annotated[
        str | None, Query(description="Restrict to one severity: rejected, duplicate or warning.")
    ] = None,
) -> Page[ImportIssueOut]:
    async with uow:
        if await uow.import_runs.get(import_run_id) is None:
            raise NotFoundError("ImportRun", import_run_id)
        issues = await uow.import_issues.list(
            import_run_id=import_run_id,
            severity=severity,
            limit=params.limit,
            offset=params.offset,
        )
        total = await uow.import_issues.count(import_run_id=import_run_id, severity=severity)

    items = [
        ImportIssueOut(
            line_number=r.issue.line_number,
            raw_record_id=r.raw_record_id,
            severity=r.issue.severity,
            code=r.issue.code,
            message=r.issue.message,
            field_path=r.issue.field_path,
        )
        for r in issues
    ]
    return paginate(items, total, params)
