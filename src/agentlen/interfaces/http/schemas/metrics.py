"""Wire shapes for the metrics routes (API.md §7)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CoverageOut(BaseModel):
    """How much of the scope actually carried the value.

    The front is expected to show a partial-coverage indicator whenever
    `ratio < 1`: a number computed from 88% of the rows is not the same claim
    as one computed from all of them.
    """

    present: int = Field(description="Records that carried the value.")
    total: int = Field(description="Records in scope.")
    ratio: float = Field(ge=0.0, le=1.0)


class MetricOut(BaseModel):
    key: str = Field(examples=["avg_session_duration_ms"])
    value: float | int | None = Field(
        description="null means unavailable — never a substitute for 0.",
    )
    unit: str = Field(examples=["ms"])
    coverage: CoverageOut
    warning: str | None = Field(
        default=None,
        description="Set when the indicator must not be read as comparable.",
    )


class OverviewOut(BaseModel):
    filters_applied: dict[str, Any] = Field(
        description="Echo of the active filters, replayable on GET /sessions."
    )
    metrics: list[MetricOut]


class DefinitionOut(BaseModel):
    """One indicator's published definition."""

    key: str
    label: str
    unit: str
    formula: str
    scope: str
    missing_policy: str = Field(description="What the indicator does when the data is absent.")
    comparability: Literal["cross_source", "per_source_only"]


class DefinitionsOut(BaseModel):
    definitions: list[DefinitionOut]
