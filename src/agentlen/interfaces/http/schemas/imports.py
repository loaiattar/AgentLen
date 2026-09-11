"""Wire shapes for the import routes (API.md §5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from agentlen.application.use_cases.preview_import import (
    DEFAULT_SAMPLE_SIZE,
    MAX_SAMPLE_SIZE,
)


class ImportPreviewIn(BaseModel):
    file_id: int
    mapping_id: int
    # Bounded at both ends: the preview reads this many records server-side, so
    # an unbounded value is work the caller can ask for for free. `max` on the
    # front's number input is advisory — a typed value above it is submitted —
    # so the limit has to live here. See MAX_SAMPLE_SIZE in `preview_import`.
    sample_size: int = Field(default=DEFAULT_SAMPLE_SIZE, ge=1, le=MAX_SAMPLE_SIZE)


class PreviewEntitiesOut(BaseModel):
    target: str = Field(examples=["session"])
    rows: list[dict[str, Any]]


class PreviewIssueOut(BaseModel):
    line_number: int | None = None
    severity: str
    code: str
    message: str
    field_path: str | None = None


class ImportPreviewOut(BaseModel):
    sampled: int
    would_import: dict[str, int]
    would_reject: int
    entities: list[PreviewEntitiesOut]
    issues: list[PreviewIssueOut]


class ImportCreateIn(BaseModel):
    data_source_id: int
    file_upload_id: int
    mapping_id: int


class ImportCreateOut(BaseModel):
    import_run_id: int
    status: str = Field(examples=["pending"])


class ImportReportOut(BaseModel):
    records_read: int
    records_imported: int
    records_duplicate: int
    records_rejected: int
    fields_missing: dict[str, int] | None = Field(
        default=None,
        description="Field -> how many records were missing it. Feeds the data-quality view.",
    )


class DataSourceRefOut(BaseModel):
    id: int
    slug: str


class FileRefOut(BaseModel):
    id: int
    original_name: str


class MappingRefOut(BaseModel):
    id: int
    name: str
    version: int


class ImportStatusOut(BaseModel):
    id: int
    status: str
    data_source: DataSourceRefOut
    file: FileRefOut
    mapping: MappingRefOut
    report: ImportReportOut
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ImportIssueOut(BaseModel):
    line_number: int | None = None
    severity: str
    code: str
    message: str
    field_path: str | None = None
