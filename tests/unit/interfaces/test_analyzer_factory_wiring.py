"""The analyzer the HTTP layer builds from the environment (#191)."""

from __future__ import annotations

import pytest

from agentlen.application.use_cases.analysis_deadline import DeadlineBoundAnalyzer
from agentlen.interfaces.http.dependencies import get_analyzer_factory


def test_a_per_request_provider_gets_its_own_host_and_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_MODEL", "m")
    monkeypatch.setenv("AI_BASE_URL", "https://third-party.example/v1")
    monkeypatch.setenv("AI_TOTAL_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")

    overridden = get_analyzer_factory()("anthropic", "other-model")
    configured = get_analyzer_factory()(None, None)

    assert isinstance(overridden, DeadlineBoundAnalyzer)
    assert isinstance(configured, DeadlineBoundAnalyzer)
    assert overridden._seconds == 42
    assert overridden._inner._endpoint() == "https://api.anthropic.com/v1/messages"  # type: ignore[attr-defined]
    assert configured._inner._endpoint().startswith("https://third-party.example/")  # type: ignore[attr-defined]
