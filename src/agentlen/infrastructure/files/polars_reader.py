from pathlib import Path

import polars as pl

# scan_ndjson/scan_csv only look at the first `infer_schema_length` rows to
# work out the schema (Polars default: 100). A field that first appears past
# that point is silently absent from every downstream profile — no error, no
# warning, and the model can never propose a mapping for a field it never
# saw. scan_parquet has no such parameter: Parquet carries its real schema.
DEFAULT_INFER_SCHEMA_LENGTH = 100


def read_jsonl(
    path: str | Path, *, infer_schema_length: int = DEFAULT_INFER_SCHEMA_LENGTH
) -> pl.LazyFrame:
    return pl.scan_ndjson(path, infer_schema_length=infer_schema_length)


def read_csv(
    path: str | Path, *, infer_schema_length: int = DEFAULT_INFER_SCHEMA_LENGTH
) -> pl.LazyFrame:
    return pl.scan_csv(path, infer_schema_length=infer_schema_length)


def read_parquet(path: str | Path) -> pl.LazyFrame:
    return pl.scan_parquet(path)


def scan_file(
    path: str | Path, *, format: str, infer_schema_length: int = DEFAULT_INFER_SCHEMA_LENGTH
) -> pl.LazyFrame:
    """Lazily scan a source file of the given format. Never reads it into memory."""
    if format == "jsonl":
        return read_jsonl(path, infer_schema_length=infer_schema_length)
    if format == "csv":
        return read_csv(path, infer_schema_length=infer_schema_length)
    if format == "parquet":
        return read_parquet(path)
    raise ValueError(f"Unsupported format: {format!r}. Expected one of csv, jsonl, parquet.")


def infer_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in ("jsonl", "ndjson"):
        return "jsonl"
    if suffix == "csv":
        return "csv"
    if suffix in ("parquet", "pq"):
        return "parquet"
    raise ValueError(f"Cannot infer a supported format from path: {path!r}")
