from agentlen.domain.model.model_call import TokenUsage


def test_total_returns_none_when_both_unknown():
    usage = TokenUsage(input_tokens=None, output_tokens=None)
    assert usage.total is None


def test_total_returns_none_when_only_input_is_known():
    usage = TokenUsage(input_tokens=100, output_tokens=None)
    assert usage.total is None


def test_total_returns_none_when_only_output_is_known():
    usage = TokenUsage(input_tokens=None, output_tokens=200)
    assert usage.total is None


def test_total_returns_full_sum_when_both_known():
    usage = TokenUsage(input_tokens=100, output_tokens=200)
    assert usage.total == 300


def test_total_is_not_zero_when_both_unknown():
    """A missing value must never silently become 0."""
    usage = TokenUsage()
    assert usage.total is None
    assert usage.total != 0
