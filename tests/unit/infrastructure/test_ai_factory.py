"""Provider selection by configuration, and what it refuses."""

from __future__ import annotations

import pytest

from agentlen.application.errors import AnalyzerError
from agentlen.infrastructure.ai.factory import (
    UnsupportedProviderError,
    build_structure_analyzer,
    provider_status,
    supported_providers,
)
from agentlen.infrastructure.config.settings import AISettings, ProviderKeys

KEYS = ProviderKeys(
    anthropic_api_key="sk-ant-test", openai_api_key="sk-test", ai_api_key="gsk-test"
)


def test_the_four_providers_are_registered() -> None:
    assert supported_providers() == ["anthropic", "fake", "openai", "openai_compatible"]


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("anthropic", "anthropic"),
        ("openai", "openai"),
        ("openai_compatible", "openai_compatible"),
        ("fake", "fake"),
    ],
)
def test_each_provider_resolves_to_its_adapter(provider: str, expected: str) -> None:
    analyzer = build_structure_analyzer(
        AISettings(provider=provider, model="m", base_url="https://x/v1"), KEYS
    )
    assert analyzer.descriptor["provider"] == expected


def test_an_unknown_provider_lists_the_valid_ones() -> None:
    with pytest.raises(UnsupportedProviderError) as exc:
        build_structure_analyzer(AISettings(provider="gemini", model="m"), KEYS)

    assert exc.value.code == "UNSUPPORTED_PROVIDER"
    assert "anthropic" in str(exc.value)


def test_a_missing_key_is_refused_before_any_call() -> None:
    with pytest.raises(AnalyzerError) as exc:
        build_structure_analyzer(AISettings(provider="anthropic", model="m"), ProviderKeys())
    assert "ANTHROPIC_API_KEY" in str(exc.value)


def test_the_fake_needs_no_key() -> None:
    """What lets the CI run the whole suite with no account."""
    analyzer = build_structure_analyzer(AISettings(provider="fake", model="m"), ProviderKeys())
    assert analyzer.descriptor["provider"] == "fake"


def test_a_missing_model_is_refused() -> None:
    """ADR-006: the model comes from configuration, never from the code. No
    default is provided, so an unset variable must fail loudly."""
    with pytest.raises(AnalyzerError) as exc:
        build_structure_analyzer(AISettings(provider="anthropic", model=""), KEYS)
    assert "AI_MODEL" in str(exc.value)


# ---------------------------------------------------------------------------
# Any OpenAI-compatible endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("base_url", "host"),
    [
        ("https://api.groq.com/openai/v1", "api.groq.com"),
        ("https://api.mistral.ai/v1", "api.mistral.ai"),
        ("https://openrouter.ai/api/v1", "openrouter.ai"),
        ("http://localhost:11434/v1", "localhost:11434"),  # Ollama
    ],
)
def test_one_adapter_reaches_any_openai_shaped_host(base_url: str, host: str) -> None:
    """Groq, Mistral, OpenRouter, a local Ollama — all reached by configuration
    alone, with no provider-specific code."""
    analyzer = build_structure_analyzer(
        AISettings(provider="openai_compatible", model="m", base_url=base_url), KEYS
    )
    assert host in analyzer._endpoint()  # type: ignore[attr-defined]
    assert analyzer._endpoint().endswith("/chat/completions")  # type: ignore[attr-defined]


def test_openai_compatible_requires_a_base_url() -> None:
    """Without it there is no provider to talk to, and a silent fallback to
    OpenAI would send someone's data to the wrong company."""
    analyzer = build_structure_analyzer(
        AISettings(provider="openai_compatible", model="m", base_url=""), KEYS
    )
    with pytest.raises(AnalyzerError) as exc:
        analyzer._endpoint()  # type: ignore[attr-defined]
    assert "AI_BASE_URL" in str(exc.value)


def test_openai_keeps_its_default_endpoint() -> None:
    analyzer = build_structure_analyzer(AISettings(provider="openai", model="m"), KEYS)
    assert "api.openai.com" in analyzer._endpoint()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Nothing leaks
