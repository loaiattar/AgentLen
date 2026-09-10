"""Dependency injection — the single wiring point between layers.

This is the only module where a concrete adapter is chosen for a port. Routers
and use cases receive ports and never learn which implementation they got, so
swapping Postgres, Polars or the AI provider touches this file and nothing else.

Everything here is overridable in tests via `app.dependency_overrides`, which is
why the providers are plain functions rather than module-level singletons.

Ports whose adapters do not exist yet (repositories, storage, the analyzer) are
declared as `_not_wired` placeholders: a route asking for one gets a clear 503
naming the issue that will provide it, instead of an import error at start-up
or a mystery `None`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.application.errors import ApplicationError
from agentlen.application.ports.clock import Clock, SystemClock
from agentlen.application.ports.dashboard_queries import DashboardQueries
from agentlen.application.ports.exploration_queries import ExplorationQueries
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.infrastructure.ai.factory import build_structure_analyzer
from agentlen.infrastructure.persistence.engine import create_engine, get_database_url
from agentlen.infrastructure.persistence.read_models import SqlDashboardQueries
from agentlen.infrastructure.persistence.read_models.sql import SqlExplorationQueries


class DependencyNotWiredError(ApplicationError):
    """A port has no adapter yet. -> 503, with the issue number that lands it."""

    code = "DEPENDENCY_NOT_WIRED"


def _not_wired(port: str, issue: str) -> Callable[[], Any]:
    def provider() -> Any:
        raise DependencyNotWiredError(
            f"Le port '{port}' n'a pas encore d'implémentation (voir {issue}).",
            details={"port": port, "issue": issue},
        )

    return provider


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
# Ports awaiting their adapters. Each names the issue that will provide it.
# ---------------------------------------------------------------------------

get_unit_of_work = _not_wired("UnitOfWork", "#45")
get_session_repository = _not_wired("SessionRepository", "#45")
get_mapping_repository = _not_wired("MappingRepository", "#45")
get_import_run_repository = _not_wired("ImportRunRepository", "#45")
get_file_storage = _not_wired("FileStorage", "#47")
get_file_reader = _not_wired("FileReader", "#48")
get_file_profiler = _not_wired("FileProfiler", "#48")


#: Inject with `clock: ClockDep` in a route signature.
ClockDep = Annotated[Clock, Depends(get_clock)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
DashboardQueriesDep = Annotated[DashboardQueries, Depends(get_dashboard_queries)]
AnalyzerDep = Annotated[StructureAnalyzer, Depends(get_structure_analyzer)]


def get_exploration_queries(engine: EngineDep) -> ExplorationQueries:
    return SqlExplorationQueries(engine)


ExplorationQueriesDep = Annotated[ExplorationQueries, Depends(get_exploration_queries)]
