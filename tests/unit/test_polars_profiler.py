from pathlib import Path

from agentlen.infrastructure.files.polars_profiler import profile_fields
from agentlen.infrastructure.files.polars_reader import read_jsonl

SAMPLE_FILE = Path(__file__).parents[2] / "data" / "samples" / "tracelab_example_session.jsonl"


def test_profile_fields_reports_provider_column():
    df = read_jsonl(SAMPLE_FILE)
    profiles = profile_fields(df)
    provider_profile = next(p for p in profiles if p.name == "provider")

    assert provider_profile.null_rate == 0.0
    assert "claude" in provider_profile.examples
