from collections.abc import Callable
from pathlib import Path

import polars as pl

_SCANNERS: dict[str, Callable[[str | Path], pl.LazyFrame]] = {
    "jsonl": pl.scan_ndjson,
    "csv": pl.scan_csv,
    "parquet": pl.scan_parquet,
}


def read_jsonl(path: str | Path) -> pl.LazyFrame:
    return pl.scan_ndjson(path)


def read_csv(path: str | Path) -> pl.LazyFrame:
    return pl.scan_csv(path)


def read_parquet(path: str | Path) -> pl.LazyFrame:
    return pl.scan_parquet(path)


def scan_file(path: str | Path, *, format: str) -> pl.LazyFrame:
    """Lazily scan a source file of the given format. Never reads it into memory."""
    try:
        scanner = _SCANNERS[format]
    except KeyError:
        raise ValueError(
            f"Unsupported format: {format!r}. Expected one of {sorted(_SCANNERS)}."
        ) from None
    return scanner(path)


def infer_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in ("jsonl", "ndjson"):
        return "jsonl"
    if suffix == "csv":
        return "csv"
    if suffix in ("parquet", "pq"):
        return "parquet"
    raise ValueError(f"Cannot infer a supported format from path: {path!r}")
