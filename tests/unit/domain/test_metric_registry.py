import pytest

from agentlen.domain.services.metric_registry import (
    ALL_METRICS,
    all_definitions,
    get,
)


def test_registry_exposes_four_metrics():
    assert len(all_definitions()) == 4


def test_all_required_keys_present():
    expected_keys = {
        "session_count",
        "avg_tokens_per_session",
        "avg_session_duration_ms",
        "tool_error_rate",
    }
    assert {m.key for m in all_definitions()} == expected_keys


def test_get_returns_correct_definition():
    defn = get("session_count")
    assert defn.unit == "sessions"
    assert defn.comparability == "cross_source"


def test_get_raises_for_unknown_key():
    with pytest.raises(KeyError):
        get("nonexistent_metric")


def test_no_metric_has_cross_source_comparability_with_cache_fields():
    """Cache token metrics must be per_source_only — not in this registry."""
    for m in all_definitions():
        assert "cache" not in m.key, (
            f"Metric '{m.key}' mentions cache tokens but is in the "
            "cross-source registry. It should be per_source_only."
        )
