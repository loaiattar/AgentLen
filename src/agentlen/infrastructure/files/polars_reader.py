from pathlib import Path

import polars as pl


def read_jsonl(path: str | Path) -> pl.DataFrame:
    return pl.read_ndjson(path)
