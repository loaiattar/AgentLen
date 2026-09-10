"""The filter set shared by the metric routes and `GET /sessions`.

Declared once, on purpose. API.md §6 promises that every chart point carries a
`filters` object that can be replayed verbatim on the session list — that only
holds if both ends parse the same names with the same types. Two hand-written
copies would drift, and the drill-down would break in a way nobody notices until
a filter silently stops narrowing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, Query

from agentlen.application.dto.dashboard import DashboardFilters


def dashboard_filters(  # noqa: PLR0913, PLR0917
    # Eight parameters because API.md §6 documents eight filters. FastAPI
    # derives the query string from this signature, so collapsing them into
    # an object would remove them from the OpenAPI the front generates from.
    data_source_id: Annotated[int | None, Query(description="Restrict to one source.")] = None,
    agent_id: Annotated[int | None, Query(description="Restrict to one agent.")] = None,
    model_id: Annotated[int | None, Query(description="Sessions that used this model.")] = None,
    tool_id: Annotated[int | None, Query(description="Sessions that used this tool.")] = None,
    import_run_id: Annotated[int | None, Query(description="Restrict to one import run.")] = None,
    date_from: Annotated[
        datetime | None, Query(description="Sessions started at or after this instant.")
    ] = None,
    date_to: Annotated[
        datetime | None, Query(description="Sessions started at or before this instant.")
    ] = None,
    status: Annotated[
        Literal["completed", "error", "aborted", "unknown"] | None,
        Query(description="Session outcome."),
    ] = None,
) -> DashboardFilters:
    return DashboardFilters(
        data_source_id=data_source_id,
        agent_id=agent_id,
        model_id=model_id,
        tool_id=tool_id,
        import_run_id=import_run_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )


#: Inject with `filters: FiltersDep` in a route signature.
FiltersDep = Annotated[DashboardFilters, Depends(dashboard_filters)]
