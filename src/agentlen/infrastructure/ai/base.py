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

from agentlen.application.dto.mapping_document import document_to_mapping
from agentlen.application.errors import AnalyzerError
from agentlen.application.ports.tool_executor import ImportAgentToolExecutor
from agentlen.domain.errors import AgentMaxIterationsError
from agentlen.domain.model.mapping import Mapping, MappingProposal
from agentlen.infrastructure.ai.prompts.analysis import PROMPT_VERSION, wrap_as_data
from agentlen.infrastructure.ai.sanitizer import sanitize_samples, sanitize_value
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
    #: Set when the model's arguments were not a JSON object. The loop sends it
    #: back as the tool's result instead of running the tool: the model can fix
    #: a malformed call, not a 500 it never sees (#152).
    arguments_error: str | None = None

    @classmethod
    def from_model(cls, call_id: str, name: str, arguments: Any) -> ToolCall:
        """Read the arguments as the provider sent them.

        OpenAI sends a JSON string; Anthropic, and some OpenAI-compatible hosts,
        send the object itself. Absent arguments are an empty object.
        """
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else None
            except (ValueError, RecursionError):
                return cls(call_id, name, {}, "Tool arguments are not valid JSON.")
        if arguments is None:
            return cls(call_id, name, {})
        if not isinstance(arguments, dict):
            return cls(call_id, name, {}, "Tool arguments must be a JSON object.")
        return cls(call_id, name, arguments)


def tool_result_content(result: dict[str, Any]) -> str:
    """A tool result as it goes back to the model: its JSON, fenced as data.

    Results carry trace content — field paths, sample values — and went back as
    bare `json.dumps`, which escapes neither `<` nor `>`. A value holding the
    closing delimiter left the data block the prompt builds everywhere else
    (#152).
    """
    return wrap_as_data(json.dumps(result, ensure_ascii=False))


