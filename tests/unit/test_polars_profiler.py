from pathlib import Path

import polars as pl
import pytest

from agentlen.domain.model.profile import FieldProfile, FileProfile
from agentlen.infrastructure.files.polars_profiler import PolarsFileProfiler

SAMPLE_FILE = Path(__file__).parents[2] / "data" / "samples" / "tracelab_example_session.jsonl"
FLAT_FIXTURES = Path(__file__).parents[2] / "tests" / "fixtures" / "profiler"
SAMPLE_ROW_COUNT = 19
FLAT_FIXTURE_ROW_COUNT = 10
LARGE_FILE_ROW_COUNT = 50_000

pytestmark = pytest.mark.asyncio


def _field(profile: FileProfile, path: str) -> FieldProfile:
    return next(f for f in profile.fields if f.path == path)


async def test_profile_returns_domain_file_profile_not_a_polars_object():
    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(SAMPLE_FILE))

    assert type(profile) is FileProfile
    for field in profile.fields:
        assert type(field) is FieldProfile
        assert all(isinstance(t, str) for t in field.types)
        assert all(isinstance(e, str) for e in field.examples)


async def test_profile_reports_real_record_count_vs_sampled_records():
    requested_sample_size = 5
    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(SAMPLE_FILE), sample_size=requested_sample_size)

    assert profile.record_count == SAMPLE_ROW_COUNT
    assert profile.sampled_records == requested_sample_size


async def test_nested_field_is_flattened_to_jsonpath_on_real_sample():
    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(SAMPLE_FILE))

    tool_name = _field(profile, "$.tools[].tool_name")
    assert "string" in tool_name.types
    assert len(tool_name.examples) > 0


@pytest.mark.parametrize(
    "filename",
    ["flat_sample.jsonl", "flat_sample.csv", "flat_sample.parquet"],
)
async def test_the_three_formats_produce_equivalent_field_profiles(filename):
    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(FLAT_FIXTURES / filename))

    paths = {f.path for f in profile.fields}
    assert paths == {"$.id", "$.name", "$.score"}
    assert profile.record_count == FLAT_FIXTURE_ROW_COUNT

    score = _field(profile, "$.score")
    assert score.min_value == "3.5"
    assert score.max_value == "19.0"


async def test_null_ratio_is_computed_precisely(tmp_path):
    # 3 nulls out of 25 rows = exactly 0.12, matching the ticket's stated example.
    df = pl.DataFrame({"value": [1] * 22 + [None] * 3})
    path = tmp_path / "nulls.jsonl"
    df.write_ndjson(path)

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path))

    value = _field(profile, "$.value")
    assert value.null_ratio == pytest.approx(0.12)


@pytest.mark.parametrize("bad_sample_size", [0, -1])
async def test_non_positive_sample_size_is_rejected_with_a_clear_error(bad_sample_size):
    profiler = PolarsFileProfiler()
    with pytest.raises(ValueError, match="sample_size"):
        await profiler.profile(str(SAMPLE_FILE), sample_size=bad_sample_size)


async def test_empty_file_returns_a_zero_record_profile_instead_of_crashing(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.touch()

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path))

    assert profile.record_count == 0
    assert profile.sampled_records == 0
    assert profile.fields == ()


async def test_decimal_column_is_named_and_gets_min_max_not_a_raw_polars_repr(tmp_path):
    df = pl.DataFrame({"amount": ["1.50", "2.75", "0.10"]}).with_columns(
        pl.col("amount").cast(pl.Decimal(scale=2))
    )
    path = tmp_path / "decimal.parquet"
    df.write_parquet(path)

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path))

    amount = _field(profile, "$.amount")
    assert amount.types == ("decimal",)
    assert amount.min_value == "0.10"
    assert amount.max_value == "2.75"


async def test_examples_are_sanitized_before_leaving_the_profiler(tmp_path):
    df = pl.DataFrame(
        {
            "cmd": ["export KEY=sk-ant-api03-AAAABBBBCCCCDDDD"],
            "home": ["/home/loai/x"],
        }
    )
    path = tmp_path / "secrets.jsonl"
    df.write_ndjson(path)

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path))

    cmd_examples = " ".join(_field(profile, "$.cmd").examples)
    home_examples = " ".join(_field(profile, "$.home").examples)
    assert "sk-ant-api03-AAAABBBBCCCCDDDD" not in cmd_examples
    assert "loai" not in home_examples


async def test_a_dotted_field_name_does_not_collide_with_a_nested_struct(tmp_path):
    # {"a.b": 1, "a": {"b": 2}} are two distinct fields; naive dot-joining
    # would render both as "$.a.b" and silently merge them into one.
    import json

    path = tmp_path / "dotted_name.jsonl"
    path.write_text(json.dumps({"a.b": 1, "a": {"b": 2}}), encoding="utf-8")

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path))

    paths = {f.path for f in profile.fields}
    assert paths == {'$["a.b"]', "$.a.b"}


async def test_a_field_appearing_after_row_100_still_reaches_the_profile(tmp_path):
    # Polars' default schema-inference window is 100 rows. A field that only
    # shows up later must not silently vanish from the profile just because
    # infer_schema_length wasn't told to match sample_size.
    import json

    rows = []
    for i in range(150):
        row: dict[str, object] = {"a": i}
        if i >= 120:
            row["late_field"] = f"value-{i}"
        rows.append(row)
    path = tmp_path / "late_field.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path), sample_size=150)

    paths = {f.path for f in profile.fields}
    assert "$.late_field" in paths


async def test_distinct_ratio_reaches_1_0_for_a_unique_but_nullable_column(tmp_path):
    # A key that's unique among the values actually present must read as a
    # perfect natural-key candidate, regardless of how many rows are null —
    # null_ratio already carries the "how much is missing" signal separately.
    df = pl.DataFrame({"key": ["a", "b", "c", "d", "e", "f", "g", "h", "i", None]})
    path = tmp_path / "unique_with_null.jsonl"
    df.write_ndjson(path)

    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path))

    key = _field(profile, "$.key")
    assert key.distinct_ratio == 1.0
    assert key.null_ratio == pytest.approx(0.1)


async def test_sample_size_bounds_memory_even_on_a_larger_file(tmp_path):
    # Stands in for the 500 MB acceptance criterion: proves record_count still
    # reflects the true total while the collected sample stays bounded, which is
    # exactly the property that keeps a large file from being loaded whole.
    df = pl.DataFrame({"value": list(range(LARGE_FILE_ROW_COUNT))})
    path = tmp_path / "large.jsonl"
    df.write_ndjson(path)

    requested_sample_size = 100
    profiler = PolarsFileProfiler()
    profile = await profiler.profile(str(path), sample_size=requested_sample_size)

    assert profile.record_count == LARGE_FILE_ROW_COUNT
    assert profile.sampled_records == requested_sample_size
