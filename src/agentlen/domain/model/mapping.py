from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class FieldRule:
    """Describes how to map one source field to one target field."""

    target: str                      # e.g. 'external_id', 'duration_ms'
    source: str                      # JSONPath e.g. '$.session_id'
    required: bool = False
    operators: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Ensure operators is always a tuple (hashable) even if passed as list
        object.__setattr__(self, "operators", tuple(self.operators))


@dataclass(frozen=True)
class EntityMapping:
    """Describes how to extract one target entity from source records."""

    target: str                      # 'session', 'model_call', 'tool_call'
    natural_key: tuple[str, ...]     # field names used for deduplication
    fields: tuple[FieldRule, ...]
    iterate: str | None = None       # JSONPath for nested lists (1 record → N rows)
    parent: dict[str, Any] | None = None  # {'entity': 'session', 'via': 'external_id'}

    def __post_init__(self) -> None:
        object.__setattr__(self, "natural_key", tuple(self.natural_key))
        object.__setattr__(self, "fields", tuple(self.fields))

    VALID_TARGETS = frozenset({"session", "model_call", "tool_call"})

    def validate_target(self) -> None:
        if self.target not in self.VALID_TARGETS:
            raise ValueError(
                f"Unknown entity target '{self.target}'. "
                f"Must be one of {sorted(self.VALID_TARGETS)}."
            )


@dataclass(frozen=True)
class Mapping:
    """A versioned, reusable import configuration for one data source format."""

    id: UUID
    name: str
    version: int
    source_format: str               # 'jsonl', 'csv', 'parquet'
    entities: tuple[EntityMapping, ...]

    VALID_FORMATS = frozenset({"jsonl", "csv", "parquet"})

    def __post_init__(self) -> None:
        object.__setattr__(self, "entities", tuple(self.entities))
        if self.source_format not in self.VALID_FORMATS:
            raise ValueError(
                f"Unsupported source format '{self.source_format}'. "
                f"Must be one of {sorted(self.VALID_FORMATS)}."
            )


@dataclass(frozen=True)
class MappingProposal:
    """A mapping document proposed by the AI agent, before user validation."""

    mapping: Mapping
    rationale: tuple[dict[str, Any], ...]      # [{'target': ..., 'confidence': ..., 'explanation': ...}]
    ambiguities: tuple[dict[str, Any], ...]    # [{'field': ..., 'question': ..., 'options': [...]}]
    unmapped_fields: tuple[dict[str, Any], ...]  # [{'path': ..., 'reason': ...}]
    analyzer_descriptor: dict[str, Any]        # {'provider': ..., 'model': ..., 'prompt_version': ...}

    def __post_init__(self) -> None:
        object.__setattr__(self, "rationale", tuple(self.rationale))
        object.__setattr__(self, "ambiguities", tuple(self.ambiguities))
        object.__setattr__(self, "unmapped_fields", tuple(self.unmapped_fields))
