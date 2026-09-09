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

    One method for all five kinds — but they do NOT all share the same key
    shape (DATA_MODEL.md §4): `provider` and `tool` are unique on `name`
    alone; `model` is unique on `(provider_id, name)`; `repository` is
    unique on `(host, owner, name)`. `context` carries whatever extra key
    components a kind needs beyond `name`, e.g. for `model`:
    `context={"provider_name": "anthropic"}`. The implementation is
    responsible for resolving/creating any referenced-by-context row too
    (e.g. the provider) before inserting the row that depends on it.
    """

    async def resolve(self, kind: str, name: str, *, context: dict[str, str] | None = None) -> int:
        """Return the id for (kind, name, context), creating the row if needed."""
        ...
