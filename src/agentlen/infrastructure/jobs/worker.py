"""The import worker: claim a job, run it, release it, repeat.

Two behaviours matter more than the loop itself.

**A job is never left locked.** Whatever happens — success, a failed import, an
unexpected crash in our own code — the row is released before moving on. A job
stuck in `running` with a lock and no worker behind it is invisible: it is not
pending, so nobody picks it up, and it never finishes. (#18 handles the case
where the process dies outright and cannot release anything.)

**SIGTERM finishes the job in flight.** Container orchestrators send SIGTERM
before SIGKILL. Stopping mid-import would leave a partially written run; the
worker instead stops *claiming* new work and lets the current job complete.

**A database outage is waited out, not fatal.** When the queue itself fails —
Postgres restarting, a network cut — the loop logs it, waits, and tries again.
A worker that exited instead would leave every later import `pending` for good.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import socket
from typing import Protocol

logger = logging.getLogger("agentlen.worker")

#: How long to wait when the queue is empty. Short enough that a queued import
#: starts promptly, long enough not to hammer the database while idle.
IDLE_SLEEP_SECONDS = 1.0

#: Wait after the queue fails, doubled on each consecutive failure up to the
#: maximum and reset by the first success: a blip costs a second, and a long
#: outage is retried at a steady pace instead of hammered or given up on.
ERROR_BACKOFF_SECONDS = 1.0
MAX_ERROR_BACKOFF_SECONDS = 30.0

#: How far down a `raise ... from` chain the failure summary looks. A SQLAlchemy
#: error wraps the driver adapter's, which wraps the driver's own: that is
#: three links, and the last one names what actually went wrong.
_MAX_CAUSE_DEPTH = 4


class _Queue(Protocol):
    async def claim_next(self, *, worker_id: str) -> int | None: ...
    async def mark_succeeded(self, import_run_id: int, *, status: str = "succeeded") -> None: ...
    async def mark_failed(self, import_run_id: int, *, error: str) -> None: ...


class _Importer(Protocol):
    async def execute(self, import_run_id: int) -> object: ...


def default_worker_id() -> str:
    """Identifies the holder of a lock — a hostname and pid are what someone
    debugging a stuck job actually needs."""
    return f"{socket.gethostname()}:{os.getpid()}"


def failure_summary(import_run_id: int, exc: BaseException) -> str:
    """What a failed import leaves behind, in the worker log and in
    `import_run.error_summary`.

    Class names only, never an exception's text. That text is not ours to
    trust: SQLAlchemy renders the bound parameters of the failing statement,
    and Postgres itself echoes the offending row (`DETAIL: Failing row contains
    (...)`) — for a `raw_record` insert, the trace payload. `hide_parameters`
    on the engine covers the first, nothing covers the second, so the message is
    dropped rather than filtered: no redaction pattern knows which part of an
    arbitrary payload is sensitive. The traceback goes with it, since its last
    line is that same message.

    The chain of causes stays, because it is what an operator needs:
    `IntegrityError <- NotNullViolationError` says what kind of failure it was
    without saying on which values.
    """
    names: list[str] = []
    current: BaseException | None = exc
    for _ in range(_MAX_CAUSE_DEPTH):
        if current is None:
            break
        name = type(current).__name__
        if not names or names[-1] != name:
            names.append(name)
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    return (
        f"Import {import_run_id} en échec : {' <- '.join(names)} "
        "(détail non conservé : il peut contenir des données de trace)."
    )


class ImportWorker:
    def __init__(
        self,
        queue: _Queue,
        importer: _Importer,
        *,
        worker_id: str | None = None,
        idle_sleep: float = IDLE_SLEEP_SECONDS,
        error_backoff: tuple[float, float] = (ERROR_BACKOFF_SECONDS, MAX_ERROR_BACKOFF_SECONDS),
    ) -> None:
        self._queue = queue
        self._importer = importer
        self._worker_id = worker_id or default_worker_id()
        self._idle_sleep = idle_sleep
        # First and longest wait after a queue failure.
        self._error_backoff, self._max_error_backoff = error_backoff
        self._stopping = False
        self._stop_requested = asyncio.Event()
        # A failed job whose release did not reach the database: released
        # before anything else is claimed, so it does not stay locked.
        self._unreleased: tuple[int, str] | None = None
        self.processed = 0

    def request_stop(self) -> None:
        """Stop after the current job. Never interrupts one in flight."""
        logger.info("Arrêt demandé ; le job en cours va être terminé.")
        self._stopping = True
        self._stop_requested.set()

    async def run_once(self) -> bool:
        """Claim and run one job. Returns False when the queue was empty.

        Raises when the queue itself fails (`claim_next`, `mark_failed`):
        waiting and retrying is `run_forever`'s job, not a single step's.
        """
        if self._unreleased is not None:
            await self._release_as_failed(*self._unreleased)
        import_run_id = await self._queue.claim_next(worker_id=self._worker_id)
        if import_run_id is None:
            return False

        try:
            report = await self._importer.execute(import_run_id)
            status = "partial" if getattr(report, "records_rejected", 0) else "succeeded"
            await self._queue.mark_succeeded(import_run_id, status=status)
            logger.info("Import %s terminé (%s).", import_run_id, status)
        except Exception as exc:  # noqa: BLE001 - the loop must survive one bad job
            # Released deliberately: a job that fails while holding its lock is
            # indistinguishable from a crashed worker, and nobody retries it.
            summary = failure_summary(import_run_id, exc)
            logger.error("%s", summary)
            await self._release_as_failed(import_run_id, summary)
        finally:
            self.processed += 1
        return True

    async def _release_as_failed(self, import_run_id: int, summary: str) -> None:
        # Remembered until `mark_failed` succeeds: if the database is gone as
        # well, the next `run_once` retries the release before claiming.
        self._unreleased = (import_run_id, summary)
        await self._queue.mark_failed(import_run_id, error=summary)
        self._unreleased = None

    async def run_forever(self, *, stop_when_idle: bool = False) -> None:
        """Consume until asked to stop.

        `stop_when_idle` turns the loop into a drain: process what is queued,
        then exit. That is what a test needs, and it is also the honest way to
        run the worker as a one-shot task in CI or a cron job — a service that
        can only run forever is awkward to use any other way.
        """
        logger.info("Worker %s démarré.", self._worker_id)
        delay = self._error_backoff
        while not self._stopping:
            try:
                worked = await self.run_once()
            except Exception as exc:  # noqa: BLE001 - a database outage must not end the process
                # Class names only, like `failure_summary`: a driver error's
                # text can carry the statement's parameters.
                logger.error(
                    "File d'imports indisponible (%s) ; nouvel essai dans %.1f s.",
                    self._exception_classes(exc),
                    delay,
                )
                await self._pause(delay)
                delay = min(delay * 2, self._max_error_backoff)
                continue
            delay = self._error_backoff
            if worked:
                continue
            if stop_when_idle:
                break
            await self._pause(self._idle_sleep)
        if self._unreleased is not None:
            logger.error(
                "Import %s toujours verrouillé : sa libération n'a pas abouti avant l'arrêt.",
                self._unreleased[0],
            )
        logger.info("Worker %s arrêté après %d job(s).", self._worker_id, self.processed)

    async def _pause(self, seconds: float) -> None:
        """Sleep, but wake as soon as a stop is requested: SIGTERM must not wait
        out a 30-second backoff before the container can exit."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_requested.wait(), timeout=seconds)

    @staticmethod
    def _exception_classes(exc: BaseException) -> str:
        """`OperationalError <- ConnectionRefusedError`: the cause chain, by name."""
        names: list[str] = []
        current: BaseException | None = exc
        for _ in range(_MAX_CAUSE_DEPTH):
            if current is None:
                break
            if not names or names[-1] != type(current).__name__:
                names.append(type(current).__name__)
            current = current.__cause__ or (
                None if current.__suppress_context__ else current.__context__
            )
        return " <- ".join(names)

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.request_stop)
            except NotImplementedError:  # pragma: no cover - Windows
                signal.signal(sig, lambda *_: self.request_stop())
