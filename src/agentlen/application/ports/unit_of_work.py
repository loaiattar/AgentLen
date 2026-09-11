"""Transaction boundary.

One unit of work is one transaction, and an import is not one transaction:
`RunImport` commits each batch in its own unit of work, together with the
run's counters so far. A run that fails keeps the batches committed before the
failure, and `import_run` counts exactly those, so it says which part was
imported; the failing batch rolls back whole. Running the same import again
skips the lines it already stored (`raw_record` is unique on
`(import_run_id, line_number)`).

The repositories hang off the unit of work rather than being injected
separately, so they cannot accidentally be used outside a transaction.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from agentlen.application.ports.repositories import (
    DataSourceRepository,
    FileUploadRepository,
    ImportIssueRepository,
    ImportRunRepository,
    MappingProposalRepository,
    MappingRepository,
    ModelCallRepository,
    RawRecordRepository,
    ReferentialRepository,
    SessionRepository,
    ToolCallRepository,
    UserRepository,
    UserSessionRepository,
)


class UnitOfWork(Protocol):
    """Async context manager wrapping one transaction.

    Leaving the block without calling `commit()` rolls back — the safe default,
    so an early return or a raised exception cannot silently half-commit.
    """

    sessions: SessionRepository
    model_calls: ModelCallRepository
    tool_calls: ToolCallRepository
    raw_records: RawRecordRepository
    import_runs: ImportRunRepository
    import_issues: ImportIssueRepository
    mappings: MappingRepository
    mapping_proposals: MappingProposalRepository
    data_sources: DataSourceRepository
    file_uploads: FileUploadRepository
    referentials: ReferentialRepository
    users: UserRepository
    user_sessions: UserSessionRepository

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