async def _run_tool(call: ToolCall, executor: ImportAgentToolExecutor) -> dict[str, Any]:
    """The executor's answer, or the reason the call could not be read."""
    if call.arguments_error is not None:
        return {"error": call.arguments_error}
    return await executor.execute(call.name, call.arguments)


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
    #: Reprend la constante du builder plutôt que de la recopier : le descriptor
    #: n'a d'intérêt que s'il nomme le prompt réellement envoyé, et deux
    #: littéraux séparés divergent au premier changement de formulation.
    prompt_version = PROMPT_VERSION

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
                        try:
                            parsed: dict[str, Any] = response.json()
                        except ValueError as exc:
                            # Une base_url qui vise un proxy ou un mauvais
                            # chemin répond volontiers 200 avec du HTML. Sans
                            # cette garde, json.JSONDecodeError remontait tel
                            # quel et donnait un 500 générique.
                            raise AnalyzerError(
                                f"Le fournisseur {self.provider_name} a répondu "
                                f"{response.status_code} sans JSON exploitable. "
                                "Vérifier AI_BASE_URL : le point d'accès ne "
                                "semble pas être celui d'une API de modèles.",
                                details={
                                    "status": response.status_code,
                                    "content_type": response.headers.get("content-type", ""),
                                },
                            ) from exc
                        return parsed
                    diagnostic = _provider_diagnostic(response)
                    if response.status_code not in RETRYABLE_STATUS:
                        raise AnalyzerError(
                            f"Le fournisseur {self.provider_name} a répondu "
                            f"{response.status_code}"
                            + (f" : {diagnostic['provider_message']}" if diagnostic else "")
                            + ".",
                            details={"status": response.status_code, **(diagnostic or {})},
                        )
                    last = AnalyzerError(f"HTTP {response.status_code}")
                    logger.warning(
                        "Appel %s: HTTP %d (%s), tentative %d/%d",
                        self.provider_name,
                        response.status_code,
                        (diagnostic or {}).get("request_id", "sans request_id"),
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

    async def _next_turn(self, messages: list[dict[str, Any]]) -> ModelTurn:
        """One round trip, the reply read into a `ModelTurn`.

        The body is JSON by now (`_post` sees to that) but not necessarily in the
        provider's shape: a proxy answering `[]`, a `choices` entry that is a
        string, a `tool_use` block without an `id`. `_parse_turn` indexes straight
        into it, and the bare `AttributeError` or `KeyError` reached the catch-all
        500 (#152). Only the exception class is kept: its message can quote the body.
        """
        payload = await self._post(self._build_request(messages))
        try:
            return self._parse_turn(payload)
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AnalyzerError(
                f"Le fournisseur {self.provider_name} a renvoyé une réponse de forme inattendue.",
                details={"provider": self.provider_name, "cause": type(exc).__name__},
            ) from exc

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
            turn = await self._next_turn(messages)

            if turn.stop_reason != "tool_use":
                return self._to_proposal(turn.text)

            results: list[tuple[ToolCall, dict[str, Any]]] = []
            for call in turn.tool_calls:
                # The executor refuses anything outside the whitelist and
                # returns {"error": ...} rather than raising, so one bad tool
                # name does not end the conversation. Unreadable arguments are
                # answered the same way, before they reach it.
                results.append((call, await _run_tool(call, tool_executor)))

            messages.append(self._assistant_message(turn))
            messages.extend(self._tool_results_message(results))

        raise AgentMaxIterationsError(self._settings.max_iterations)

    async def refine(
        self,
        proposal: MappingProposal,
        user_message: str,
        tool_executor: ImportAgentToolExecutor,
        history: tuple[dict[str, str | int], ...] = (),
    ) -> MappingProposal:
        """Apply an operator's correction and re-validate through the tools."""
        from agentlen.infrastructure.ai.prompts.analysis import build_refinement_prompt

        instruction = _build_refinement_instruction(history, user_message)
        prompt = build_refinement_prompt(
            mapping=_mapping_payload(proposal.mapping), instruction=instruction
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for _ in range(self._settings.max_refinement_iterations):
            turn = await self._next_turn(messages)
            if turn.stop_reason != "tool_use":
                return self._to_proposal(turn.text)
            results = [(call, await _run_tool(call, tool_executor)) for call in turn.tool_calls]
            messages.append(self._assistant_message(turn))
            messages.extend(self._tool_results_message(results))

        raise AgentMaxIterationsError(self._settings.max_refinement_iterations)

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
        try:
            return MappingProposal(
                mapping=_document_to_mapping(payload["mapping"]),
                rationale=_objects(payload.get("rationale") or (), "rationale"),
                ambiguities=_objects(payload["ambiguities"], "ambiguities"),
                unmapped_fields=_objects(payload["unmapped_fields"], "unmapped_fields"),
                analyzer_descriptor=self.descriptor,
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            # Seules les trois clés de premier niveau étaient vérifiées : une
            # règle sans `source`, un `mapping` qui est une chaîne, un
            # `source_format` inventé, et l'exception nue remontait jusqu'au
            # fourre-tout 500. Le contrat du module annonce un 502, et le front
            # ne propose un réessai que sur un 502. Un modèle qui se trompe de
            # forme est un cas normal, pas un bug de l'application.
            raise AnalyzerError(
                "Le document renvoyé par le modèle ne respecte pas "
                f"MAPPING_CONTRACT.md §5 : {type(exc).__name__} {exc}.",
                details={"provider": self.provider_name, "cause": type(exc).__name__},
            ) from exc


# ---------------------------------------------------------------------------
# helpers shared by adapters and the fake
# ---------------------------------------------------------------------------


# One stored turn is a short summary (see `RefineMapping`), but a row written by
# an older deployment can be a whole mapping document. Bounding each turn here
# keeps a long conversation from pushing the prompt past the provider's context
# window whatever is already in the table.
MAX_HISTORY_MESSAGE_LENGTH = 500


def _build_refinement_instruction(
    history: tuple[dict[str, str | int], ...], user_message: str
) -> str:
    """Prefix the operator's instruction with the recent conversation, if any.

    `json.dumps(())` is `"[]"`, which is truthy — testing the serialized text
    made the no-history branch unreachable and sent `Conversation récente :\n[]`
    on every first refinement. The emptiness test belongs on `history` itself.
    """
    if not history:
        return user_message
    turns = [
        {
            **turn,
            "content": _truncate(str(turn.get("content", ""))),
        }
        for turn in history
    ]
    history_text = json.dumps(turns, ensure_ascii=False)
    return f"Conversation récente :\n{history_text}\n\nNouvelle instruction :\n{user_message}"


def _truncate(text: str, limit: int = MAX_HISTORY_MESSAGE_LENGTH) -> str:
    return text if len(text) <= limit else text[:limit] + "…[truncated]"


def _extract_json(text: str) -> dict[str, Any] | None:
    """Find the JSON object in a reply that may be wrapped in prose or fences.

    Only an object counts. `json.loads` takes `42`, `"text"` or a list just as
    well, and `"mapping" in 42` then raised `TypeError`, a 500 (#152). Content
    that is not even a string (some compatible hosts send a list of parts) is no
    document either.
    """
    if not isinstance(text, str):
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("```")[1]
        if candidate.startswith("json"):
            candidate = candidate[4:]
    parsed = _loads_object(candidate)
    if parsed is not None:
        return parsed
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        return None
    return _loads_object(candidate[start : end + 1])


def _loads_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except (ValueError, RecursionError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _objects(value: Any, key: str) -> tuple[dict[str, Any], ...]:
    """A section of the answer as MAPPING_CONTRACT.md §5 gives it: a list of objects.

    The response schema types these `list[dict]`. A list of strings was stored as
    it came, and the proposal then failed its own response with a 500.
    """
    if not isinstance(value, list | tuple) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"'{key}' must be a list of objects")
    return tuple(value)


def _document_to_mapping(document: Any) -> Mapping:
    """The model's `mapping`, read by the same checked converter as the tools.

    A second copy here indexed it without guards: a string where an operator
    belongs came through, and `mapping_validator` then raised on it (#152). A
    proposal keeps its own defaults for what a model may leave out.
    """
    if isinstance(document, dict):
        document = {"name": "proposed", "source_format": "jsonl", **document}
    return document_to_mapping(document)


def _mapping_payload(mapping: Mapping) -> dict[str, Any]:
    from agentlen.infrastructure.persistence.repositories.mapping_codec import (
        mapping_to_document,
    )

    return mapping_to_document(mapping)


#: Le message d'erreur d'un fournisseur tient en une phrase. Borné malgré tout :
#: un hôte openai_compatible arbitraire n'est pas tenu d'être aussi sobre.
MAX_PROVIDER_MESSAGE = 300


def _provider_diagnostic(response: httpx.Response) -> dict[str, str] | None:
    """Ce que le fournisseur a dit du refus, et sous quel identifiant.

    La règle du module — aucune clé, aucun contenu de trace dans un log — vise
    les erreurs de connexion, dont le message porte l'URL et l'URL parfois la
    clé. Elle ne vise pas le corps JSON qu'un fournisseur renvoie exprès pour
    expliquer un refus : sans lui, un solde épuisé, une clé invalide et un
    modèle inexistant donnent tous les trois « a répondu 400 », et le
    `request_id` que le support demande est perdu. L'URL, elle, n'est jamais
    reprise ici.
    """
    diagnostic: dict[str, str] = {}

    request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
    if request_id:
        diagnostic["request_id"] = request_id[:128]

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        error = error if isinstance(error, dict) else payload
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            # Passé au caviardeur, pas simplement tronqué : un proxy mal réglé
            # renvoie volontiers l'en-tête Authorization dans son message
            # d'erreur, et ce message part maintenant jusqu'au client HTTP.
            diagnostic["provider_message"] = sanitize_value(
                message.strip(), max_value_length=MAX_PROVIDER_MESSAGE
            )
        kind = error.get("type")
        if isinstance(kind, str) and kind.strip():
            diagnostic["provider_error_type"] = kind.strip()[:64]

    return diagnostic or None


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
