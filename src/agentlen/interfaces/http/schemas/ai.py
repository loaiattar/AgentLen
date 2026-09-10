from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProposalRequest(BaseModel):
    file_id: int
    data_source_id: int | None = None
    provider: str | None = None
    model: str | None = None
    hint: str | None = None


class ProposalMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class ProposalPatchRequest(BaseModel):
    name: str
    source_format: Literal["jsonl", "csv", "parquet"]
    entities: list[dict[str, Any]]
    mapping_version: str = "1.0"


class ProposalResponse(BaseModel):
    proposal_id: int
    analyzer: dict[str, Any]
    mapping: dict[str, Any]
    validation: dict[str, Any]
    rationale: list[dict[str, Any]]
    ambiguities: list[dict[str, Any]]
    unmapped_fields: list[dict[str, Any]]
