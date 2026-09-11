"""Session exploration and source provenance (API.md §6)."""

from fastapi import APIRouter, Response

from agentlen.application.dto.exploration import (
    RawRecordDetail,
    SessionDetail,
    SessionWithCalls,
    TimelineEvent,
)
from agentlen.application.use_cases.query_exploration import QueryExploration
from agentlen.interfaces.http.dependencies import ExplorationQueriesDep
from agentlen.interfaces.http.filters import FiltersDep
from agentlen.interfaces.http.ids import EntityId
from agentlen.interfaces.http.pagination import (
    TOTAL_COUNT_RESPONSE,
    Paginated,
    Windowed,
    paginate,
    window,
)
from agentlen.interfaces.http.schemas.common import Page

router = APIRouter(tags=["exploration"])


@router.get("/sessions", response_model=Page[SessionDetail])
async def sessions(
    filters: FiltersDep, params: Paginated, queries: ExplorationQueriesDep
) -> Page[SessionDetail]:
    items, total = await queries.sessions(filters, params.limit, params.offset)
    return paginate(items, total, params)


@router.get("/sessions/{id}", response_model=SessionWithCalls)
async def session(id: EntityId, queries: ExplorationQueriesDep) -> SessionWithCalls:
    return await QueryExploration(queries).session(id)


@router.get(
    "/sessions/{id}/timeline",
    response_model=list[TimelineEvent],
    summary="Ordered events of one session — a bounded bare array (API.md §1)",
    responses={200: TOTAL_COUNT_RESPONSE},
)
async def timeline(
    id: EntityId, params: Windowed, response: Response, queries: ExplorationQueriesDep
) -> list[TimelineEvent]:
    return window(await QueryExploration(queries).timeline(id), params, response)


@router.get("/records/{raw_record_id}", response_model=RawRecordDetail)
async def record(raw_record_id: EntityId, queries: ExplorationQueriesDep) -> RawRecordDetail:
    return await QueryExploration(queries).record(raw_record_id)
