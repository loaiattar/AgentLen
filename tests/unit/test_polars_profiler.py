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
