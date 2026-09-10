"""Wire shapes for the file routes (API.md §2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileUploadOut(BaseModel):
    id: int
    original_name: str = Field(examples=["tracelab_sample.jsonl"])
    format: str = Field(examples=["jsonl"])
    size_bytes: int
    content_hash: str
    already_seen: bool = Field(
        description="True when this content was already stored — the front should "
        "warn before re-running an import on it."
    )
    previous_import_run_ids: list[int] = Field(default_factory=list)


class FieldProfileOut(BaseModel):
    path: str = Field(examples=["$.usage.input_tokens"])
    types: list[str]
    null_ratio: float = Field(ge=0.0, le=1.0)
    distinct_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    min: str | None = None
    max: str | None = None
    examples: list[str]


class FileProfileOut(BaseModel):
    file_id: int
    record_count: int
    sampled_records: int
    fields: list[FieldProfileOut]
