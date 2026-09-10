"""Resource lookup and deterministic timeline composition."""

from datetime import UTC, datetime

from agentlen.application.dto.exploration import RawRecordDetail, SessionWithCalls, TimelineEvent
from agentlen.application.errors import NotFoundError
from agentlen.application.ports.exploration_queries import ExplorationQueries


class QueryExploration:
    def __init__(self, queries: ExplorationQueries) -> None:
        self._queries = queries

    async def session(self, identifier: int) -> SessionWithCalls:
        result = await self._queries.session(identifier)
        if result is None:
            raise NotFoundError("Session", identifier)
        return result

    async def record(self, identifier: int) -> RawRecordDetail:
        result = await self._queries.record(identifier)
        if result is None:
            raise NotFoundError("Raw record", identifier)
        return result

    async def timeline(self, identifier: int) -> list[TimelineEvent]:
        detail = await self.session(identifier)
        events = [TimelineEvent("model_call", c) for c in detail.model_calls]
        events.extend(TimelineEvent("tool_call", c) for c in detail.tool_calls)
        # Undated events follow dated events. Stable ties use sequence, type, id.
        return sorted(
            events,
            key=lambda e: (
                e.event.started_at is None,
                e.event.started_at or datetime.max.replace(tzinfo=UTC),
                e.event.sequence_index,
                e.type,
                e.event.id,
            ),
        )
