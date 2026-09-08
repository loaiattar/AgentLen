from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class FieldProfile:
    name: str
    dtype: str
    null_rate: float
    examples: list[str]


def profile_fields(df: pl.DataFrame, *, max_examples: int = 3) -> list[FieldProfile]:
    row_count = df.height
    profiles = []
    for name, dtype in zip(df.columns, df.dtypes):
        column = df[name]
        null_rate = column.null_count() / row_count if row_count else 0.0
        examples = [str(value) for value in column.drop_nulls().head(max_examples).to_list()]
        profiles.append(
            FieldProfile(name=name, dtype=str(dtype), null_rate=null_rate, examples=examples)
        )
    return profiles
