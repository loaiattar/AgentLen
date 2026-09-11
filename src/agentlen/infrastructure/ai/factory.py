"""Resolve `AI_PROVIDER` to an adapter.

ADR-006: adding a provider is a class and a registry line. This file is that
line — nothing else in the codebase mentions a provider by name.
"""

from __future__ import annotations

from agentlen.application.errors import AnalyzerError
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.infrastructure.ai.anthropic_adapter import AnthropicAnalyzer
from agentlen.infrastructure.ai.fake_adapter import FakeAnalyzer, fixtures_available
from agentlen.infrastructure.ai.openai_adapter import OpenAIAnalyzer, OpenAICompatibleAnalyzer
from agentlen.infrastructure.config.settings import (
    AISettings,
    ProviderKeys,
    load_ai_settings,
    load_provider_keys,
)


class UnsupportedProviderError(AnalyzerError):
    code = "UNSUPPORTED_PROVIDER"

    def __init__(self, provider: str, supported: list[str]) -> None:
        super().__init__(
            f"Fournisseur '{provider}' inconnu. Valeurs acceptées : {', '.join(supported)}.",
            details={"provider": provider, "supported": supported},
        )


_REGISTRY: dict[str, type] = {
    "anthropic": AnthropicAnalyzer,
    "openai": OpenAIAnalyzer,
    # Same dialect, different host: Groq, Mistral, DeepSeek, OpenRouter,
    # Ollama, vLLM… selected entirely by AI_BASE_URL.
    "openai_compatible": OpenAICompatibleAnalyzer,
    "fake": FakeAnalyzer,
}

#: Which key each provider reads. `openai_compatible` falls back to a generic
#: one so a new host needs no code change.
_KEY_FOR: dict[str, str] = {
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
    "openai_compatible": "ai_api_key",
    "fake": "",
}

#: Fournisseurs pour lesquels une clé absente n'est pas une erreur. Ollama,
#: LM Studio et vLLM — les cibles que la docstring de l'adaptateur nomme — n'en
#: demandent aucune, et exiger une valeur bidon pour les joindre transformait
#: leur cas d'usage principal en échec de configuration.
_KEY_OPTIONAL = frozenset({"openai_compatible"})


def supported_providers() -> list[str]:
    return sorted(_REGISTRY)


def settings_for_request(
    configured: AISettings, provider: str | None, model: str | None
) -> AISettings:
    """The settings one request runs with, when it picks its provider or model.

    `AI_BASE_URL` names the host of the **configured** provider. When a
    request picks another provider, the adapters would build their URL from it
    all the same. With `AI_PROVIDER=openai_compatible` pointing at a third-party
    host, a request asking for `anthropic` then sent `ANTHROPIC_API_KEY` to
    that host. So the host follows the configured provider only: another
    provider gets its adapter's default endpoint. `max_tokens_parameter` is kept
    because it describes the model's dialect, not a host, and carries no secret.
    """
    selected = provider or configured.provider
    update: dict[str, object] = {
        "provider": selected,
        "model": model if model is not None else configured.model,
    }
    if selected != configured.provider:
        update["base_url"] = ""
    return configured.model_copy(update=update)


def build_structure_analyzer(
    settings: AISettings | None = None, keys: ProviderKeys | None = None
) -> StructureAnalyzer:
    settings = settings or load_ai_settings()
    keys = keys or load_provider_keys()

    try:
        adapter_cls = _REGISTRY[settings.provider]
    except KeyError:
        raise UnsupportedProviderError(settings.provider, supported_providers()) from None

    attribute = _KEY_FOR.get(settings.provider, "")
    api_key = getattr(keys, attribute, "") if attribute else ""
    if attribute and not api_key and settings.provider not in _KEY_OPTIONAL:
        raise AnalyzerError(
            f"Aucune clé configurée pour '{settings.provider}'. Renseigner {attribute.upper()}.",
            details={"provider": settings.provider},
        )

    analyzer: StructureAnalyzer = adapter_cls(settings, api_key)
    return analyzer


def _has_what_it_needs(name: str, keys: ProviderKeys) -> bool:
    if name == "fake":
        return fixtures_available()
    attribute = _KEY_FOR.get(name, "")
    return not attribute or name in _KEY_OPTIONAL or bool(getattr(keys, attribute, ""))


def missing_configuration(
    settings: AISettings | None = None, keys: ProviderKeys | None = None
) -> list[str]:
    """The environment variables to set before the active provider can answer.

    Empty when nothing is missing. `AI_PROVIDER` comes alone when the provider
    is unset, unknown, or `fake` without its fixtures (the Docker image): what
    else is needed depends on the provider chosen.
    """
    settings = settings or load_ai_settings()
    keys = keys or load_provider_keys()
    provider = settings.provider
    if provider not in _REGISTRY or (provider == "fake" and not fixtures_available()):
        return ["AI_PROVIDER"]
    missing: list[str] = []
    if not _has_what_it_needs(provider, keys):
        missing.append(_KEY_FOR[provider].upper())
    if provider != "fake" and not settings.model:
        missing.append("AI_MODEL")
    if provider == "openai_compatible" and not settings.base_url:
        missing.append("AI_BASE_URL")
    return missing


def provider_status(
    settings: AISettings | None = None, keys: ProviderKeys | None = None
) -> dict[str, object]:
    """What `GET /ai/providers` needs (#54).

    Reports whether each provider is configured — **never the key**, not even
    its length or prefix — and, for the active one, which variables are still
    missing, so an unconfigured stack says what to set instead of failing at
    the first analysis.
    """
    settings = settings or load_ai_settings()
    keys = keys or load_provider_keys()
    missing = missing_configuration(settings, keys)
    return {
        "active": {
            "provider": settings.provider,
            "model": settings.model or None,
            "configured": not missing,
            "missing": missing,
        },
        "available": [
            {"provider": name, "configured": _has_what_it_needs(name, keys)}
            for name in supported_providers()
        ],
    }
