"""Persistence ports.

Two implementations exist for each: SQLAlchemy for production, and an in-memory
double so use-case tests run without Postgres. A shared contract test suite runs
against both, because a double that behaves differently from the database is
worse than no double at all.

**On identity.** Domain entities carry a `UUID`, generated fresh by
`RecordNormalizer` on every normalisation (`uuid4()`). It is *in-batch
correlation* — how a `ModelCall` says which `Session` it belongs to before
either has been written. It is not stable: re-reading the same file produces
different UUIDs. Persistent identity is the `BIGINT` the database assigns, and
that is what the API exposes. So writes take entities and hand back a
UUID → id mapping; reads take the database id. See ADR-012.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol

from agentlen.application.dto.persistence import (
    DataSourceRecord,
    FileUploadRecord,
    ImportIssueRecord,
    InsertOutcome,
    ModelCallRow,
    SessionRow,
    ToolCallRow,
    UserRecord,
    UserSessionRecord,
)
from agentlen.domain.model.import_run import ImportIssue, ImportReport
from agentlen.domain.model.mapping import Mapping, MappingProposal
from agentlen.domain.model.session import Session


class SessionRepository(Protocol):
    async def add_many(self, rows: list[SessionRow]) -> InsertOutcome:
        """Insert sessions, skipping any whose natural key already exists.

        `UNIQUE (data_source_id, external_id)` decides. A conflict is reported
        in `duplicates`, not raised: re-importing is expected behaviour.
        """
        ...

    async def get(self, session_id: int) -> Session | None: ...

    async def list(
        self,
        *,
        data_source_id: int | None = None,
        agent_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Session]: ...

    async def count(self, *, data_source_id: int | None = None) -> int: ...


class ModelCallRepository(Protocol):
    async def add_many(
        self, rows: list[ModelCallRow], *, session_ids: dict[Any, int]
    ) -> InsertOutcome:
        """`session_ids` maps each parent's in-batch UUID to its database id."""
        ...


class ToolCallRepository(Protocol):
    async def add_many(
        self,
        rows: list[ToolCallRow],
        *,
        session_ids: dict[Any, int],
        model_call_ids: dict[Any, int] | None = None,
    ) -> InsertOutcome: ...


class RawRecordRepository(Protocol):
    async def add_many(
        self, *, import_run_id: int, records: list[tuple[int, dict[str, Any]]]
    ) -> dict[int, int]:
        """Store payloads verbatim. Returns line number → raw_record id."""
        ...


