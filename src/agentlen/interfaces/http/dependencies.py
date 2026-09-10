"""Dependency injection — the single wiring point between layers.

This is the only module where a concrete adapter is chosen for a port. Routers
and use cases receive ports and never learn which implementation they got, so
swapping Postgres, Polars or the AI provider touches this file and nothing else.

Everything here is overridable in tests via `app.dependency_overrides`, which
is why the providers are plain functions rather than module-level singletons.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.application.dto.persistence import UserRecord
from agentlen.application.ports.clock import Clock, SystemClock
from agentlen.application.ports.dashboard_queries import DashboardQueries
from agentlen.application.ports.exploration_queries import ExplorationQueries
from agentlen.application.ports.file_reader import FileProfiler, FileReader, ProfileSanitizer
from agentlen.application.ports.file_storage import FileStorage
from agentlen.application.ports.password_hasher import PasswordHasher
from agentlen.application.ports.structure_analyzer import StructureAnalyzer
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.application.use_cases.authenticate_user import AuthenticateUser
from agentlen.infrastructure.ai.factory import (
    build_structure_analyzer,
    provider_status,
)
from agentlen.infrastructure.ai.sanitizer import ProfileExampleSanitizer
from agentlen.infrastructure.config.settings import load_ai_settings
from agentlen.infrastructure.files.local_storage import LocalFileStorage
from agentlen.infrastructure.files.polars_profiler import PolarsFileProfiler
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from agentlen.infrastructure.persistence.engine import create_engine, get_database_url
from agentlen.infrastructure.persistence.read_models import SqlDashboardQueries
from agentlen.infrastructure.persistence.read_models.sql import SqlExplorationQueries
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from agentlen.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher

#: Repository root, from this file: src/agentlen/interfaces/http/ -> up 4.
#: Same convention as the CLI seed (interfaces/cli/seed.py): resolves to
#: /app/storage/uploads under the compose WORKDIR, <repo_root>/storage/uploads
#: locally.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
STORAGE_ROOT = _PROJECT_ROOT / "storage" / "uploads"


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


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------


def get_structure_analyzer() -> StructureAnalyzer:
    """Resolved from AI_PROVIDER. The only place a provider is chosen."""
    return build_structure_analyzer()


def get_analyzer_factory() -> Callable[[str | None, str | None], StructureAnalyzer]:
    def build(
        provider: str | None,
        model: str | None,
    ) -> StructureAnalyzer:
        configured = load_ai_settings()
        if provider is None and model is None:
            return build_structure_analyzer(configured)

        selected = configured.model_copy(
            update={
                "provider": provider or configured.provider,
                "model": model if model is not None else configured.model,
            }
        )
        return build_structure_analyzer(selected)

    return build


def get_provider_status() -> dict[str, object]:
    return provider_status()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def get_unit_of_work(engine: EngineDep) -> UnitOfWork:
    """One instance per request; the transaction itself is opened by the
    route's own `async with uow:` block, not here."""
    return SqlAlchemyUnitOfWork(engine)


def get_dashboard_queries(engine: EngineDep) -> DashboardQueries:
    """The read side. Holds only the engine, so one per request is fine."""
    return SqlDashboardQueries(engine)


def get_exploration_queries(engine: EngineDep) -> ExplorationQueries:
    return SqlExplorationQueries(engine)


# ---------------------------------------------------------------------------
# Files — local disk today; the port is what the rest of the app depends on.
# ---------------------------------------------------------------------------


def get_file_storage() -> FileStorage:
    return LocalFileStorage(STORAGE_ROOT)


def get_file_reader() -> FileReader:
    return PolarsRecordReader()


def get_file_profiler() -> FileProfiler:
    return PolarsFileProfiler()


def get_profile_sanitizer() -> ProfileSanitizer:
    return ProfileExampleSanitizer()


def get_max_conversation_turns() -> int:
    return load_ai_settings().max_conversation_turns


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


async def get_clock() -> AsyncIterator[Clock]:
    """Real time in production, frozen in tests via dependency_overrides."""
    yield SystemClock()


# ---------------------------------------------------------------------------
# User auth — per-person login, layered on top of the app-wide X-API-Key
# (interfaces/http/auth.py). See docs/architecture/API.md §Auth.
# ---------------------------------------------------------------------------


def get_password_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()


async def get_current_user(request: Request, uow: UnitOfWorkDep, clock: ClockDep) -> UserRecord:
    """The person behind `Authorization: Bearer <token>` on a protected route.

    Raises `UnauthenticatedError` (-> 401) through `AuthenticateUser` for a
    missing header, an unknown token, or an expired one — all three look the
    same to the caller, which is the point: none of them should leak which
    case it was.
    """
    use_case = AuthenticateUser(uow, clock)
    return await use_case.execute(request.headers.get("authorization"))


#: Inject with `clock: ClockDep` in a route signature.
ClockDep = Annotated[Clock, Depends(get_clock)]
PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]
CurrentUserDep = Annotated[UserRecord, Depends(get_current_user)]
EngineDep = Annotated[AsyncEngine, Depends(get_engine)]
DashboardQueriesDep = Annotated[
    DashboardQueries,
    Depends(get_dashboard_queries),
]
ExplorationQueriesDep = Annotated[
    ExplorationQueries,
    Depends(get_exploration_queries),
]
AnalyzerDep = Annotated[
    StructureAnalyzer,
    Depends(get_structure_analyzer),
]
AnalyzerFactoryDep = Annotated[
    Callable[[str | None, str | None], StructureAnalyzer],
    Depends(get_analyzer_factory),
]
ProviderStatusDep = Annotated[
    dict[str, object],
    Depends(get_provider_status),
]
UnitOfWorkDep = Annotated[
    UnitOfWork,
    Depends(get_unit_of_work),
]
FileStorageDep = Annotated[
    FileStorage,
    Depends(get_file_storage),
]
FileReaderDep = Annotated[
    FileReader,
    Depends(get_file_reader),
]
FileProfilerDep = Annotated[
    FileProfiler,
    Depends(get_file_profiler),
]
ProfileSanitizerDep = Annotated[
    ProfileSanitizer,
    Depends(get_profile_sanitizer),
]
ConversationLimitDep = Annotated[
    int,
    Depends(get_max_conversation_turns),
]
