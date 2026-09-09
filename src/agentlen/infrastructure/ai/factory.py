"""Resolve `AI_PROVIDER` to an adapter.

ADR-006: adding a provider is a class and a registry line. This file is that
line — nothing else in the codebase mentions a provider by name.
"""

from __future__ import annotations

from agentlen.application.errors import AnalyzerError
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.infrastructure.ai.anthropic_adapter import AnthropicAnalyzer
from agentlen.infrastructure.ai.fake_adapter import FakeAnalyzer
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


def supported_providers() -> list[str]:
    return sorted(_REGISTRY)


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
    if attribute and not api_key:
        raise AnalyzerError(
            f"Aucune clé configurée pour '{settings.provider}'. Renseigner {attribute.upper()}.",
            details={"provider": settings.provider},
        )

    analyzer: StructureAnalyzer = adapter_cls(settings, api_key)
    return analyzer


def provider_status(
    settings: AISettings | None = None, keys: ProviderKeys | None = None
) -> dict[str, object]:
    """What `GET /ai/providers` needs (#54).

    Reports whether each provider is configured — **never the key**, not even
    its length or prefix.
    """
    settings = settings or load_ai_settings()
    keys = keys or load_provider_keys()
    return {
        "active": {"provider": settings.provider, "model": settings.model or None},
        "available": [
            {
                "provider": name,
                "configured": not _KEY_FOR.get(name) or bool(getattr(keys, _KEY_FOR[name], "")),
            }
            for name in supported_providers()
        ],
    }