# ---------------------------------------------------------------------------


def test_provider_status_never_exposes_a_key() -> None:
    status = provider_status(AISettings(provider="anthropic", model="m"), KEYS)
    text = str(status)

    assert "sk-ant-test" not in text
    assert "gsk-test" not in text
    assert status["active"] == {"provider": "anthropic", "model": "m"}
    configured = {p["provider"]: p["configured"] for p in status["available"]}  # type: ignore[index]
    assert configured["anthropic"] is True
    assert configured["fake"] is True


def test_provider_status_reports_unconfigured_providers() -> None:
    status = provider_status(AISettings(provider="fake", model="m"), ProviderKeys())
    configured = {p["provider"]: p["configured"] for p in status["available"]}  # type: ignore[index]

    assert configured["anthropic"] is False
    assert configured["openai"] is False
    assert configured["fake"] is True


def test_the_descriptor_carries_no_key() -> None:
    analyzer = build_structure_analyzer(AISettings(provider="anthropic", model="m"), KEYS)
    assert set(analyzer.descriptor) == {"provider", "model", "prompt_version"}
    assert "sk-ant-test" not in str(analyzer.descriptor)


def test_openai_compatible_reaches_a_keyless_host() -> None:
    """Constat #99 : la factory exigeait une clé pour `openai_compatible`,
    alors que la docstring de l'adaptateur désigne Ollama, LM Studio et vLLM
    comme cas d'usage visé — et qu'aucun n'en demande. Le cas d'usage principal
    échouait donc avant le moindre appel."""
    from agentlen.infrastructure.ai.factory import build_structure_analyzer

    analyzer = build_structure_analyzer(
        AISettings(
            provider="openai_compatible", model="llama3.2", base_url="http://localhost:11434/v1"
        ),
        ProviderKeys(),
    )

    assert analyzer.provider_name == "openai_compatible"
    # Un `Bearer ` sans jeton derrière : certains hôtes locaux le rejettent
    # plutôt que de l'ignorer.
    assert "Authorization" not in analyzer._headers()


def test_a_key_is_still_sent_when_there_is_one() -> None:
    from agentlen.infrastructure.ai.factory import build_structure_analyzer

    analyzer = build_structure_analyzer(
        AISettings(
            provider="openai_compatible", model="m", base_url="https://api.groq.com/openai/v1"
        ),
        ProviderKeys(ai_api_key="gsk-xyz"),
    )

    assert analyzer._headers()["Authorization"] == "Bearer gsk-xyz"


def test_the_providers_still_requiring_a_key_still_refuse_without_one() -> None:
    """L'assouplissement vise les hôtes sans clé, pas les fournisseurs payants."""
    from agentlen.application.errors import AnalyzerError
    from agentlen.infrastructure.ai.factory import build_structure_analyzer

    for provider in ("anthropic", "openai"):
        with pytest.raises(AnalyzerError) as exc:
            build_structure_analyzer(AISettings(provider=provider, model="m"), ProviderKeys())
        assert "Aucune clé" in str(exc.value)


def test_the_output_bound_parameter_follows_the_configuration() -> None:
    """Constat #99 : les modèles de raisonnement (o1, o3, gpt-5…) refusent
    `max_tokens` en 400 et exigent `max_completion_tokens`. Le modèle vient de
    la configuration (ADR-006), le paramètre qu'il accepte aussi — plutôt
    qu'une liste de préfixes qui se périme à chaque sortie."""
    from agentlen.infrastructure.ai.openai_adapter import OpenAIAnalyzer

    for parameter in ("max_tokens", "max_completion_tokens"):
        settings = AISettings(provider="openai", model="o3-mini", max_tokens_parameter=parameter)
        body = OpenAIAnalyzer(settings, "k")._build_request([])
        assert parameter in body
        assert len([key for key in body if key.endswith("tokens")]) == 1
