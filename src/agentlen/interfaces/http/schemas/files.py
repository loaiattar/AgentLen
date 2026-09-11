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
        description=(
            "True when this content was already stored. It answers a question "
            "about the *content hash*, not about imports: an upload of a file "
            "that was stored but never imported comes back true, with an empty "
            "`previous_import_run_ids`. On `GET /files/{id}` the file is stored "
            "by definition, so the flag is always true there and carries no "
            "signal. To ask whether importing again would create duplicates, "
            "read `previous_import_run_ids`."
        )
    )
    previous_import_run_ids: list[int] = Field(
        default_factory=list,
        description=(
            "The runs that already imported this content. Empty means no import "
            "has used it, whatever `already_seen` says."
        ),
    )


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
