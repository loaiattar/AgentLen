"""Shared pagination parameters.

One definition, injected by every list route, so `?limit=&offset=` behaves
identically across the API and the front only has to learn it once.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query, Response

from agentlen.interfaces.http.schemas.common import Page

DEFAULT_LIMIT = 50
#: Hard ceiling. Without it, `?limit=1000000` is a denial-of-service primitive
#: that costs the caller one request.
MAX_LIMIT = 200


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


def page_params(
    limit: Annotated[
        int, Query(ge=1, le=MAX_LIMIT, description=f"Rows to return (max {MAX_LIMIT}).")
    ] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


#: Inject with `params: Paginated` in a route signature.
Paginated = Annotated[PageParams, Depends(page_params)]


def paginate[T](items: list[T], total: int, params: PageParams) -> Page[T]:
    """Wrap an already-sliced list in the response envelope.

    `items` must already be the page; this does not slice, because slicing
    belongs in SQL where the database can use an index for it.
    """
    return Page[T](items=items, total=total, limit=params.limit, offset=params.offset)


# ---------------------------------------------------------------------------
# Bounded bare arrays — the two documented exceptions of API.md §1
# ---------------------------------------------------------------------------

#: Count before the window, so a client can tell a bare array was cut short.
TOTAL_COUNT_HEADER = "X-Total-Count"

TOTAL_COUNT_RESPONSE: dict[str, Any] = {
    "headers": {
        TOTAL_COUNT_HEADER: {
            "description": "Total rows, ignoring limit and offset.",
            "schema": {"type": "integer"},
        }
    }
}


def window_params(
    limit: Annotated[
        int, Query(ge=1, le=MAX_LIMIT, description=f"Rows to return (max {MAX_LIMIT}).")
    ] = MAX_LIMIT,
    offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
) -> PageParams:
    """Same bounds as `page_params`, but defaulting to the ceiling: these
    routes answered everything before, and a caller that sends no parameter
    should lose as little as possible."""
    return PageParams(limit=limit, offset=offset)


#: Inject with `params: Windowed` on a route that returns a bare array.
Windowed = Annotated[PageParams, Depends(window_params)]


def window[T](items: Sequence[T], params: PageParams, response: Response) -> list[T]:
    """Cut an in-memory list to the window and report the full count.

    In memory, unlike `paginate`: the reference table of sources and the calls
    of one session are small, and the session's calls are already loaded
    whole by `GET /sessions/{id}`. What must be bounded is the response.
    """
    response.headers[TOTAL_COUNT_HEADER] = str(len(items))
    return list(items[params.offset : params.offset + params.limit])
