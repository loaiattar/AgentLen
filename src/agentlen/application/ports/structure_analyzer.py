from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from agentlen.domain.model.mapping import MappingProposal
from agentlen.domain.model.profile import FileProfile

if TYPE_CHECKING:
    from agentlen.application.ports.tool_executor import ImportAgentToolExecutor


class StructureAnalyzer(Protocol):
    """Port for the AI import agent.

    The domain and use cases only depend on this interface.
    No reference to any provider, model name, or SDK.
    """

    async def run_agent_loop(
        self,
        profile: FileProfile,
        tool_executor: ImportAgentToolExecutor,
        hint: str | None = None,
    ) -> MappingProposal:
        """Run the autonomous agentic loop.

        The model calls tools (validate_mapping, preview_import…)
        without user intervention until it produces a valid MappingProposal
        or raises AgentMaxIterationsError.
        """
        ...

    async def refine(
        self,
        proposal: MappingProposal,
        user_message: str,
        tool_executor: ImportAgentToolExecutor,
        history: tuple[dict[str, str | int], ...] = (),
    ) -> MappingProposal:
        """Incorporate a user correction and re-validate via tools."""
        ...

    @property
    def descriptor(self) -> dict[str, Any]:
        """Provider, model, prompt version — for traceability only."""
        ...
