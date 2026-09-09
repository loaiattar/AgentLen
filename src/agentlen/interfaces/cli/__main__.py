"""Command-line entry points.

`python -m agentlen.interfaces.cli worker` is the `worker` service of the
compose stack (#60). It lives here rather than in `infrastructure/` because
wiring adapters to ports is an interface concern — this is the only place, with
`interfaces/http/dependencies.py`, where concrete implementations are chosen.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from agentlen.application.use_cases.run_import import RunImport
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from agentlen.infrastructure.jobs.postgres_queue import PostgresJobQueue
from agentlen.infrastructure.jobs.worker import ImportWorker
from agentlen.infrastructure.persistence.engine import create_engine
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


async def _run_worker(*, drain: bool = False) -> None:
    engine = create_engine()
    worker = ImportWorker(
        PostgresJobQueue(engine),
        RunImport(SqlAlchemyUnitOfWork(engine), PolarsRecordReader()),
    )
    worker.install_signal_handlers(asyncio.get_running_loop())
    try:
        await worker.run_forever(stop_when_idle=drain)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentlen")
    parser.add_argument("command", choices=["worker"], help="Ce qu'il faut lancer.")
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Traiter la file puis sortir, au lieu de tourner en continu.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    )
    if args.command == "worker":
        asyncio.run(_run_worker(drain=args.drain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
