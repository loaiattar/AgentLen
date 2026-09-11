from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from agentlen.infrastructure.ai.factory import supported_providers

#: Free text, but one token: no whitespace, no control character (Postgres
#: refuses NUL in the `text` column that stores it with the proposal).
_MODEL_ID = re.compile(r"[^\x00-\x20\x7f]+")


class ProposalRequest(BaseModel):
    file_id: int
    data_source_id: int | None = None
    provider: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "`null` uses the configured provider. Otherwise one of: "
            f"{', '.join(supported_providers())}. AI_BASE_URL applies to the "
            "configured provider only; any other one uses its default endpoint."
        ),
    )
    model: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        validate_default=True,
        description=(
            "`null` uses the configured model. Required when `provider` is set. "
            "Free text: each host publishes its own model ids."
        ),
    )
    hint: str | None = None

    @field_validator("provider")
    @classmethod
    def _registered_provider(cls, value: str | None) -> str | None:
        """Refused before any analyzer is built; the factory answered 502."""
        supported = supported_providers()
        if value is not None and value not in supported:
            raise PydanticCustomError(
                "unsupported_provider",
                "Fournisseur '{provider}' inconnu. Valeurs acceptées : {supported}.",
                {"provider": value, "supported": ", ".join(supported)},
            )
        return value

    @field_validator("model")
    @classmethod
    def _model_goes_with_provider(cls, value: str | None, info: ValidationInfo) -> str | None:
        """A model id belongs to one provider: the configured one is no use to another."""
        if value is None:
            if info.data.get("provider") is not None:
                raise PydanticCustomError(
                    "model_required",
                    "Préciser `model` avec `provider` : un identifiant de modèle "
                    "appartient à un seul fournisseur.",
                )
            return value
        if not _MODEL_ID.fullmatch(value):
            raise PydanticCustomError(
                "invalid_model",
                "`model` ne peut contenir ni espace ni caractère de contrôle.",
            )
        return value


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
