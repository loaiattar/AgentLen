from __future__ import annotations

import asyncio
import re

import polars as pl

from agentlen.domain.model.profile import FieldProfile, FileProfile
from agentlen.infrastructure.files.polars_reader import (
    DEFAULT_INFER_SCHEMA_LENGTH,
    infer_format,
    scan_file,
)

_MAX_EXAMPLES = 3

_TYPE_NAMES: dict[type[pl.DataType], str] = {
    pl.Utf8: "string",
    pl.Boolean: "boolean",
    pl.Date: "date",
    pl.Time: "time",
    pl.Null: "null",
}
_INT_TYPES = (
    pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
)
_FLOAT_TYPES = (pl.Float32, pl.Float64)
_NUMERIC_TYPES = _INT_TYPES + _FLOAT_TYPES


def _type_name(dtype: pl.DataType) -> str:
    if dtype in _INT_TYPES:
        return "integer"
    if dtype in _FLOAT_TYPES:
        return "float"
    if isinstance(dtype, pl.Datetime):
        return "datetime"
    for base, name in _TYPE_NAMES.items():
        if dtype == base:
            return name
    return str(dtype).lower()


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

    examples = [str(v) for v in non_null.head(_MAX_EXAMPLES).to_list()]

    min_value: str | None = None
    max_value: str | None = None
    if series.dtype in _NUMERIC_TYPES and len(non_null) > 0:
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
    """Implements the `FileProfiler` port. Format is inferred from the path suffix."""

    async def profile(self, path: str, *, sample_size: int = 500) -> FileProfile:
        format_ = infer_format(path)
        # Schema inference must see at least as many rows as we're about to
        # sample, or a field that only appears later silently vanishes from
        # the profile (see infra/files/polars_reader.py). Floored at Polars'
        # own default so a deliberately tiny sample_size (tests, previews)
        # can't narrow the window enough to make the full-file record_count
        # scan below choke on a field it never saw.
        infer_schema_length = max(sample_size, DEFAULT_INFER_SCHEMA_LENGTH)
        lazy = scan_file(path, format=format_, infer_schema_length=infer_schema_length)

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
