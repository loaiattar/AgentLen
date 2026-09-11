from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentlen.interfaces.http.schemas.mappings import EntityMappingIn, SourceFormat


class ProposalRequest(BaseModel):
    file_id: int
    data_source_id: int | None = None
    provider: str | None = None
    model: str | None = None
    hint: str | None = Field(default=None, max_length=10_000)


class ProposalMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class ProposalPatchRequest(BaseModel):
    name: str
    source_format: SourceFormat
    entities: list[EntityMappingIn]
    mapping_version: str = "1.0"


class ProposalResponse(BaseModel):
    proposal_id: int
    analyzer: dict[str, Any]
    mapping: dict[str, Any]
    validation: dict[str, Any]
    rationale: list[dict[str, Any]]
    ambiguities: list[dict[str, Any]]
    unmapped_fields: list[dict[str, Any]]
