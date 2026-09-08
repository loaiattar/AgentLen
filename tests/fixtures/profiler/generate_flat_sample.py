"""Regenerates the flat cross-format fixtures (jsonl/csv/parquet) used to test that
profiling the same data through the three supported formats yields equivalent
FileProfile field lists. Not part of the test suite itself — run manually if the
fixture data needs to change:

    .venv/Scripts/python.exe tests/fixtures/profiler/generate_flat_sample.py
"""

from pathlib import Path

import polars as pl

HERE = Path(__file__).parent

df = pl.DataFrame(
    {
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "name": [
            "alice", "bob", "carol", "dave", None,
            "frank", "grace", "heidi", "ivan", "judy",
        ],
        "score": [
            12.5, 8.0, None, 4.25, 19.0,
            None, 7.75, 15.0, 3.5, 11.0,
        ],
    }
)

df.write_ndjson(HERE / "flat_sample.jsonl")
df.write_csv(HERE / "flat_sample.csv")
df.write_parquet(HERE / "flat_sample.parquet")
