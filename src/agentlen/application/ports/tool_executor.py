from __future__ import annotations

from typing import Any, Protocol


class ImportAgentToolExecutor(Protocol):
    """Port for executing agent tools.

    The AI adapter calls this; it never touches the database directly.
    All tool calls are routed through existing use cases and ports.
    """

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute one tool call requested by the agent.

        Returns a JSON-serialisable dict.
        If tool_name is not in the allowed whitelist, returns
        {'error': '...'} — never raises.
        """
        ...
