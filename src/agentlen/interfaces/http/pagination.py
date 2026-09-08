"""Shared pagination parameters.

One definition, injected by every list route, so `?limit=&offset=` behaves
identically across the API and the front only has to learn it once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

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
