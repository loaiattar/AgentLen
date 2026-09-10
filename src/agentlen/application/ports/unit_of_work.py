"""Transaction boundary for an import run.

One import is one transaction. A file that fails halfway must leave the
database exactly as it was — a half-imported file is worse than a failed one,
because nothing tells you which half you got.

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

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
