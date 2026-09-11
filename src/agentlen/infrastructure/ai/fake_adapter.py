"""Replays recorded proposals. No network, no key, no credit spent.

This is what the CI runs. Every test that exercises the AI path uses it, which
is why the pipeline needs no provider account and why a contributor can run the
whole suite offline.

It is not a stub that returns a constant: it replays fixtures through the same
`_to_proposal` path as the real adapters, and it simulates the agent loop —
first turn asks for a tool, second answers. A double that skipped the loop would
let a broken loop pass the tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentlen.application.errors import AnalyzerError
from agentlen.application.ports.tool_executor import ImportAgentToolExecutor
from agentlen.domain.model.mapping import MappingProposal
from agentlen.infrastructure.ai.base import BaseAnalyzerAdapter
from agentlen.infrastructure.config.settings import AISettings

FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "ai_responses"
DEFAULT_FIXTURE = "tracelab_proposal.json"


class FakeAnalyzer(BaseAnalyzerAdapter):
    provider_name = "fake"

    def __init__(
        self,
        settings: AISettings | None = None,
        api_key: str = "",
        *,
        fixture: str = DEFAULT_FIXTURE,
        response_text: str | None = None,
    ) -> None:
        # The fake has a model name so `descriptor` is filled like the others;
        # the base class refuses an empty one.
        settings = settings or AISettings(provider="fake", model="fake-model-1")
        if not settings.model:
            settings = settings.model_copy(update={"model": "fake-model-1"})
        super().__init__(settings, api_key)
        self._fixture = fixture
        self._response_text = response_text
        self.tool_calls_made: list[str] = []

    def _load(self) -> str:
        if self._response_text is not None:
            return self._response_text
        path = FIXTURES / self._fixture
        if not path.exists():
            # `AISettings.provider` vaut `fake` par défaut, et les fixtures ne
            # sont présentes que dans une copie des sources. Un déploiement qui
            # oublie AI_PROVIDER échouait donc à l'analyse sur un nom de
            # fichier, sans rien qui désigne la cause. Le message la nomme.
            raise AnalyzerError(
                f"Fixture introuvable : {path}. Le fournisseur 'fake' rejoue des "
                "réponses enregistrées et n'existe que pour le développement — "
                "renseigner AI_PROVIDER (anthropic, openai ou openai_compatible) "
                "pour interroger un vrai modèle.",
                details={"provider": self.provider_name, "fixture": self._fixture},
            )
        return path.read_text(encoding="utf-8")

    async def run_agent_loop(
        self,
        profile: Any,
        tool_executor: ImportAgentToolExecutor,
        hint: str | None = None,
    ) -> MappingProposal:
        """Two turns, like a real run: ask a tool, then answer."""
        payload = json.loads(self._load())
        result = await tool_executor.execute("validate_mapping", {"mapping": payload["mapping"]})
        self.tool_calls_made.append("validate_mapping")
        if isinstance(result, dict) and result.get("error"):
            raise AnalyzerError(
                "L'outil validate_mapping a refusé la proposition rejouée.",
                details={"tool_error": str(result["error"])},
            )
        return self._to_proposal(self._load())

    async def refine(
        self,
        proposal: MappingProposal,
        user_message: str,
        tool_executor: ImportAgentToolExecutor,
        history: tuple[dict[str, str | int], ...] = (),
    ) -> MappingProposal:
        await tool_executor.execute("validate_mapping", {"mapping": {}})
        self.tool_calls_made.append("validate_mapping")
        return self._to_proposal(self._load())
