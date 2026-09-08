from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Comparability = Literal["cross_source", "per_source_only"]


@dataclass(frozen=True)
class MetricDefinition:
    """Describes one dashboard metric: formula, unit, scope, missing-value policy.

    Lives in the domain so the registry and the SQL read model can be
    tested against each other without any infrastructure dependency.
    """

    key: str
    label: str
    unit: str
    formula: str
    scope: str
    missing_policy: str
    comparability: Comparability


@dataclass(frozen=True)
class Coverage:
    """How many records actually contributed to a metric value."""

    present: int  # records with a non-null value
    total: int  # total records in scope

    @property
    def ratio(self) -> float:
        return self.present / self.total if self.total else 0.0


@dataclass(frozen=True)
class MetricValue:
    """One computed metric with its coverage object.

    value is None when the data is genuinely unavailable — never 0.
    """

    key: str
    value: float | int | None  # None = unavailable, not zero
    unit: str
    coverage: Coverage
    warning: str | None = None  # shown when comparability is violated
