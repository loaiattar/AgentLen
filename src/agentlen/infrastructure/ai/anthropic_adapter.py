"""Anthropic Messages API.

Everything specific to Anthropic is confined here: the `x-api-key` header, the
`anthropic-version` header, the content-block shape, and `tool_use` blocks. The
rest of the application only ever sees a `MappingProposal`.
"""

from __future__ import annotations

from typing import Any

from agentlen.infrastructure.ai.agent_tools import to_anthropic
from agentlen.infrastructure.ai.base import BaseAnalyzerAdapter, ModelTurn, ToolCall

DEFAULT_BASE_URL = "https://api.anthropic.com"
API_VERSION = "2023-06-01"


class AnthropicAnalyzer(BaseAnalyzerAdapter):
    provider_name = "anthropic"

    def _endpoint(self) -> str:
        base = (self._settings.base_url or DEFAULT_BASE_URL).rstrip("/")
        return f"{base}/v1/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    def _build_request(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": self._settings.model,
            "max_tokens": self._settings.max_output_tokens,
            "tools": to_anthropic(),
            "messages": messages,
        }

    def _parse_turn(self, payload: dict[str, Any]) -> ModelTurn:
        blocks = payload.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = tuple(
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input", {}))
            for b in blocks
            if b.get("type") == "tool_use"
        )
        return ModelTurn(
            stop_reason=payload.get("stop_reason", "end_turn"),
            text=text,
            tool_calls=calls,
            raw=payload,
        )

    def _assistant_message(self, turn: ModelTurn) -> dict[str, Any]:
        # Echo the blocks back verbatim: Anthropic matches tool results to the
        # tool_use blocks of the exact assistant turn that requested them.
        return {"role": "assistant", "content": (turn.raw or {}).get("content", [])}

    def _tool_results_message(
        self, results: list[tuple[ToolCall, dict[str, Any]]]
    ) -> dict[str, Any]:
        import json

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
                for call, result in results
            ],
        }
