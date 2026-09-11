"""OpenAI Chat Completions, and every API that speaks the same dialect.

`OpenAIAnalyzer` targets OpenAI itself. `OpenAICompatibleAnalyzer` is the same
adapter pointed somewhere else by `AI_BASE_URL` — which is how Groq, Mistral,
DeepSeek, Together, OpenRouter, Fireworks, Azure OpenAI, and locally Ollama,
LM Studio or vLLM are reached, without a line of provider-specific code.

That covers the transport. It does **not** guarantee the agent loop works
everywhere: tool calling is the least uniform part of the OpenAI-compatible
contract, and small local models often implement it poorly or not at all. The
adapter reaches them; whether a given model can drive the loop is a property of
that model, and `docs/verification/ai-models-report.md` (#22) is where that gets
measured rather than assumed.
"""

from __future__ import annotations

import json
from typing import Any

from agentlen.application.errors import AnalyzerError
from agentlen.infrastructure.ai.agent_tools import to_openai
from agentlen.infrastructure.ai.base import BaseAnalyzerAdapter, ModelTurn, ToolCall

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIAnalyzer(BaseAnalyzerAdapter):
    provider_name = "openai"
    default_base_url = DEFAULT_BASE_URL

    def _endpoint(self) -> str:
        base = (self._settings.base_url or self.default_base_url).rstrip("/")
        return f"{base}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # `Bearer ` sans jeton derrière : certains hôtes locaux rejettent
        # l'en-tête vide plutôt que de l'ignorer. Absent vaut mieux que vide.
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_request(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": self._settings.model,
            self._settings.max_tokens_parameter: self._settings.max_output_tokens,
            "tools": to_openai(),
            "messages": messages,
        }

    def _parse_turn(self, payload: dict[str, Any]) -> ModelTurn:
        choices = payload.get("choices") or []
        if not choices:
            raise AnalyzerError(
                "Réponse sans 'choices' — le point d'accès n'est probablement pas "
                "compatible OpenAI.",
                details={"provider": self.provider_name},
            )
        message = choices[0].get("message", {})
        raw_calls = message.get("tool_calls") or []

        calls = []
        for call in raw_calls:
            function = call.get("function", {})
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                # A model emitting unparsable arguments is a model error, not a
                # crash: reported as such so the loop can surface it.
                raise AnalyzerError(
                    f"Arguments d'outil illisibles pour '{function.get('name')}'.",
                    details={"provider": self.provider_name},
                ) from None
            calls.append(
                ToolCall(id=call.get("id", ""), name=function.get("name", ""), arguments=arguments)
            )

        return ModelTurn(
            stop_reason="tool_use" if calls else "end_turn",
            text=message.get("content") or "",
            tool_calls=tuple(calls),
            raw=payload,
        )

    def _assistant_message(self, turn: ModelTurn) -> dict[str, Any]:
        choices = (turn.raw or {}).get("choices") or [{}]
        message: dict[str, Any] = choices[0].get("message", {})
        return message

    def _tool_results_message(
        self, results: list[tuple[ToolCall, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        # OpenAI expects one message per result, not one message holding them
        # all — the opposite of Anthropic.
        return [
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            }
            for call, result in results
        ]


class OpenAICompatibleAnalyzer(OpenAIAnalyzer):
    """Any endpoint speaking the OpenAI dialect. `AI_BASE_URL` is required."""

    provider_name = "openai_compatible"
    default_base_url = ""

    def _endpoint(self) -> str:
        if not self._settings.base_url:
            raise AnalyzerError(
                "AI_BASE_URL est obligatoire avec AI_PROVIDER=openai_compatible : "
                "c'est lui qui désigne le fournisseur (Groq, Mistral, Ollama…)."
            )
        return f"{self._settings.base_url.rstrip('/')}/chat/completions"
