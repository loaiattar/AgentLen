"""The one identifier type for path and filter parameters.

Every primary key is a Postgres BIGINT identity, so a valid id lies in
[1, 2**63 - 1]. A plain `int` lets any Python integer through to asyncpg, which
cannot encode one past int64 and fails with a 500. Bounding it here turns that
into a 400 before a query is even built.
"""

from __future__ import annotations

from typing import Annotated

from annotated_types import Ge, Le

#: Largest value a BIGINT column can hold.
MAX_ID = 2**63 - 1

#: Plain constraint metadata rather than `Path()`/`Query()`, so it composes
#: with either: `EntityId` in a path, `Annotated[EntityId | None, Query()]` in a
#: query string.
EntityId = Annotated[int, Ge(1), Le(MAX_ID)]
