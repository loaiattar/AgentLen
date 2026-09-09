"""Dependency injection — the single wiring point between layers.

This is the only module where a concrete adapter is chosen for a port. Routers
and use cases receive ports and never learn which implementation they got, so
swapping Postgres, Polars or the AI provider touches this file and nothing else.

Everything here is overridable in tests via `app.dependency_overrides`, which is
why the providers are plain functions rather than module-level singletons.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.application.ports.clock import Clock, SystemClock
from agentlen.application.ports.dashboard_queries import DashboardQueries
from agentlen.application.ports.file_reader import FileProfiler, FileReader
from agentlen.application.ports.file_storage import FileStorage
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.infrastructure.ai.factory import build_structure_analyzer
from agentlen.infrastructure.files.local_storage import LocalFileStorage
from agentlen.infrastructure.files.polars_profiler import PolarsFileProfiler
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from agentlen.infrastructure.persistence.engine import create_engine, get_database_url
from agentlen.infrastructure.persistence.read_models import SqlDashboardQueries
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

# ---------------------------------------------------------------------------
# Engine — one per application, created lazily and disposed on shutdown
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _engine_singleton(url: str) -> AsyncEngine:
    """One engine per URL. The pool is the point: building an engine per
    request would open a new connection pool per request."""
    return create_engine(url)


def get_engine(request: Request) -> AsyncEngine:
    """The engine held on app state, or a lazily built one.

    Reads from `app.state` first so `create_app()` can inject a test engine.
    """
    engine: AsyncEngine | None = getattr(request.app.state, "engine", None)
    if engine is not None:
        return engine
    return _engine_singleton(get_database_url())


def get_structure_analyzer() -> StructureAnalyzer:
    """Resolved from AI_PROVIDER. The only place a provider is chosen."""
    return build_structure_analyzer()


def get_dashboard_queries(engine: EngineDep) -> DashboardQueries:
    """The read side. Holds only the engine, so one per request is fine."""
    return SqlDashboardQueries(engine)


async def get_clock() -> AsyncIterator[Clock]:
    """Real time in production, frozen in tests via dependency_overrides."""
    yield SystemClock()


# ---------------------------------------------------------------------------
# Unit of work — one instance per request, bound to the shared engine.
# ---------------------------------------------------------------------------


def get_unit_of_work(engine: EngineDep) -> UnitOfWork:
    return SqlAlchemyUnitOfWork(engine)


# ---------------------------------------------------------------------------
# Files — local disk today; the port is what the rest of the app depends on.
# ---------------------------------------------------------------------------

#: Repository root, from this file: src/agentlen/interfaces/http/ -> up 4.
#: Same convention as the CLI seed (interfaces/cli/seed.py): resolves to
#: /app/storage/uploads under the compose WORKDIR, <repo_root>/storage/uploads
#: locally.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
STORAGE_ROOT = _PROJECT_ROOT / "storage" / "uploads"


def get_file_storage() -> FileStorage:
    return LocalFileStorage(STORAGE_ROOT)


def get_file_reader() -> FileReader:
    return PolarsRecordReader()


def get_file_profiler() -> FileProfiler:
    return PolarsFileProfiler()


#: Inject with `clock: ClockDep` in a route signature.
ClockDep = Annotated[Clock, Depends(get_clock)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
DashboardQueriesDep = Annotated[DashboardQueries, Depends(get_dashboard_queries)]
AnalyzerDep = Annotated[StructureAnalyzer, Depends(get_structure_analyzer)]
UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]
FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]
FileReaderDep = Annotated[FileReader, Depends(get_file_reader)]
FileProfilerDep = Annotated[FileProfiler, Depends(get_file_profiler)]
