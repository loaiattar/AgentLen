import pytest

from agentlen.domain.services.metric_registry import (
    all_definitions,
    get,
    overview_definitions,
)


def test_overview_exposes_exactly_four_metrics():
    """The brief requires at least four headline indicators, and the dashboard
    header shows exactly these. Documenting an extra chart figure must not add
    a fifth tile — hence the split from `all_definitions()`."""
    assert len(overview_definitions()) == 4


def test_all_required_keys_present():
    expected_keys = {
        "session_count",
        "avg_tokens_per_session",
        "avg_session_duration_ms",
        "tool_error_rate",
    }
    # The four are a subset: all_definitions() also publishes the figures the
    # chart routes return, so every number the API shows has a definition.
    assert expected_keys <= {m.key for m in all_definitions()}
    assert {m.key for m in overview_definitions()} == expected_keys


def test_get_returns_correct_definition():
    defn = get("session_count")
    assert defn.unit == "sessions"
    assert defn.comparability == "cross_source"


def test_get_raises_for_unknown_key():
    with pytest.raises(KeyError):
        get("nonexistent_metric")


def test_cache_metrics_are_declared_per_source_only():
    """Cache metrics must never be comparable across sources.

    Some sources publish no cache figures at all, so a total spanning several
    of them measures "the sources that bothered", not "all sources".

    Previously this asserted no cache metric existed in the registry at all,
    which was a proxy for the same rule while none had been defined. Now that
    `cache_read_tokens` is published, the rule itself is asserted.
    """
    for m in all_definitions():
        if "cache" in m.key:
            assert m.comparability == "per_source_only", (
                f"Metric '{m.key}' concerns cache tokens and must be "
                "per_source_only, so the API warns when it is aggregated."
            )
