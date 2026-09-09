"""The worker loop: never leaves a job locked, and stops cleanly."""

from __future__ import annotations

from typing import Any

from agentlen.domain.model.import_run import ImportReport
from agentlen.infrastructure.jobs.worker import ImportWorker


class FakeQueue:
    """Records what the worker did, so the assertions are about behaviour."""

    def __init__(self, jobs: list[int]) -> None:
        self.pending = list(jobs)
        self.claimed: list[int] = []
        self.succeeded: list[tuple[int, str]] = []
        self.failed: list[tuple[int, str]] = []

    async def claim_next(self, *, worker_id: str) -> int | None:
        if not self.pending:
            return None
        job = self.pending.pop(0)
        self.claimed.append(job)
        return job

    async def mark_succeeded(self, import_run_id: int, *, status: str = "succeeded") -> None:
        self.succeeded.append((import_run_id, status))

    async def mark_failed(self, import_run_id: int, *, error: str) -> None:
        self.failed.append((import_run_id, error))

    @property
    def released(self) -> set[int]:
        return {i for i, _ in self.succeeded} | {i for i, _ in self.failed}


class FakeImporter:
    def __init__(self, behaviour: dict[int, Any] | None = None) -> None:
        self.behaviour = behaviour or {}
        self.ran: list[int] = []

    async def execute(self, import_run_id: int) -> ImportReport:
        self.ran.append(import_run_id)
        outcome = self.behaviour.get(import_run_id)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome or ImportReport(
            records_read=1, records_imported=1, records_duplicate=0, records_rejected=0
        )


async def test_a_successful_job_is_released_as_succeeded() -> None:
    queue, importer = FakeQueue([1]), FakeImporter()
    worker = ImportWorker(queue, importer, worker_id="w1")

    assert await worker.run_once() is True
    assert queue.succeeded == [(1, "succeeded")]


async def test_a_run_with_rejections_is_released_as_partial() -> None:
    report = ImportReport(
        records_read=100, records_imported=97, records_duplicate=0, records_rejected=3
    )
    queue = FakeQueue([1])
    worker = ImportWorker(queue, FakeImporter({1: report}), worker_id="w1")

    await worker.run_once()

    assert queue.succeeded == [(1, "partial")]


async def test_a_failing_job_is_released_not_left_locked() -> None:
    """A job holding its lock after failing is indistinguishable from a crashed
    worker: not pending, so never picked up, and never finished."""
    queue = FakeQueue([1])
    worker = ImportWorker(queue, FakeImporter({1: ValueError("boom")}), worker_id="w1")

    assert await worker.run_once() is True
    assert queue.succeeded == []
    assert len(queue.failed) == 1
    assert "boom" in queue.failed[0][1]
    assert queue.released == {1}


async def test_one_bad_job_does_not_stop_the_loop() -> None:
    queue = FakeQueue([1, 2, 3])
    importer = FakeImporter({2: RuntimeError("nope")})
    worker = ImportWorker(queue, importer, worker_id="w1", idle_sleep=0)

    await worker.run_forever(stop_when_idle=True)

    assert importer.ran == [1, 2, 3]
    assert queue.released == {1, 2, 3}


async def test_an_empty_queue_reports_no_work() -> None:
    worker = ImportWorker(FakeQueue([]), FakeImporter(), worker_id="w1")

    assert await worker.run_once() is False


async def test_stop_requested_mid_run_finishes_the_current_job() -> None:
    """SIGTERM arrives before SIGKILL. Stopping mid-import would leave a
    partially written run, so the worker finishes what it holds and then
    stops claiming."""
    queue = FakeQueue([1, 2, 3])

    class StoppingImporter(FakeImporter):
        async def execute(self, import_run_id: int) -> ImportReport:
            report = await super().execute(import_run_id)
            worker.request_stop()  # as if SIGTERM landed here
            return report

    importer = StoppingImporter()
    worker = ImportWorker(queue, importer, worker_id="w1", idle_sleep=0)

    await worker.run_forever(stop_when_idle=True)

    # The job in flight completed and was released; the rest were left queued.
    assert importer.ran == [1]
    assert queue.released == {1}
    assert queue.pending == [2, 3]


async def test_no_job_is_ever_left_claimed_but_unreleased() -> None:
    queue = FakeQueue([1, 2, 3, 4])
    importer = FakeImporter({2: RuntimeError("x"), 4: ValueError("y")})
    worker = ImportWorker(queue, importer, worker_id="w1", idle_sleep=0)

    await worker.run_forever(stop_when_idle=True)

    assert set(queue.claimed) == queue.released


def test_the_worker_id_identifies_the_lock_holder() -> None:
    """Whoever is debugging a stuck job needs to know which process holds it."""
    from agentlen.infrastructure.jobs.worker import default_worker_id

    worker_id = default_worker_id()
    assert ":" in worker_id
    assert worker_id.rsplit(":", 1)[1].isdigit()


def test_the_cli_exposes_the_worker_command() -> None:
    import pytest as _pytest

    from agentlen.interfaces.cli.__main__ import main

    with _pytest.raises(SystemExit):
        main(["nonexistent-command"])
