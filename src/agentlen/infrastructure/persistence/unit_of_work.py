"""SQLAlchemy unit of work: one import, one transaction.

Built on `AsyncConnection` rather than `AsyncSession` because nothing here uses
the identity map or lazy loading — the repositories issue explicit batched
statements. A session would add a layer of implicit behaviour over writes whose
timing and batching are the whole point.

Leaving the block without `commit()` rolls back. That default is deliberate: an
exception mid-import must leave the database exactly as it was, since a
half-imported file is worse than a failed one.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from agentlen.application.ports.repositories import (
    DataSourceRepository,
    FileUploadRepository,
    ImportIssueRepository,
    ImportRunRepository,
    MappingRepository,
    ModelCallRepository,
    RawRecordRepository,
    ReferentialRepository,
    SessionRepository,
    ToolCallRepository,
    UserRepository,
    UserSessionRepository,
)
from agentlen.infrastructure.persistence.repositories import (
    SqlAlchemyDataSourceRepository,
    SqlAlchemyFileUploadRepository,
    SqlAlchemyImportIssueRepository,
    SqlAlchemyImportRunRepository,
    SqlAlchemyMappingProposalRepository,
    SqlAlchemyMappingRepository,
    SqlAlchemyModelCallRepository,
    SqlAlchemyRawRecordRepository,
    SqlAlchemyReferentialRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyToolCallRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSessionRepository,
)


class SqlAlchemyUnitOfWork:
    # Declared as the port types (not inferred from the concrete adapters
    # assigned in __aenter__), because Protocol attribute matching is
    # invariant: an inferred `SqlAlchemyDataSourceRepository` attribute type
    # would not satisfy `data_sources: DataSourceRepository` on `UnitOfWork`.
    sessions: SessionRepository
    model_calls: ModelCallRepository
    tool_calls: ToolCallRepository
    raw_records: RawRecordRepository
    import_runs: ImportRunRepository
    import_issues: ImportIssueRepository
    mappings: MappingRepository
    data_sources: DataSourceRepository
    file_uploads: FileUploadRepository
    referentials: ReferentialRepository
    users: UserRepository
    user_sessions: UserSessionRepository

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._conn: AsyncConnection | None = None
        self.committed = False

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._conn = await self._engine.connect()
        await self._conn.begin()
        self.committed = False

        conn = self._conn
        self.sessions = SqlAlchemySessionRepository(conn)
        self.model_calls = SqlAlchemyModelCallRepository(conn)
        self.tool_calls = SqlAlchemyToolCallRepository(conn)
        self.raw_records = SqlAlchemyRawRecordRepository(conn)
        self.import_runs = SqlAlchemyImportRunRepository(conn)
        self.import_issues = SqlAlchemyImportIssueRepository(conn)
        self.mappings = SqlAlchemyMappingRepository(conn)
        self.mapping_proposals = SqlAlchemyMappingProposalRepository(conn)
        self.data_sources = SqlAlchemyDataSourceRepository(conn)
        self.file_uploads = SqlAlchemyFileUploadRepository(conn)
        self.referentials = SqlAlchemyReferentialRepository(conn)
        self.users = SqlAlchemyUserRepository(conn)
        self.user_sessions = SqlAlchemyUserSessionRepository(conn)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if not self.committed:
                await self.rollback()
        finally:
            if self._conn is not None:
                await self._conn.close()
                self._conn = None

    async def commit(self) -> None:
        if self._conn is not None:
            await self._conn.commit()
            self.committed = True

    async def rollback(self) -> None:
        if self._conn is not None:
            await self._conn.rollback()
