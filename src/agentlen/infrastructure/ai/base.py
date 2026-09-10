"""Shared skeleton for every provider adapter.

Holds what does not depend on the provider: the agent loop, retries, timeouts,
and the conversion of a model's answer into a `MappingProposal`. Each adapter
supplies only the three provider-specific pieces — how to send a request, how to
read tool calls out of the reply, and how to send results back.

Two rules apply to everything here:

**No key, no trace content, ever reaches a log.** Connection errors habitually
carry the URL and the URL carries the credential, so only exception classes and
status codes are logged.

**A non-conforming answer is an error, never a patched-up mapping.** If the
model returns something that is not a valid proposal, that surfaces as a 502.
Silently repairing it would mean importing data under rules nobody authored.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from typing import Any

import httpx

from agentlen.application.errors import AnalyzerError
from agentlen.application.ports.tool_executor import ImportAgentToolExecutor
from agentlen.domain.errors import AgentMaxIterationsError
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping, MappingProposal
from agentlen.infrastructure.ai.sanitizer import sanitize_samples
from agentlen.infrastructure.config.settings import AISettings

logger = logging.getLogger("agentlen.ai")

#: Retried with backoff. 429 is rate limiting, 5xx is the provider having a bad
#: minute — both are worth a second attempt. A 400 or 401 is not: retrying a
#: malformed request or a bad key just wastes time.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4

#: Below this, the provider answered; at or above it, it refused.
HTTP_ERROR_THRESHOLD = 400


@dataclass(frozen=True)
class ToolCall:
    """One tool invocation requested by the model, provider-neutral."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """One reply, normalised across providers."""

    #: "tool_use" when the model wants tools run, "end_turn" when it has answered.
    stop_reason: str
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    raw: dict[str, Any] | None = None


class BaseAnalyzerAdapter:
    """Everything a provider adapter shares."""

    provider_name = "base"
    prompt_version = "analysis-v1"

    def __init__(self, settings: AISettings, api_key: str = "") -> None:
        if not settings.model:
            raise AnalyzerError(
                "AI_MODEL n'est pas défini. Le modèle vient de la configuration, "
                "jamais du code (ADR-006)."
            )
        self._settings = settings
        self._api_key = api_key

    # -- to be provided by each adapter ------------------------------------

    def _endpoint(self) -> str:
        raise NotImplementedError

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _build_request(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    def _parse_turn(self, payload: dict[str, Any]) -> ModelTurn:
        raise NotImplementedError

    def _tool_results_message(
        self, results: list[tuple[ToolCall, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """The messages carrying these results back, in the provider's shape.

        Always a list, even when the provider wants a single message holding
        every result: the loop extends `messages` with it, and a lone dict
        returned here would be appended as a nested element instead.
        """
        raise NotImplementedError

    def _assistant_message(self, turn: ModelTurn) -> Any:
        raise NotImplementedError

    # -- shared ------------------------------------------------------------

    @property
    def descriptor(self) -> dict[str, Any]:
        """Traceability only — provider, model, prompt version. Never the key."""
        return {
            "provider": self.provider_name,
            "model": self._settings.model,
            "prompt_version": self.prompt_version,
        }

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """One request, with backoff on transient failures."""
        last: Exception | None = None
        async with httpx.AsyncClient(timeout=self._settings.timeout_seconds) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await client.post(
                        self._endpoint(), headers=self._headers(), json=body
                    )
                except httpx.RequestError as exc:
                    # Only the class: the message embeds the URL, which may
                    # embed a key for self-hosted endpoints.
                    last = exc
                    logger.warning(
                        "Appel %s échoué (%s), tentative %d/%d",
                        self.provider_name,
                        type(exc).__name__,
                        attempt,
                        MAX_ATTEMPTS,
                    )
                else:
                    if response.status_code < HTTP_ERROR_THRESHOLD:
                        parsed: dict[str, Any] = response.json()
                        return parsed
                    if response.status_code not in RETRYABLE_STATUS:
                        raise AnalyzerError(
                            f"Le fournisseur {self.provider_name} a répondu "
                            f"{response.status_code}.",
                            details={"status": response.status_code},
                        )
                    last = AnalyzerError(f"HTTP {response.status_code}")
                    logger.warning(
                        "Appel %s: HTTP %d, tentative %d/%d",
                        self.provider_name,
                        response.status_code,
                        attempt,
                        MAX_ATTEMPTS,
                    )

                if attempt < MAX_ATTEMPTS:
                    # Exponential, with jitter so several workers retrying after
                    # the same rate limit do not line up and hit it again together.
                    delay = (2 ** (attempt - 1)) * 0.5
                    await asyncio.sleep(delay + random.uniform(0, delay / 2))  # noqa: S311

        raise AnalyzerError(
            f"Le fournisseur {self.provider_name} est injoignable après {MAX_ATTEMPTS} tentatives.",
            details={"cause": type(last).__name__ if last else "unknown"},
        )

    async def run_agent_loop(
        self,
        profile: Any,
        tool_executor: ImportAgentToolExecutor,
        hint: str | None = None,
    ) -> MappingProposal:
        """Observe → call tools → observe → answer, until the model is done.

        Bounded by `max_iterations`: a model that keeps asking for tools without
        ever answering must fail loudly rather than bill indefinitely.
        """
        from agentlen.infrastructure.ai.prompts.analysis import build_analysis_prompt

        # Routed through the sanitizer even when empty: the NewType is what
        # makes "these samples were redacted" checkable rather than a comment,
        # and passing a bare list around it would defeat the point.
        prompt = build_analysis_prompt(
            profile=_profile_payload(profile),
            samples=sanitize_samples([]),
            target_schema=_target_schema(),
            allowed_operators=_allowed_operators(),
            hint=hint,
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for _ in range(self._settings.max_iterations):
            turn = self._parse_turn(await self._post(self._build_request(messages)))

            if turn.stop_reason != "tool_use":
                return self._to_proposal(turn.text)

            results: list[tuple[ToolCall, dict[str, Any]]] = []
            for call in turn.tool_calls:
                # The executor refuses anything outside the whitelist and
                # returns {"error": ...} rather than raising, so one bad tool
                # name does not end the conversation.
                results.append((call, await tool_executor.execute(call.name, call.arguments)))

            messages.append(self._assistant_message(turn))
            messages.extend(self._tool_results_message(results))

        raise AgentMaxIterationsError(self._settings.max_iterations)

    async def refine(
        self,
        proposal: MappingProposal,
        user_message: str,
        tool_executor: ImportAgentToolExecutor,
    ) -> MappingProposal:
        """Apply an operator's correction and re-validate through the tools."""
        from agentlen.infrastructure.ai.prompts.analysis import build_refinement_prompt

        prompt = build_refinement_prompt(
            mapping=_mapping_payload(proposal.mapping), instruction=user_message
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for _ in range(self._settings.max_conversation_turns):
            turn = self._parse_turn(await self._post(self._build_request(messages)))
            if turn.stop_reason != "tool_use":
                return self._to_proposal(turn.text)
            results = [
                (call, await tool_executor.execute(call.name, call.arguments))
                for call in turn.tool_calls
            ]
            messages.append(self._assistant_message(turn))
            messages.extend(self._tool_results_message(results))

        raise AgentMaxIterationsError(self._settings.max_conversation_turns)

    def _to_proposal(self, text: str) -> MappingProposal:
        """Parse the model's answer into the one shape the application accepts.

        Anything that does not parse is an error. `ambiguities` and
        `unmapped_fields` are required by MAPPING_CONTRACT.md §5 — an adapter
        that returns neither is incomplete, so their absence is reported rather
        than filled in with empty lists.
        """
        payload = _extract_json(text)
        if payload is None:
            raise AnalyzerError(
                "Le fournisseur n'a pas renvoyé de document JSON exploitable.",
                details={"provider": self.provider_name},
            )
        for required in ("mapping", "ambiguities", "unmapped_fields"):
            if required not in payload:
                raise AnalyzerError(
                    f"Réponse non conforme : '{required}' manquant (MAPPING_CONTRACT.md §5).",
                    details={"provider": self.provider_name, "missing": required},
                )
        return MappingProposal(
            mapping=_document_to_mapping(payload["mapping"]),
            rationale=tuple(payload.get("rationale", ())),
            ambiguities=tuple(payload["ambiguities"]),
            unmapped_fields=tuple(payload["unmapped_fields"]),
            analyzer_descriptor=self.descriptor,
        )


# ---------------------------------------------------------------------------
# helpers shared by adapters and the fake
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any] | None:
    """Find the JSON object in a reply that may be wrapped in prose or fences."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("```")[1]
        if candidate.startswith("json"):
            candidate = candidate[4:]
    try:
        parsed: dict[str, Any] = json.loads(candidate)
        return parsed
    except json.JSONDecodeError:
        pass
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(candidate[start : end + 1])
        return parsed
    except json.JSONDecodeError:
        return None


def _document_to_mapping(document: dict[str, Any]) -> Mapping:
    from uuid import uuid4

    return Mapping(
        id=uuid4(),
        name=document.get("name", "proposed"),
        version=1,
        source_format=document.get("source_format", "jsonl"),
        entities=tuple(
            EntityMapping(
                target=entity["target"],
                natural_key=tuple(entity.get("natural_key", ())),
                iterate=entity.get("iterate"),
                parent=entity.get("parent"),
                fields=tuple(
                    FieldRule(
                        target=rule["target"],
                        source=rule["source"],
                        required=rule.get("required", False),
                        operators=tuple(rule.get("operators", ())),
                    )
                    for rule in entity.get("fields", ())
                ),
            )
            for entity in document.get("entities", ())
        ),
    )


def _mapping_payload(mapping: Mapping) -> dict[str, Any]:
    from agentlen.infrastructure.persistence.repositories.mapping_codec import (
        mapping_to_document,
    )

    return mapping_to_document(mapping)


def _profile_payload(profile: Any) -> dict[str, Any]:
    if isinstance(profile, dict):
        return profile
    return {
        "format": getattr(profile, "format", "jsonl"),
        "record_count": getattr(profile, "record_count", 0),
        "sampled_records": getattr(profile, "sampled_records", 0),
        "fields": [
            {
                "path": f.path,
                "types": list(f.types),
                "null_ratio": f.null_ratio,
                "distinct_ratio": f.distinct_ratio,
                "examples": list(f.examples),
            }
            for f in getattr(profile, "fields", ())
        ],
    }


def _target_schema() -> dict[str, Any]:
    # Imported by name, not read with getattr and a default: these two feed the
    # prompt's contract sections, and a silent fallback here ships an empty
    # schema or an empty whitelist to the model with nothing to show for it.
    from agentlen.domain.services.mapping_validator import _SCHEMA

    return {target: sorted(fields) for target, fields in _SCHEMA.items()}


def _allowed_operators() -> list[str]:
    from agentlen.domain.services.mapping_validator import OPERATOR_WHITELIST

    return sorted(OPERATOR_WHITELIST)
