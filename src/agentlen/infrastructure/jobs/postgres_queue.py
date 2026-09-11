"""Postgres-backed job queue.

The whole design is one statement:

```sql
UPDATE import_run SET status = 'running', locked_at = now(), locked_by = :worker
WHERE id = (
    SELECT id FROM import_run WHERE status = 'pending'
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id
```

`FOR UPDATE` locks the candidate row; `SKIP LOCKED` makes a second worker step
over it and take the next one instead of blocking. Claiming and marking are the
same statement, so there is no window in which a job is chosen but not yet
marked — which is where a naive SELECT-then-UPDATE queue hands the same job to
two workers.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_CLAIM = text("""
    UPDATE import_run
    SET status = 'running',
        locked_at = now(),
        locked_by = :worker_id,
        started_at = coalesce(started_at, now()),
        attempts = attempts + 1
    WHERE id = (
        SELECT id FROM import_run
        WHERE status = 'pending'
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id
""")

_ENQUEUE = text("""
    UPDATE import_run
    SET status = 'pending', locked_at = NULL, locked_by = NULL
    WHERE id = :import_run_id
""")

_SUCCEED = text("""
    UPDATE import_run
    SET status = :status, locked_at = NULL, locked_by = NULL, finished_at = now()
    WHERE id = :import_run_id
""")

_FAIL = text("""
    UPDATE import_run
    SET status = 'failed', locked_at = NULL, locked_by = NULL,
        finished_at = now(), error_summary = :error
    WHERE id = :import_run_id
""")


class PostgresJobQueue:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def enqueue(self, import_run_id: int) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(_ENQUEUE, {"import_run_id": import_run_id})

    async def claim_next(self, *, worker_id: str) -> int | None:
        async with self._engine.begin() as conn:
            claimed = (await conn.execute(_CLAIM, {"worker_id": worker_id})).scalar_one_or_none()
        return int(claimed) if claimed is not None else None

    async def mark_succeeded(self, import_run_id: int, *, status: str = "succeeded") -> None:
        async with self._engine.begin() as conn:
            await conn.execute(_SUCCEED, {"import_run_id": import_run_id, "status": status})

    async def mark_failed(self, import_run_id: int, *, error: str) -> None:
        async with self._engine.begin() as conn:
            # Truncated: error_summary is for a human scanning a list. The worker
            # stores exception class names only, never their text, which can
            # carry trace content (see `failure_summary`).
            await conn.execute(_FAIL, {"import_run_id": import_run_id, "error": error[:2000]})
