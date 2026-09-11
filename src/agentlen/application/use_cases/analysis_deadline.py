"""An overall deadline on one analysis: a whole proposal or a whole refinement.

The adapters bound one call (`AI_TIMEOUT_SECONDS`) and one loop
(`AI_MAX_ITERATIONS`), not their product, which reaches about forty minutes
while the reverse proxy gives up after 600 s. `ProposeMapping` and
`RefineMapping` each make one analyzer call; this decorator bounds it end to
end and cancels it on expiry. It wraps the port so that
`interfaces/http/dependencies.py` applies it to every analyzer it builds.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

from agentlen.application.errors import AnalyzerTimeoutError
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.application.ports.tool_executor import ImportAgentToolExecutor
from agentlen.domain.model.mapping import MappingProposal
from agentlen.domain.model.profile import FileProfile


class DeadlineBoundAnalyzer:
    """A `StructureAnalyzer` whose every analysis must finish in time."""

    def __init__(self, inner: StructureAnalyzer, total_timeout_seconds: float) -> None:
        self._inner = inner
        self._seconds = total_timeout_seconds

    @property
    def descriptor(self) -> dict[str, Any]:
        return self._inner.descriptor

    async def run_agent_loop(
        self,
        profile: FileProfile,
        tool_executor: ImportAgentToolExecutor,
        hint: str | None = None,
    ) -> MappingProposal:
        return await self._bounded(self._inner.run_agent_loop(profile, tool_executor, hint))

    async def refine(
        self,
        proposal: MappingProposal,
        user_message: str,
        tool_executor: ImportAgentToolExecutor,
        history: tuple[dict[str, str | int], ...] = (),
    ) -> MappingProposal:
        return await self._bounded(
            self._inner.refine(proposal, user_message, tool_executor, history)
        )

    async def _bounded(self, call: Awaitable[MappingProposal]) -> MappingProposal:
        deadline = asyncio.timeout(self._seconds)
        try:
            async with deadline:
                return await call
        except TimeoutError:
            # A TimeoutError raised by the call itself is not this deadline.
            if not deadline.expired():
                raise
            raise AnalyzerTimeoutError(self._seconds) from None
