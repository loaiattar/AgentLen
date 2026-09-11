from __future__ import annotations

import asyncio
import re
from pathlib import Path

import polars as pl

from agentlen.domain.model.profile import FieldProfile, FileProfile
from agentlen.infrastructure.ai.sanitizer import sanitize_value
from agentlen.infrastructure.files.polars_reader import infer_format, scan_file

_MAX_EXAMPLES = 3

_TYPE_NAMES: dict[type[pl.DataType], str] = {
    pl.Utf8: "string",
    pl.Boolean: "boolean",
    pl.Date: "date",
    pl.Time: "time",
    pl.Null: "null",
}
_INT_TYPES = (
    pl.Int8,
    pl.Int16,
    pl.Int32,
    pl.Int64,
    pl.UInt8,
    pl.UInt16,
    pl.UInt32,
    pl.UInt64,
)
_FLOAT_TYPES = (pl.Float32, pl.Float64)
_NUMERIC_TYPES = _INT_TYPES + _FLOAT_TYPES


def _type_name(dtype: pl.DataType) -> str:  # noqa: PLR0911
    if dtype in _INT_TYPES:
        return "integer"
    if dtype in _FLOAT_TYPES:
        return "float"
    if isinstance(dtype, pl.Decimal):
        return "decimal"
    if isinstance(dtype, pl.Datetime):
        return "datetime"
    if isinstance(dtype, pl.Duration):
        return "duration"
    for base, name in _TYPE_NAMES.items():
        if dtype == base:
            return name
    # Never leak a raw Polars repr (e.g. "categorical(ordering='physical')")
    # across the port boundary — an unhandled type is reported as "unknown"
    # rather than whatever str(dtype) happens to produce.
    return "unknown"


def _is_numeric(dtype: pl.DataType) -> bool:
    return dtype in _NUMERIC_TYPES or isinstance(dtype, pl.Decimal)


_SAFE_UNQUOTED_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _path_segment(name: str) -> str:
    """`.name` for a plain identifier, `["name"]` otherwise.

    A raw field literally named `"a.b"` must not render as `.a.b` — that's
    indistinguishable from a nested field `a` containing `b`, and the two
    would silently collide on the same JSONPath.
    """
    if _SAFE_UNQUOTED_NAME.match(name):
        return f".{name}"
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'["{escaped}"]'


def _leaf_columns(df: pl.DataFrame, prefix: str = "$") -> list[tuple[str, pl.Series]]:
    """Recursively flatten struct/list columns into JSONPath-addressed leaf series.

    A struct field `usage: {input_tokens: ...}` becomes `$.usage.input_tokens`.
    A list column (of structs or of scalars) is exploded once per nesting level
    and addressed as `$.field[]` (or `$.field[].subfield` for a list of structs) —
    note that after exploding, the leaf series no longer has one value per source
    record but one value per list element, so its null_ratio/distinct_ratio are
    relative to that flattened element count, not to the file's record_count.
    """
    leaves: list[tuple[str, pl.Series]] = []
    for name in df.columns:
        leaves.extend(_flatten_series(df[name], f"{prefix}{_path_segment(name)}"))
    return leaves


def _flatten_series(series: pl.Series, path: str) -> list[tuple[str, pl.Series]]:
    dtype = series.dtype
    if isinstance(dtype, pl.Struct):
        struct_df = series.struct.unnest()
        leaves: list[tuple[str, pl.Series]] = []
        for field_name in struct_df.columns:
            leaves.extend(
                _flatten_series(struct_df[field_name], f"{path}{_path_segment(field_name)}")
            )
        return leaves
    if isinstance(dtype, pl.List):
        return _flatten_series(series.explode(empty_as_null=True), f"{path}[]")
    return [(path, series)]


def _profile_leaf(path: str, series: pl.Series) -> FieldProfile:
    total = series.len()
    null_count = series.null_count()
    non_null = series.drop_nulls()

    types: list[str] = []
    if len(non_null) > 0:
        types.append(_type_name(series.dtype))
    if null_count > 0:
        types.append("null")
    if not types:
        types.append(_type_name(series.dtype))

    # The profile travels straight into the agent's prompt (MAPPING_CONTRACT.md
    # §5, file_profile.fields[].examples) — same redaction as sample_records,
    # or a secret sitting in a raw value leaks through the other door.
    examples = [sanitize_value(str(v)) for v in non_null.head(_MAX_EXAMPLES).to_list()]

    min_value: str | None = None
    max_value: str | None = None
    if _is_numeric(series.dtype) and len(non_null) > 0:
        min_value = str(non_null.min())
        max_value = str(non_null.max())

    # Over non-null values only: a nullable-but-otherwise-unique column must
    # still read 1.0 (MAPPING_CONTRACT.md §5 uses that as the natural-key
    # signal), not be capped at (1 - null_ratio) by dividing by `total`.
    present = len(non_null)
    distinct_ratio = non_null.n_unique() / present if present else None

    return FieldProfile(
        path=path,
        types=tuple(types),
        null_ratio=(null_count / total) if total else 0.0,
        examples=tuple(examples),
        min_value=min_value,
        max_value=max_value,
        distinct_ratio=distinct_ratio,
    )


class PolarsFileProfiler:
    """Implements the `FileProfiler` port.

    `format` is inferred from the path suffix only as a fallback (test
    fixtures, callers that don't already know it) — the storage layer writes
    content-addressed paths with no extension at all, so a caller that has
    already stored the file must pass the format it recorded.
    """

    async def profile(
        self, path: str, *, sample_size: int = 500, format: str | None = None
    ) -> FileProfile:
        if sample_size <= 0:
            raise ValueError(f"sample_size must be positive, got {sample_size!r}.")

        format_ = format or infer_format(path)

        # An empty file has no data to infer a schema from — scan_ndjson in
        # particular raises a raw Polars ComputeError rather than a sensible
        # profile. A zero-byte file always means zero records regardless of
        # format, so short-circuit before Polars ever sees it.
        if Path(path).stat().st_size == 0:
            return FileProfile(
                file_id=0, format=format_, record_count=0, sampled_records=0, fields=()
            )

        # scan_file's default schema inference is the one the import reader
        # uses too (polars_reader.INFER_SCHEMA_LENGTH): a field or a type the
        # profile shows is one the import reads, wherever it first appears.
        lazy = scan_file(path, format=format_)

        # Both collect() calls are synchronous and CPU/IO-bound; run off the
        # event loop so one profile request doesn't stall every other
        # concurrent request FastAPI is serving.
        record_count = await asyncio.to_thread(lambda: lazy.select(pl.len()).collect().item())
        sample = await asyncio.to_thread(lazy.head(sample_size).collect)

        fields = tuple(
            _profile_leaf(field_path, series) for field_path, series in _leaf_columns(sample)
        )

        return FileProfile(
            file_id=0,  # filled in by the ProfileFile use case, which knows the real id
            format=format_,
            record_count=record_count,
            sampled_records=sample.height,
            fields=fields,
        )
