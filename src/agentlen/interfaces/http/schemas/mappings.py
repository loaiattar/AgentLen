"""Wire shapes for the mapping routes (API.md §4, MAPPING_CONTRACT.md §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FieldRuleIn(BaseModel):
    target: str = Field(examples=["external_id"])
    source: str = Field(examples=["$.session_id"])
    required: bool = False
    operators: list[dict[str, Any]] = Field(default_factory=list)


class EntityMappingIn(BaseModel):
    target: str = Field(examples=["session"])
    natural_key: list[str] = Field(examples=[["external_id"]])
    fields: list[FieldRuleIn]
    iterate: str | None = Field(default=None, description="JSONPath for 1 record -> N rows.")
    parent: dict[str, Any] | None = None


class MappingDocumentIn(BaseModel):
    """The document itself, MAPPING_CONTRACT.md §2 — minus the storage metadata
    (id, version, status) the repository owns."""

    source_format: str = Field(examples=["jsonl"])
    entities: list[EntityMappingIn]


class MappingCreateIn(MappingDocumentIn):
    data_source_id: int
    name: str = Field(examples=["tracelab-jsonl"])


class FieldRuleOut(BaseModel):
    target: str
    source: str
    required: bool
    operators: list[dict[str, Any]]


class EntityMappingOut(BaseModel):
    target: str
    natural_key: list[str]
    fields: list[FieldRuleOut]
    iterate: str | None = None
    parent: dict[str, Any] | None = None


class MappingOut(BaseModel):
    id: int
    data_source_id: int
    name: str
    version: int
    source_format: str
    status: str = Field(examples=["active"])
    entities: list[EntityMappingOut]
    created_at: datetime


class ValidationErrorOut(BaseModel):
    code: str = Field(examples=["MAPPING_UNKNOWN_TARGET"])
    field_path: str | None = None
    message: str


class MappingValidateOut(BaseModel):
    valid: bool
    errors: list[ValidationErrorOut]
