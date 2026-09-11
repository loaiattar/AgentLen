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
    ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="null when the scope is empty; absence is not zero coverage.",
    )


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


class PointOut(BaseModel):
    """Common tail of every chart point.

    `filters` is the drill-down payload: replay it on `GET /sessions` and you
    get the rows behind this point. It is never empty — a point the user cannot
    click through to is a dead end (API.md §6).
    """

    filters: dict[str, Any] = Field(
        description="Replayable verbatim on GET /sessions.",
        examples=[{"tool_id": 4, "data_source_id": 3}],
    )


class ActivityPointOut(PointOut):
    day: str = Field(description="Calendar day, UTC.", examples=["2026-08-01"])
    data_source_id: int
    session_count: int
    model_call_count: int
    tool_call_count: int
    input_tokens: int | None
    output_tokens: int | None
    coverage: CoverageOut


class ToolPointOut(PointOut):
    label: str = Field(description="Tool name, ready to display.")
    tool_id: int
    data_source_id: int
    call_count: int
    error_count: int
    error_ratio: float | None = Field(
        description="null when no call has a known status — never 0.0, which "
        "would read as 'observed, no errors'.",
    )
    coverage: CoverageOut


class ModelPointOut(PointOut):
    label: str
    model_id: int | None
    provider_name: str | None
    data_source_id: int
    call_count: int
    input_tokens: int | None
    output_tokens: int | None
    coverage: CoverageOut
    cache_read_tokens: int | None
    cache_coverage: CoverageOut


class QualityPointOut(PointOut):
    import_run_id: int
    data_source_id: int
    status: str
    records_read: int
    records_imported: int
    records_duplicate: int
    records_rejected: int
    issue_count: int
    rejection_ratio: float | None
    fields_missing: dict[str, int]


class PointsOut[T](BaseModel):
    """Envelope for every chart route."""

    points: list[T]
    filters_applied: dict[str, Any]
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-empty when a value must not be read as comparable "
        "across sources. The front is expected to surface these.",
    )
