from pathlib import Path

import polars as pl

# The one schema-inference strategy, shared by the profiler and the import
# reader: infer over the whole file (`None`). scan_ndjson/scan_csv otherwise
# look at the first N rows only (Polars default: 100), and any window smaller
# than the file breaks the promise that the import reads what the profile
# showed — a field first seen past the window reaches the profile but is NULL
# at import, and a CSV column whose type changes past it fails the run with a
# ComputeError. Over the whole file, a late type widens the column instead.
# The cost is one linear inference scan per profile and per CSV import.
# scan_parquet has no such parameter: Parquet carries its real schema.
INFER_SCHEMA_LENGTH: int | None = None

#: Rows a preview infers its schema from. A preview reads a few hundred records
#: at most, and whole-file inference made even a one-row preview of a large CSV
#: scan every line, synchronously, before showing anything.
PREVIEW_INFER_SCHEMA_LENGTH = 1_000


def read_jsonl(
    path: str | Path, *, infer_schema_length: int | None = INFER_SCHEMA_LENGTH
) -> pl.LazyFrame:
    return pl.scan_ndjson(path, infer_schema_length=infer_schema_length)


def read_csv(
    path: str | Path, *, infer_schema_length: int | None = INFER_SCHEMA_LENGTH
) -> pl.LazyFrame:
    return pl.scan_csv(path, infer_schema_length=infer_schema_length)


def read_parquet(path: str | Path) -> pl.LazyFrame:
    return pl.scan_parquet(path)


def scan_file(
    path: str | Path, *, format: str, infer_schema_length: int | None = INFER_SCHEMA_LENGTH
) -> pl.LazyFrame:
    """Lazily scan a source file of the given format. Never reads it into memory."""
    if format == "jsonl":
        return read_jsonl(path, infer_schema_length=infer_schema_length)
    if format == "csv":
        return read_csv(path, infer_schema_length=infer_schema_length)
    if format == "parquet":
        return read_parquet(path)
    raise ValueError(f"Unsupported format: {format!r}. Expected one of csv, jsonl, parquet.")


def read_head(path: str | Path, format: str, limit: int) -> pl.LazyFrame:
    """The first `limit` records, with the schema inferred from the first rows.

    For previews only. The import keeps whole-file inference, so a column whose
    type changes further down may be read wider there than the preview shows.
    Polars parses past `limit` in blocks, so a type change just beyond the
    window can still fail the read; whole-file inference is then used instead,
    which reads the file once more but never fails where the import succeeds.
    """
    window = max(limit, PREVIEW_INFER_SCHEMA_LENGTH)
    try:
        frame = scan_file(path, format=format, infer_schema_length=window).head(limit).collect()
    except pl.exceptions.ComputeError:
        frame = scan_file(path, format=format).head(limit).collect()
    return frame.lazy()


def infer_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in ("jsonl", "ndjson"):
        return "jsonl"
    if suffix == "csv":
        return "csv"
    if suffix in ("parquet", "pq"):
        return "parquet"
    raise ValueError(f"Cannot infer a supported format from path: {path!r}")
