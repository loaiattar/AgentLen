"""Wire shapes for the data-sources routes (API.md §2)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class DataSourceOut(BaseModel):
    id: int
    slug: str = Field(examples=["tracelab"])
    name: str = Field(examples=["TraceLab"])
    description: str | None = None
    url: str | None = None
    license: str | None = None
    dataset_version: str | None = Field(
        default=None, description="Version or commit of the dataset, as published."
    )
    retrieved_at: date | None = Field(
        default=None, description="When this dataset was fetched — null if unknown."
    )
    created_at: datetime


class DataSourceCreateIn(BaseModel):
    slug: str = Field(examples=["tracelab"])
    name: str = Field(examples=["TraceLab"])
    description: str | None = None
    url: str | None = None
    license: str | None = None
    dataset_version: str | None = None
    retrieved_at: date | None = None
