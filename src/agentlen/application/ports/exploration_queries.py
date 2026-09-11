"""Read port for session exploration; no storage types cross this boundary."""

from typing import Protocol

from agentlen.application.dto.dashboard import DashboardFilters
from agentlen.application.dto.exploration import RawRecordDetail, SessionDetail, SessionWithCalls


class ExplorationQueries(Protocol):
    async def sessions(
        self, filters: DashboardFilters, limit: int, offset: int
    ) -> tuple[list[SessionDetail], int]: ...
    async def session(self, identifier: int) -> SessionWithCalls | None: ...
    async def record(self, identifier: int) -> RawRecordDetail | None: ...
