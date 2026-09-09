"""The Postgres queue, and the property that makes it safe: SKIP LOCKED."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import Connection, insert, select
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.infrastructure.jobs.postgres_queue import PostgresJobQueue
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres


@pytest.fixture
def runs(clean_db: Connection) -> list[int]:
    conn = clean_db
    source = conn.execute(
        insert(t.data_source).values(slug="s", name="S").returning(t.data_source.c.id)
    ).scalar_one()
    file_id = conn.execute(
        insert(t.file_upload)
        .values(
            original_name="t.jsonl",
            storage_path="/x",
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        .returning(t.file_upload.c.id)
    ).scalar_one()
    mapping_id = conn.execute(
        insert(t.mapping)
        .values(
            data_source_id=source,
            name="m",
            version=1,
            source_format="jsonl",
            document={},
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()
    ids = [
        conn.execute(
            insert(t.import_run)
            .values(
                data_source_id=source,
                file_upload_id=file_id,
                mapping_id=mapping_id,
                status="pending",
            )
            .returning(t.import_run.c.id)
        ).scalar_one()
        for _ in range(6)
    ]
    conn.commit()
    return ids


@pytest.fixture
async def queue(database_url: str) -> AsyncIterator[PostgresJobQueue]:
    engine = create_async_engine(to_async_url(database_url))
    yield PostgresJobQueue(engine)
    await engine.dispose()


async def test_a_claimed_job_is_marked_running_and_locked(
    runs: list[int], queue: PostgresJobQueue, engine: Any
) -> None:
    claimed = await queue.claim_next(worker_id="w1")

    assert claimed is not None
    with engine.connect() as conn:
        row = conn.execute(
            select(t.import_run.c.status, t.import_run.c.locked_by, t.import_run.c.attempts).where(
                t.import_run.c.id == claimed
            )
        ).one()
    assert row.status == "running"
    assert row.locked_by == "w1"
    assert row.attempts == 1


async def test_jobs_are_taken_oldest_first(runs: list[int], queue: PostgresJobQueue) -> None:
    first = await queue.claim_next(worker_id="w1")
    second = await queue.claim_next(worker_id="w1")

    assert [first, second] == runs[:2]


async def test_two_workers_never_get_the_same_job(runs: list[int], queue: PostgresJobQueue) -> None:
    """The whole reason for SKIP LOCKED. Two workers running the same import
    would duplicate the work and race on the same rows."""
    claims = await asyncio.gather(*(queue.claim_next(worker_id=f"w{i}") for i in range(6)))

    got = [c for c in claims if c is not None]
    assert len(got) == len(set(got)), f"un job réclamé deux fois : {got}"
    assert set(got) == set(runs)


async def test_an_empty_queue_returns_none_rather_than_blocking(
    clean_db: Connection, queue: PostgresJobQueue
) -> None:
    assert await queue.claim_next(worker_id="w1") is None


async def test_a_finished_job_releases_its_lock(
    runs: list[int], queue: PostgresJobQueue, engine: Any
) -> None:
    claimed = await queue.claim_next(worker_id="w1")
    assert claimed is not None

    await queue.mark_succeeded(claimed, status="partial")

    with engine.connect() as conn:
        row = conn.execute(
            select(
                t.import_run.c.status, t.import_run.c.locked_by, t.import_run.c.finished_at
            ).where(t.import_run.c.id == claimed)
        ).one()
    assert row.status == "partial"
    assert row.locked_by is None
    assert row.finished_at is not None


async def test_a_failed_job_releases_its_lock_too(
    runs: list[int], queue: PostgresJobQueue, engine: Any
) -> None:
    """A job that fails while holding its lock is indistinguishable from a
    crashed worker, and nobody ever retries it."""
    claimed = await queue.claim_next(worker_id="w1")
    assert claimed is not None

    await queue.mark_failed(claimed, error="ValueError: boom")

    with engine.connect() as conn:
        row = conn.execute(
            select(
                t.import_run.c.status, t.import_run.c.locked_by, t.import_run.c.error_summary
            ).where(t.import_run.c.id == claimed)
        ).one()
    assert row.status == "failed"
    assert row.locked_by is None
    assert "boom" in row.error_summary


async def test_a_running_job_is_not_claimed_again(runs: list[int], queue: PostgresJobQueue) -> None:
    claimed = {await queue.claim_next(worker_id="w1") for _ in range(len(runs))}
    extra = await queue.claim_next(worker_id="w2")

    assert extra is None
    assert None not in claimed
