from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FieldProfile:
    """Statistical profile of one field in a source file."""

    path: str                        # JSONPath e.g. '$.usage.input_tokens'
    types: tuple[str, ...]           # observed types e.g. ('integer', 'null')
    null_ratio: float                # 0.0 – 1.0
    examples: tuple[str, ...]        # sanitized sample values
    min_value: str | None = None
    max_value: str | None = None
    distinct_ratio: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "types", tuple(self.types))
        object.__setattr__(self, "examples", tuple(self.examples))


@dataclass(frozen=True)
class FileProfile:
    """Profile of an entire source file, produced before sending to the AI."""

    file_id: int
    format: str                      # 'jsonl', 'csv', 'parquet'
    record_count: int
    sampled_records: int
    fields: tuple[FieldProfile, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(self.fields))
