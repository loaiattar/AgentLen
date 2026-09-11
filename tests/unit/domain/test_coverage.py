"""Tests for Coverage and MetricValue — enforces the null ≠ 0 contract.

Subject requirement: "une donnée indisponible ne doit pas devenir un zéro".
"""

from agentlen.domain.model.metrics import Coverage, MetricValue


class TestCoverage:
    def test_ratio_is_unknown_when_no_records(self):
        cov = Coverage(present=0, total=0)
        assert cov.ratio is None

    def test_ratio_is_one_when_all_present(self):
        cov = Coverage(present=100, total=100)
        assert cov.ratio == 1.0

    def test_ratio_is_partial_when_some_missing(self):
        cov = Coverage(present=80, total=100)
        assert cov.ratio == 0.8

    def test_ratio_is_zero_when_none_present(self):
        cov = Coverage(present=0, total=100)
        assert cov.ratio == 0.0


class TestMetricValue:
    def test_value_can_be_none(self):
        """A metric with no available data must carry None, not 0."""
        mv = MetricValue(
            key="avg_session_duration_ms",
            value=None,
            unit="ms",
            coverage=Coverage(present=0, total=50),
        )
        assert mv.value is None
        assert mv.value != 0

    def test_value_none_is_distinguishable_from_zero(self):
        none_value = MetricValue(
            key="tool_error_rate",
            value=None,
            unit="ratio",
            coverage=Coverage(present=0, total=10),
        )
        zero_value = MetricValue(
            key="tool_error_rate",
            value=0.0,
            unit="ratio",
            coverage=Coverage(present=10, total=10),
        )
        assert none_value.value is None
        assert zero_value.value == 0.0
        assert none_value.value != zero_value.value

    def test_warning_is_none_by_default(self):
        mv = MetricValue(
            key="session_count",
            value=42,
            unit="sessions",
            coverage=Coverage(present=42, total=42),
        )
        assert mv.warning is None
