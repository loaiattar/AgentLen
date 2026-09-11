"""In-memory repositories, enforcing the same constraints as the database.

The point of a double is that a use case behaves identically against it. So
these do not just store objects — they reproduce the database's unique keys:
`(data_source_id, external_id)` for sessions, `(session_id, sequence_index)`
for calls. A duplicate insert is reported as a duplicate, exactly as
`ON CONFLICT DO NOTHING` would.

`tests/contract/test_repository_contract.py` runs the same suite against these
and against the SQLAlchemy implementations, which is what keeps the claim true.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any
from uuid import UUID

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
from agentlen.application.errors import ConflictError
from agentlen.domain.model.import_run import ImportIssue, ImportReport
from agentlen.domain.model.mapping import Mapping, MappingProposal
from agentlen.domain.model.session import Session


class _Sequence:
    """Stands in for BIGINT GENERATED ALWAYS AS IDENTITY."""

    def __init__(self) -> None:
        self._next = 0

    def take(self) -> int:
        self._next += 1
        return self._next


@dataclass
class _Store:
    """Shared state, so a rollback can restore every repository at once."""

    sessions: dict[int, tuple[Session, SessionRow]] = field(default_factory=dict)
    session_keys: dict[tuple[int, str], int] = field(default_factory=dict)
    model_calls: list[tuple[int, ModelCallRow]] = field(default_factory=list)
    model_call_keys: dict[tuple[int, int], int] = field(default_factory=dict)
    tool_calls: list[tuple[int, ToolCallRow]] = field(default_factory=list)
    tool_call_keys: dict[tuple[int, int], int] = field(default_factory=dict)
    raw_records: dict[tuple[int, int], int] = field(default_factory=dict)
    payloads: dict[int, dict[str, Any]] = field(default_factory=dict)
    import_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    reports: dict[int, ImportReport] = field(default_factory=dict)
    issues: list[tuple[int, ImportIssue, int | None]] = field(default_factory=list)

    mappings: dict[int, tuple[Mapping, int, str, datetime]] = field(default_factory=dict)
    mapping_proposals: dict[int, MappingProposal] = field(default_factory=dict)
    proposal_messages: list[tuple[int, str, str]] = field(default_factory=list)
    data_sources: dict[str, int] = field(default_factory=dict)
    data_source_records: dict[int, DataSourceRecord] = field(default_factory=dict)
    referentials: dict[tuple[str, str, str], int] = field(default_factory=dict)
    file_uploads: dict[str, FileUploadRecord] = field(default_factory=dict)
    users_by_email: dict[str, UserRecord] = field(default_factory=dict)
    users_by_id: dict[int, UserRecord] = field(default_factory=dict)
    user_sessions: dict[str, UserSessionRecord] = field(default_factory=dict)
    ids: _Sequence = field(default_factory=_Sequence)

    def snapshot(self) -> dict[str, Any]:
        """Deep enough to restore on rollback: containers are copied, the
        objects inside are frozen dataclasses and safe to share."""
        return {
            "sessions": dict(self.sessions),
            "session_keys": dict(self.session_keys),
            "model_calls": list(self.model_calls),
            "model_call_keys": dict(self.model_call_keys),
            "tool_calls": list(self.tool_calls),
            "tool_call_keys": dict(self.tool_call_keys),
            "raw_records": dict(self.raw_records),
            "payloads": dict(self.payloads),
            "import_runs": {k: dict(v) for k, v in self.import_runs.items()},
            "reports": dict(self.reports),
            "issues": list(self.issues),
            "mappings": dict(self.mappings),
            "mapping_proposals": dict(self.mapping_proposals),
            "proposal_messages": list(self.proposal_messages),
            "data_sources": dict(self.data_sources),
            "data_source_records": dict(self.data_source_records),
            "referentials": dict(self.referentials),
            "file_uploads": dict(self.file_uploads),
            "users_by_email": dict(self.users_by_email),
            "users_by_id": dict(self.users_by_id),
            "user_sessions": dict(self.user_sessions),
        }

    def restore(self, snap: dict[str, Any]) -> None:
        for name, value in snap.items():
            setattr(self, name, value)


class InMemorySessionRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def add_many(self, rows: list[SessionRow]) -> InsertOutcome:
        assigned: dict[UUID, int] = {}
        existing: dict[UUID, int] = {}
        duplicates: list[UUID] = []
        counted: set[tuple[int, str]] = set()
        for row in rows:
            key = (row.entity.data_source_id, row.entity.external_id)
            stored_id = self._s.session_keys.get(key)
            if stored_id is None:
                new_id = self._s.ids.take()
                self._s.session_keys[key] = new_id
                self._s.sessions[new_id] = (row.entity, row)
                assigned[row.entity.id] = new_id
                continue
            existing[row.entity.id] = stored_id
            _, stored_row = self._s.sessions[stored_id]
            # Same run (earlier line or batch): the same session. Earlier run: a re-import.
            if stored_row.import_run_id != row.import_run_id and key not in counted:
                counted.add(key)
                duplicates.append(row.entity.id)
        return InsertOutcome(assigned=assigned, existing=existing, duplicates=tuple(duplicates))

    async def get(self, session_id: int) -> Session | None:
        found = self._s.sessions.get(session_id)
        return found[0] if found else None

    async def list(
        self,
        *,
        data_source_id: int | None = None,
        agent_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Session]:
        rows = [
            entity
            for entity, row in self._s.sessions.values()
            if (data_source_id is None or entity.data_source_id == data_source_id)
            and (agent_id is None or row.agent_id == agent_id)
        ]
        return rows[offset : offset + limit]

    async def count(self, *, data_source_id: int | None = None) -> int:
        return len(
            [
                e
                for e, _ in self._s.sessions.values()
                if data_source_id is None or e.data_source_id == data_source_id
            ]
        )


class InMemoryModelCallRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def add_many(
        self, rows: list[ModelCallRow], *, session_ids: dict[Any, int]
    ) -> InsertOutcome:
        assigned: dict[UUID, int] = {}
        existing: dict[UUID, int] = {}
        duplicates: list[UUID] = []
        unlinked: list[UUID] = []
        for row in rows:
            parent = session_ids.get(row.entity.session_id)
            if parent is None:
                unlinked.append(row.entity.id)
                continue
            key = (parent, row.entity.sequence_index)
            stored_id = self._s.model_call_keys.get(key)
            if stored_id is not None:
                existing[row.entity.id] = stored_id
                duplicates.append(row.entity.id)
                continue
            new_id = self._s.ids.take()
            self._s.model_call_keys[key] = new_id
            self._s.model_calls.append((new_id, row))
            assigned[row.entity.id] = new_id
        return InsertOutcome(
            assigned=assigned,
            existing=existing,
            duplicates=tuple(duplicates),
            unlinked=tuple(unlinked),
        )


class InMemoryToolCallRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def add_many(
        self,
        rows: list[ToolCallRow],
        *,
        session_ids: dict[Any, int],
        model_call_ids: dict[Any, int] | None = None,
    ) -> InsertOutcome:
        assigned: dict[UUID, int] = {}
        existing: dict[UUID, int] = {}
        duplicates: list[UUID] = []
        unlinked: list[UUID] = []
        for row in rows:
            parent = session_ids.get(row.entity.session_id)
            if parent is None:
                unlinked.append(row.entity.id)
                continue
            key = (parent, row.entity.sequence_index)
            stored_id = self._s.tool_call_keys.get(key)
            if stored_id is not None:
                existing[row.entity.id] = stored_id
                duplicates.append(row.entity.id)
                continue
            new_id = self._s.ids.take()
            self._s.tool_call_keys[key] = new_id
            self._s.tool_calls.append((new_id, row))
            assigned[row.entity.id] = new_id
        return InsertOutcome(
            assigned=assigned,
            existing=existing,
            duplicates=tuple(duplicates),
            unlinked=tuple(unlinked),
        )


class InMemoryRawRecordRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def add_many(
        self, *, import_run_id: int, records: list[tuple[int, dict[str, Any]]]
    ) -> dict[int, int]:
        out: dict[int, int] = {}
        for line_number, payload in records:
            key = (import_run_id, line_number)
            if key in self._s.raw_records:
                out[line_number] = self._s.raw_records[key]
                continue
            new_id = self._s.ids.take()
            self._s.raw_records[key] = new_id
            self._s.payloads[new_id] = payload
            out[line_number] = new_id
        return out


class InMemoryImportRunRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def create(self, *, data_source_id: int, file_upload_id: int, mapping_id: int) -> int:
        new_id = self._s.ids.take()
        self._s.import_runs[new_id] = {
            "data_source_id": data_source_id,
            "file_upload_id": file_upload_id,
            "mapping_id": mapping_id,
            "status": "pending",
            "records_read": 0,
            "records_imported": 0,
            "records_duplicate": 0,
            "records_rejected": 0,
            "fields_missing": None,
            "error_summary": None,
            "started_at": None,
            "finished_at": None,
            "created_at": datetime.now(UTC),
        }
        return new_id

    async def get(self, import_run_id: int) -> dict[str, Any] | None:
        run = self._s.import_runs.get(import_run_id)
        return dict(run, id=import_run_id) if run else None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        # `id` breaks ties: two runs created in the same clock tick must still
        # sort most-recent-first, deterministically.
        ids = sorted(
            self._s.import_runs,
            key=lambda i: (self._s.import_runs[i]["created_at"], i),
            reverse=True,
        )
        page = ids[offset : offset + limit]
        return [dict(self._s.import_runs[i], id=i) for i in page]

    async def count(self) -> int:
        return len(self._s.import_runs)

    async def save_report(self, import_run_id: int, report: ImportReport, *, status: str) -> None:
        self._s.reports[import_run_id] = report
        if import_run_id in self._s.import_runs:
            self._s.import_runs[import_run_id].update(
                status=status,
                records_read=report.records_read,
                records_imported=report.records_imported,
                records_duplicate=report.records_duplicate,
                records_rejected=report.records_rejected,
                finished_at=datetime.now(UTC),
            )

    async def get_report(self, import_run_id: int) -> ImportReport | None:
        return self._s.reports.get(import_run_id)


class InMemoryImportIssueRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def add_many(
        self, *, import_run_id: int, issues: list[tuple[ImportIssue, int | None]]
    ) -> None:
        for issue, raw_record_id in issues:
            self._s.issues.append((import_run_id, issue, raw_record_id))

    async def list(
        self, *, import_run_id: int, severity: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ImportIssueRecord]:
        # Mirrors the SQL outer join: the line number is the linked raw_record's,
        # never the one the issue was built with, and null without a raw_record.
        lines = {raw_id: line for (_, line), raw_id in self._s.raw_records.items()}
        found = [
            ImportIssueRecord(
                issue=ImportIssue(
                    severity=issue.severity,
                    code=issue.code,
                    message=issue.message,
                    field_path=issue.field_path,
                    line_number=None if raw_record_id is None else lines.get(raw_record_id),
                ),
                raw_record_id=raw_record_id,
            )
            for run_id, issue, raw_record_id in self._s.issues
            if run_id == import_run_id and (severity is None or issue.severity == severity)
        ]
        return found[offset : offset + limit]

    async def count(self, *, import_run_id: int, severity: str | None = None) -> int:
        return sum(
            1
            for run_id, issue, _ in self._s.issues
            if run_id == import_run_id and (severity is None or issue.severity == severity)
        )


class InMemoryMappingRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def get(self, mapping_id: int) -> Mapping | None:
        found = self._s.mappings.get(mapping_id)
        return found[0] if found else None

    async def save(self, mapping: Mapping, *, data_source_id: int) -> int:
        if any(
            stored_source == data_source_id
            and stored_mapping.name == mapping.name
            and stored_mapping.version == mapping.version
            for stored_mapping, stored_source, _status, _created_at in self._s.mappings.values()
        ):
            raise ConflictError(
                "Un mapping avec ce nom et cette version existe déjà.",
                details={
                    "data_source_id": data_source_id,
                    "name": mapping.name,
                    "version": mapping.version,
                },
            )
        new_id = self._s.ids.take()
        self._s.mappings[new_id] = (mapping, data_source_id, "active", datetime.now(UTC))
        return new_id

    async def list(self, *, data_source_id: int | None = None) -> list[Mapping]:
        return [
            m
            for m, source, _status, _created_at in self._s.mappings.values()
            if data_source_id is None or source == data_source_id
        ]

    async def get_by_id(self, mapping_id: int) -> dict[str, Any] | None:
        found = self._s.mappings.get(mapping_id)
        if found is None:
            return None
        return self._to_row(mapping_id, found)

    async def get_by_id_for_update(self, mapping_id: int) -> dict[str, Any] | None:
        return await self.get_by_id(mapping_id)

    async def name_exists(self, *, data_source_id: int, name: str) -> bool:
        return any(
            source == data_source_id and mapping.name == name
            for mapping, source, _status, _created_at in self._s.mappings.values()
        )

    async def list_records(
        self,
        *,
        data_source_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        matched = [
            (mapping_id, entry)
            for mapping_id, entry in self._s.mappings.items()
            if (data_source_id is None or entry[1] == data_source_id)
            and (status is None or entry[2] == status)
        ]
        matched.sort(key=lambda item: (item[1][3], item[0]), reverse=True)
        page = matched[offset : offset + limit]
        return [self._to_row(mapping_id, entry) for mapping_id, entry in page]

    async def count(self, *, data_source_id: int | None = None, status: str | None = None) -> int:
        return sum(
            1
            for _mapping, source, st, _created_at in self._s.mappings.values()
            if (data_source_id is None or source == data_source_id)
            and (status is None or st == status)
        )

    async def latest_version(self, *, data_source_id: int, name: str) -> int | None:
        versions = [
            mapping.version
            for mapping, source, _status, _created_at in self._s.mappings.values()
            if source == data_source_id and mapping.name == name
        ]
        return max(versions) if versions else None

    async def supersede(self, mapping_id: int) -> None:
        found = self._s.mappings.get(mapping_id)
        if found is not None:
            mapping, source, _status, created_at = found
            self._s.mappings[mapping_id] = (mapping, source, "superseded", created_at)

    @staticmethod
    def _to_row(mapping_id: int, entry: tuple[Mapping, int, str, datetime]) -> dict[str, Any]:
        from agentlen.infrastructure.persistence.repositories.mapping_codec import (
            mapping_to_document,
        )

        mapping, data_source_id, status, created_at = entry
        return {
            "id": mapping_id,
            "data_source_id": data_source_id,
            "name": mapping.name,
            "version": mapping.version,
            "source_format": mapping.source_format,
            "status": status,
            "document": mapping_to_document(mapping),
            "created_at": created_at,
        }


class InMemoryDataSourceRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def get_by_slug(self, slug: str) -> int | None:
        return self._s.data_sources.get(slug)

    async def get_by_id(self, data_source_id: int) -> DataSourceRecord | None:
        return self._s.data_source_records.get(data_source_id)

    async def list(self) -> list[DataSourceRecord]:
        return sorted(self._s.data_source_records.values(), key=lambda r: r.name)

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
    ) -> int:
        if slug in self._s.data_sources:
            return self._s.data_sources[slug]
        new_id = self._s.ids.take()
        self._s.data_sources[slug] = new_id
        self._s.data_source_records[new_id] = DataSourceRecord(
            id=new_id,
            slug=slug,
            name=name,
            description=description,
            url=url,
            license=license,
            dataset_version=dataset_version,
            retrieved_at=retrieved_at,
            created_at=datetime.now(UTC),
        )
        return new_id


class InMemoryFileUploadRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def get_by_hash(self, content_hash: str) -> FileUploadRecord | None:
        return self._s.file_uploads.get(content_hash)

    async def get_by_id(self, file_upload_id: int) -> FileUploadRecord | None:
        return next((r for r in self._s.file_uploads.values() if r.id == file_upload_id), None)

    async def create(
        self,
        *,
        original_name: str,
        storage_path: str,
        format: str,
        size_bytes: int,
        content_hash: str,
    ) -> FileUploadRecord:
        # Same UNIQUE(content_hash) the database enforces.
        if content_hash in self._s.file_uploads:
            return self._s.file_uploads[content_hash]
        record = FileUploadRecord(
            id=self._s.ids.take(),
            original_name=original_name,
            storage_path=storage_path,
            format=format,
            size_bytes=size_bytes,
            content_hash=content_hash,
        )
        self._s.file_uploads[content_hash] = record
        return record

    async def import_run_ids(self, file_upload_id: int) -> list[int]:
        return sorted(
            (
                run_id
                for run_id, run in self._s.import_runs.items()
                if run["file_upload_id"] == file_upload_id
            ),
            reverse=True,
        )


class InMemoryReferentialRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def resolve(self, kind: str, name: str, *, context: dict[str, str] | None = None) -> int:
        # The context is part of the key, so two providers publishing a
        # same-named model do not collapse into one row.
        marker = ";".join(f"{k}={v}" for k, v in sorted((context or {}).items()))
        key = (kind, name, marker)
        if key not in self._s.referentials:
            self._s.referentials[key] = self._s.ids.take()
        return self._s.referentials[key]


class InMemoryMappingProposalRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def save(
        self,
        proposal: MappingProposal,
        *,
        file_upload_id: int,
        data_source_id: int | None = None,
    ) -> int:
        proposal_id = self._s.ids.take()
        self._s.mapping_proposals[proposal_id] = proposal
        return proposal_id

    async def get(self, proposal_id: int) -> MappingProposal | None:
        return self._s.mapping_proposals.get(proposal_id)

    async def update(self, proposal_id: int, proposal: MappingProposal) -> None:
        self._s.mapping_proposals[proposal_id] = proposal

    async def add_message(self, proposal_id: int, *, role: str, content: str) -> None:
        self._s.proposal_messages.append((proposal_id, role, content))

    async def list_messages(self, proposal_id: int, *, limit: int) -> list[dict[str, str | int]]:
        all_messages = [m for m in self._s.proposal_messages if m[0] == proposal_id]
        start = max(len(all_messages) - limit, 0)
        messages = all_messages[start:] if limit > 0 else []
        return [
            {"turn_index": start + index, "role": role, "content": content}
            for index, (_, role, content) in enumerate(messages)
        ]


class InMemoryUserRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def get_by_email(self, email: str) -> UserRecord | None:
        return self._s.users_by_email.get(email)

    async def get_by_id(self, user_id: int) -> UserRecord | None:
        return self._s.users_by_id.get(user_id)

    async def create(self, *, email: str, password_hash: str) -> UserRecord:
        if email in self._s.users_by_email:
            raise ConflictError(
                f"Un compte existe déjà pour l'adresse '{email}'.", details={"email": email}
            )
        record = UserRecord(
            id=self._s.ids.take(),
            email=email,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self._s.users_by_email[email] = record
        self._s.users_by_id[record.id] = record
        return record


class InMemoryUserSessionRepository:
    def __init__(self, store: _Store) -> None:
        self._s = store

    async def create(
        self, *, user_id: int, token: str, expires_at: datetime | None
    ) -> UserSessionRecord:
        record = UserSessionRecord(
            token=token, user_id=user_id, created_at=datetime.now(UTC), expires_at=expires_at
        )
        self._s.user_sessions[token] = record
        return record

    async def get_by_token(self, token: str) -> UserSessionRecord | None:
        return self._s.user_sessions.get(token)

    async def delete_by_token(self, token: str) -> None:
        self._s.user_sessions.pop(token, None)


class InMemoryUnitOfWork:
    """Real rollback: state is snapshotted on entry and restored unless
    `commit()` was called, so a test can assert that a failure left nothing
    behind — the same guarantee the SQLAlchemy version gives."""

    def __init__(self) -> None:
        self._store = _Store()
        self._snapshot: dict[str, Any] | None = None
        self.committed = False
        self.sessions = InMemorySessionRepository(self._store)
        self.model_calls = InMemoryModelCallRepository(self._store)
        self.tool_calls = InMemoryToolCallRepository(self._store)
        self.raw_records = InMemoryRawRecordRepository(self._store)
        self.import_runs = InMemoryImportRunRepository(self._store)
        self.import_issues = InMemoryImportIssueRepository(self._store)
        self.mappings = InMemoryMappingRepository(self._store)
        self.mapping_proposals = InMemoryMappingProposalRepository(self._store)
        self.data_sources = InMemoryDataSourceRepository(self._store)
        self.file_uploads = InMemoryFileUploadRepository(self._store)
        self.referentials = InMemoryReferentialRepository(self._store)
        self.users = InMemoryUserRepository(self._store)
        self.user_sessions = InMemoryUserSessionRepository(self._store)

    async def __aenter__(self) -> InMemoryUnitOfWork:
        self._snapshot = self._store.snapshot()
        self.committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True
        self._snapshot = self._store.snapshot()

    async def rollback(self) -> None:
        if self._snapshot is not None:
            self._store.restore(self._snapshot)
