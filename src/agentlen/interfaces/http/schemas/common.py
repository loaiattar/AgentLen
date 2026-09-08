"""Response shapes shared by every router: the error envelope and pagination."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """The inner object of the error envelope (API.md §1)."""

    code: str = Field(
        description="Stable machine-readable code. Safe to branch on in the front.",
        examples=["MAPPING_UNKNOWN_TARGET"],
    )
    message: str = Field(
        description="Human-readable explanation, shown to the user as-is.",
        examples=["Le champ cible 'session.user_email' n'existe pas dans le schéma."],
    )
    field_path: str | None = Field(
        default=None,
        description="Where in the submitted document the problem is.",
        examples=["entities[0].fields[3].target"],
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Extra machine-readable context."
    )


class ErrorResponse(BaseModel):
    """Every error the API emits has this shape. No exceptions."""

    error: ErrorBody


class Page[T](BaseModel):
    """Envelope for every list endpoint.

    `total` is the count *before* limit/offset, so the front can render a pager
    without a second request.
    """

    items: list[T]
    total: int = Field(description="Total matching rows, ignoring limit and offset.")
    limit: int
    offset: int