class ImportRunRepository(Protocol):
    async def create(self, *, data_source_id: int, file_upload_id: int, mapping_id: int) -> int: ...

    async def get(self, import_run_id: int) -> dict[str, Any] | None:
        """The run's identifying columns: source, file, mapping, status."""
        ...

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Most recent first — the history view (API.md §5)."""
        ...

    async def count(self) -> int: ...

    async def save_report(
        self, import_run_id: int, report: ImportReport, *, status: str
    ) -> None: ...
    async def get_report(self, import_run_id: int) -> ImportReport | None: ...


class ImportIssueRepository(Protocol):
    async def add_many(
        self,
        *,
        import_run_id: int,
        issues: list[tuple[ImportIssue, int | None]],
    ) -> None:
        """Each issue with the raw_record id it concerns, when there is one."""
        ...

    async def list(
        self, *, import_run_id: int, severity: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ImportIssueRecord]:
        """Oldest first. The line number comes from the linked raw_record."""
        ...

    async def count(self, *, import_run_id: int, severity: str | None = None) -> int: ...


class MappingRepository(Protocol):
    # get_by_id/list_records/count/supersede are declared before `get`/`list`
    # below: a method named `list` in this class shadows the builtin `list[...]`
    # in every annotation that follows it (mypy resolves the bare name against
    # the class's own namespace), so anything using a bare `list[...]` return
    # type has to come first.
    async def get_by_id(self, mapping_id: int) -> dict[str, Any] | None:
        """The full stored row: status, data_source_id, timestamps, and the raw
        document — API.md §4 surfaces more than the transformation-engine's
        `Mapping` carries."""
        ...

    async def list_records(
        self,
        *,
        data_source_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    async def count(
        self, *, data_source_id: int | None = None, status: str | None = None
    ) -> int: ...

    async def latest_version(self, *, data_source_id: int, name: str) -> int | None:
        """The highest version stored under this name, or None if there is none.

        Versioning cannot be derived from the row the caller named: a PUT
        against an already superseded version would then recreate a version
        that exists, violating `uq_mapping_name_version`.
        """
        ...

    async def supersede(self, mapping_id: int) -> None:
        """Marks a mapping 'superseded' — called when a PUT creates its
        successor (MAPPING_CONTRACT.md §6)."""
        ...

    async def get(self, mapping_id: int) -> Mapping | None: ...
    async def save(self, mapping: Mapping, *, data_source_id: int) -> int: ...
    async def list(self, *, data_source_id: int | None = None) -> list[Mapping]: ...


class FileUploadRepository(Protocol):
    """Files, keyed by the SHA-256 of their content.

    `content_hash` is UNIQUE in the schema, so the same bytes are stored once
    however many times they are uploaded — the first idempotence barrier
    (DATA_MODEL.md §6.1).
    """

    async def get_by_hash(self, content_hash: str) -> FileUploadRecord | None: ...

    async def get_by_id(self, file_upload_id: int) -> FileUploadRecord | None: ...

    async def create(
        self,
        *,
        original_name: str,
        storage_path: str,
        format: str,
        size_bytes: int,
        content_hash: str,
    ) -> FileUploadRecord: ...

    async def import_run_ids(self, file_upload_id: int) -> list[int]:
        """Runs that already used this file, newest first."""
        ...


class MappingProposalRepository(Protocol):
    """Traceability of what the AI proposed. Consumed by #53."""

    async def save(
        self, proposal: MappingProposal, *, file_upload_id: int, data_source_id: int | None = None
    ) -> int: ...

    async def get(self, proposal_id: int) -> MappingProposal | None: ...

    async def update(self, proposal_id: int, proposal: MappingProposal) -> None: ...

    async def add_message(self, proposal_id: int, *, role: str, content: str) -> None: ...

    async def list_messages(
        self, proposal_id: int, *, limit: int
    ) -> list[dict[str, str | int]]: ...


class DataSourceRepository(Protocol):
    async def get_by_slug(self, slug: str) -> int | None: ...

    async def get_by_id(self, data_source_id: int) -> DataSourceRecord | None: ...

    async def list(self) -> list[DataSourceRecord]:
        """All declared sources — GET /data-sources (API.md §2)."""
        ...

    async def create(  # noqa: PLR0913
        self,
        *,
        slug: str,
        name: str,
        description: str | None = None,
        url: str | None = None,
        license: str | None = None,
        dataset_version: str | None = None,
        retrieved_at: date | None = None,
    ) -> int: ...


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> UserRecord | None: ...

    async def get_by_id(self, user_id: int) -> UserRecord | None: ...

    async def create(self, *, email: str, password_hash: str) -> UserRecord:
        """Raises on a duplicate e-mail; the use case checks first so it can
        raise the application-level `ConflictError` with a clean message
        instead of surfacing a raw integrity error."""
        ...


class UserSessionRepository(Protocol):
    """Sessions are keyed by the SHA-256 of their token
    (`domain/services/session_tokens.py`): the token never reaches this port."""

    async def create(
        self, *, user_id: int, token_hash: str, expires_at: datetime | None
    ) -> UserSessionRecord: ...

    async def get_active_by_token_hash(
        self, token_hash: str, *, now: datetime
    ) -> UserSessionRecord | None:
        """`None` for an unknown digest and for a session expired at `now`
        (`expires_at <= now`). A NULL `expires_at` never expires."""
        ...

    async def delete_by_token_hash(self, token_hash: str) -> None:
        """No-op if the session is already gone — logout is idempotent."""
        ...

    async def delete_expired(self, *, now: datetime) -> int:
        """Remove every session expired at `now`; return how many were removed."""
        ...


class ReferentialRepository(Protocol):
    """Upsert-by-name for provider / model / agent / tool / repository.

    A mapping supplies a *name*; the id is resolved or created here. `context`
    carries the extra key components some kinds need — `model` is unique on
    `(provider_id, name)`, not on `name` alone (DATA_MODEL.md §4).
    """

    async def resolve(
        self, kind: str, name: str, *, context: dict[str, str] | None = None
    ) -> int: ...
