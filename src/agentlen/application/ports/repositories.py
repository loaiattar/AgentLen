from __future__ import annotations

from typing import Protocol
from uuid import UUID

from agentlen.domain.model.import_run import ImportReport
from agentlen.domain.model.mapping import Mapping, MappingProposal
from agentlen.domain.model.session import Session


class SessionRepository(Protocol):
    async def get(self, session_id: UUID) -> Session | None: ...
    async def save(self, session: Session) -> None: ...
    async def list(
        self,
        *,
        data_source_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Session]: ...


class MappingRepository(Protocol):
    async def get(self, mapping_id: UUID) -> Mapping | None: ...
    async def save(self, mapping: Mapping) -> None: ...
    async def list(self, *, data_source_id: int | None = None) -> list[Mapping]: ...


class ImportRunRepository(Protocol):
    async def save_report(self, import_run_id: UUID, report: ImportReport) -> None: ...
    async def get_report(self, import_run_id: UUID) -> ImportReport | None: ...


class MappingProposalRepository(Protocol):
    async def save(self, proposal: MappingProposal, file_id: int) -> UUID: ...
    async def get(self, proposal_id: UUID) -> MappingProposal | None: ...


class ReferentialRepository(Protocol):
    """Persists the small reference tables (provider/model/agent/tool/repository).

    One method for all five kinds, since they share the same upsert-by-name
    shape (DATA_MODEL.md §4) — a mapping only ever supplies a *name*, never
    a technical id.
    """

    async def resolve(self, kind: str, name: str) -> int:
        """Return the id for (kind, name), creating the row if it doesn't exist yet."""
        ...
