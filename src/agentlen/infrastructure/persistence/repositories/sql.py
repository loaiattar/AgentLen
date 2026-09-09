"""SQLAlchemy implementations of the persistence ports.

Three rules run through the whole module:

**Insert in batches.** An import is tens of thousands of rows; one statement per
row spends the whole run on round trips. Every write here is a single
`INSERT ... VALUES (...), (...), ...`.

**Conflicts are answers, not errors.** Natural-key collisions use
`ON CONFLICT DO NOTHING RETURNING id`. Re-importing a file is expected, so a
collision is reported back to the use case to be counted as a duplicate
(DATA_MODEL.md §6) rather than raised.

**Everything is bound.** No value is ever formatted into SQL text, and no
identifier comes from a request — the target schema is closed and known.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from agentlen.application.dto.persistence import (
    FileUploadRecord,
    InsertOutcome,
    ModelCallRow,
    SessionRow,
    ToolCallRow,
)
from agentlen.domain.model.import_run import ImportIssue, ImportReport
from agentlen.domain.model.mapping import Mapping
from agentlen.domain.model.session import Session
from agentlen.infrastructure.persistence import tables as t


class _Base:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn


class SqlAlchemySessionRepository(_Base):
    async def add_many(self, rows: list[SessionRow]) -> InsertOutcome:
        if not rows:
            return InsertOutcome()

        values = [
            {
                "data_source_id": r.entity.data_source_id,
                "import_run_id": r.import_run_id,
                "raw_record_id": r.raw_record_id,
                "external_id": r.entity.external_id,
                "agent_id": r.agent_id,
                "repository_id": r.repository_id,
                "started_at": r.entity.started_at,
                "ended_at": r.entity.ended_at,
                "duration_ms": r.entity.duration_ms,
                "outcome": r.entity.outcome,
            }
            for r in rows
        ]
        statement = (
            insert(t.session)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_session_source_external")
            .returning(t.session.c.id, t.session.c.data_source_id, t.session.c.external_id)
        )
        returned = (await self._conn.execute(statement)).all()

        # RETURNING only yields the rows actually inserted, so anything missing
        # from it collided on the natural key.
        by_key = {(r.data_source_id, r.external_id): r.id for r in returned}
        assigned: dict[UUID, int] = {}
        duplicates: list[UUID] = []
        for row in rows:
            key = (row.entity.data_source_id, row.entity.external_id)
            if key in by_key:
                assigned[row.entity.id] = by_key[key]
            else:
                duplicates.append(row.entity.id)
        return InsertOutcome(assigned=assigned, duplicates=tuple(duplicates))

    async def get(self, session_id: int) -> Session | None:
        row = (
            (await self._conn.execute(select(t.session).where(t.session.c.id == session_id)))
            .mappings()
            .one_or_none()
        )
        return _to_session(row) if row else None

    async def list(
        self,
        *,
        data_source_id: int | None = None,
        agent_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Session]:
        query = select(t.session)
        if data_source_id is not None:
            query = query.where(t.session.c.data_source_id == data_source_id)
        if agent_id is not None:
            query = query.where(t.session.c.agent_id == agent_id)
        query = query.order_by(t.session.c.id).limit(limit).offset(offset)
        return [_to_session(r) for r in (await self._conn.execute(query)).mappings()]

    async def count(self, *, data_source_id: int | None = None) -> int:
        from sqlalchemy import func

        query = select(func.count()).select_from(t.session)
        if data_source_id is not None:
            query = query.where(t.session.c.data_source_id == data_source_id)
        return int((await self._conn.execute(query)).scalar_one())


def _to_session(row: Any) -> Session:
    """Row -> entity. Hand-written on purpose: the entity carries business
    fields, the row carries storage keys, and the two shapes differ (ADR-011)."""
    from uuid import uuid4

    return Session(
        # The persistent identity is row["id"]; the entity's UUID is in-batch
        # correlation only, so a fresh one is minted on read.
        id=uuid4(),
        data_source_id=row["data_source_id"],
        external_id=row["external_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        duration_ms=row["duration_ms"],
        outcome=row["outcome"],
    )


class SqlAlchemyModelCallRepository(_Base):
    async def add_many(
        self, rows: list[ModelCallRow], *, session_ids: dict[Any, int]
    ) -> InsertOutcome:
        pending = [(r, session_ids.get(r.entity.session_id)) for r in rows]
        insertable = [(r, sid) for r, sid in pending if sid is not None]
        # A child whose parent collided is itself already stored.
        orphans = tuple(r.entity.id for r, sid in pending if sid is None)
        if not insertable:
            return InsertOutcome(duplicates=orphans)

        values = [
            {
                "session_id": sid,
                "raw_record_id": r.raw_record_id,
                "model_id": r.model_id,
                "sequence_index": r.entity.sequence_index,
                "started_at": r.entity.started_at,
                "duration_ms": r.entity.duration_ms,
                "input_tokens": r.entity.token_usage.input_tokens,
                "output_tokens": r.entity.token_usage.output_tokens,
                "cache_read_tokens": r.entity.token_usage.cache_read_tokens,
                "cache_creation_tokens": r.entity.token_usage.cache_creation_tokens,
                "stop_reason": r.entity.stop_reason,
                "status": r.entity.status,
                "error_code": r.entity.error_code,
            }
            for r, sid in insertable
        ]
        statement = (
            insert(t.model_call)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_model_call_session_sequence")
            .returning(t.model_call.c.id, t.model_call.c.session_id, t.model_call.c.sequence_index)
        )
        returned = (await self._conn.execute(statement)).all()
        by_key = {(r.session_id, r.sequence_index): r.id for r in returned}

        assigned: dict[UUID, int] = {}
        duplicates = list(orphans)
        for row, sid in insertable:
            key = (sid, row.entity.sequence_index)
            if key in by_key:
                assigned[row.entity.id] = by_key[key]
            else:
                duplicates.append(row.entity.id)
        return InsertOutcome(assigned=assigned, duplicates=tuple(duplicates))


class SqlAlchemyToolCallRepository(_Base):
    async def add_many(
        self,
        rows: list[ToolCallRow],
        *,
        session_ids: dict[Any, int],
        model_call_ids: dict[Any, int] | None = None,
    ) -> InsertOutcome:
        model_call_ids = model_call_ids or {}
        pending = [(r, session_ids.get(r.entity.session_id)) for r in rows]
        insertable = [(r, sid) for r, sid in pending if sid is not None]
        orphans = tuple(r.entity.id for r, sid in pending if sid is None)
        if not insertable:
            return InsertOutcome(duplicates=orphans)

        values = [
            {
                "session_id": sid,
                "model_call_id": model_call_ids.get(r.entity.model_call_id),
                "raw_record_id": r.raw_record_id,
                "tool_id": r.tool_id,
                "sequence_index": r.entity.sequence_index,
                "started_at": r.entity.started_at,
                "duration_ms": r.entity.duration_ms,
                "status": r.entity.status,
                "error_message": r.entity.error_message,
            }
            for r, sid in insertable
        ]
        statement = (
            insert(t.tool_call)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_tool_call_session_sequence")
            .returning(t.tool_call.c.id, t.tool_call.c.session_id, t.tool_call.c.sequence_index)
        )
        returned = (await self._conn.execute(statement)).all()
        by_key = {(r.session_id, r.sequence_index): r.id for r in returned}

        assigned: dict[UUID, int] = {}
        duplicates = list(orphans)
        for row, sid in insertable:
            key = (sid, row.entity.sequence_index)
            if key in by_key:
                assigned[row.entity.id] = by_key[key]
            else:
                duplicates.append(row.entity.id)
        return InsertOutcome(assigned=assigned, duplicates=tuple(duplicates))


class SqlAlchemyRawRecordRepository(_Base):
    async def add_many(
        self, *, import_run_id: int, records: list[tuple[int, dict[str, Any]]]
    ) -> dict[int, int]:
        if not records:
            return {}
        from agentlen.domain.services.deduplicator import Deduplicator

        dedup = Deduplicator()
        values = [
            {
                "import_run_id": import_run_id,
                "line_number": line_number,
                "payload": payload,
                "content_hash": dedup.content_hash(payload),
            }
            for line_number, payload in records
        ]
        statement = (
            insert(t.raw_record)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_raw_record_run_line")
            .returning(t.raw_record.c.id, t.raw_record.c.line_number)
        )
        returned = (await self._conn.execute(statement)).all()
        return {r.line_number: r.id for r in returned}


class SqlAlchemyImportRunRepository(_Base):
    async def create(self, *, data_source_id: int, file_upload_id: int, mapping_id: int) -> int:
        statement = (
            insert(t.import_run)
            .values(
                data_source_id=data_source_id,
                file_upload_id=file_upload_id,
                mapping_id=mapping_id,
                status="pending",
            )
            .returning(t.import_run.c.id)
        )
        return int((await self._conn.execute(statement)).scalar_one())

    async def save_report(self, import_run_id: int, report: ImportReport, *, status: str) -> None:
        from sqlalchemy import func

        await self._conn.execute(
            t.import_run.update()
            .where(t.import_run.c.id == import_run_id)
            .values(
                status=status,
                records_read=report.records_read,
                records_imported=report.records_imported,
                records_duplicate=report.records_duplicate,
                records_rejected=report.records_rejected,
                finished_at=func.now(),
            )
        )

    async def get_report(self, import_run_id: int) -> ImportReport | None:
        row = (
            (
                await self._conn.execute(
                    select(t.import_run).where(t.import_run.c.id == import_run_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return ImportReport(
            records_read=row["records_read"],
            records_imported=row["records_imported"],
            records_duplicate=row["records_duplicate"],
            records_rejected=row["records_rejected"],
        )


class SqlAlchemyImportIssueRepository(_Base):
    async def add_many(
        self, *, import_run_id: int, issues: list[tuple[ImportIssue, int | None]]
    ) -> None:
        if not issues:
            return
        await self._conn.execute(
            insert(t.import_issue).values(
                [
                    {
                        "import_run_id": import_run_id,
                        "raw_record_id": raw_record_id,
                        "severity": issue.severity,
                        "code": issue.code,
                        "field_path": issue.field_path,
                        "message": issue.message,
                    }
                    for issue, raw_record_id in issues
                ]
            )
        )

    async def list(
        self, *, import_run_id: int, severity: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ImportIssue]:
        query = select(t.import_issue).where(t.import_issue.c.import_run_id == import_run_id)
        if severity is not None:
            query = query.where(t.import_issue.c.severity == severity)
        query = query.order_by(t.import_issue.c.id).limit(limit).offset(offset)
        return [
            ImportIssue(
                severity=r["severity"],
                code=r["code"],
                message=r["message"],
                field_path=r["field_path"],
            )
            for r in (await self._conn.execute(query)).mappings()
        ]


class SqlAlchemyMappingRepository(_Base):
    async def get(self, mapping_id: int) -> Mapping | None:
        row = (
            (await self._conn.execute(select(t.mapping).where(t.mapping.c.id == mapping_id)))
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        from agentlen.infrastructure.persistence.repositories.mapping_codec import (
            document_to_mapping,
        )

        return document_to_mapping(row["document"], name=row["name"], version=row["version"])

    async def save(self, mapping: Mapping, *, data_source_id: int) -> int:
        from agentlen.infrastructure.persistence.repositories.mapping_codec import (
            mapping_to_document,
        )

        statement = (
            insert(t.mapping)
            .values(
                data_source_id=data_source_id,
                name=mapping.name,
                version=mapping.version,
                source_format=mapping.source_format,
                document=mapping_to_document(mapping),
                status="active",
            )
            .returning(t.mapping.c.id)
        )
        return int((await self._conn.execute(statement)).scalar_one())

    async def list(self, *, data_source_id: int | None = None) -> list[Mapping]:
        from agentlen.infrastructure.persistence.repositories.mapping_codec import (
            document_to_mapping,
        )

        query = select(t.mapping)
        if data_source_id is not None:
            query = query.where(t.mapping.c.data_source_id == data_source_id)
        return [
            document_to_mapping(r["document"], name=r["name"], version=r["version"])
            for r in (await self._conn.execute(query.order_by(t.mapping.c.id))).mappings()
        ]


class SqlAlchemyFileUploadRepository(_Base):
    async def get_by_hash(self, content_hash: str) -> FileUploadRecord | None:
        row = (
            (
                await self._conn.execute(
                    select(t.file_upload).where(t.file_upload.c.content_hash == content_hash)
                )
            )
            .mappings()
            .one_or_none()
        )
        return _to_file_upload(row) if row else None

    async def get_by_id(self, file_upload_id: int) -> FileUploadRecord | None:
        row = (
            (
                await self._conn.execute(
                    select(t.file_upload).where(t.file_upload.c.id == file_upload_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        return _to_file_upload(row) if row else None

    async def create(
        self,
        *,
        original_name: str,
        storage_path: str,
        format: str,
        size_bytes: int,
        content_hash: str,
    ) -> FileUploadRecord:
        statement = (
            insert(t.file_upload)
            .values(
                original_name=original_name,
                storage_path=storage_path,
                format=format,
                size_bytes=size_bytes,
                content_hash=content_hash,
            )
            .on_conflict_do_nothing(index_elements=[t.file_upload.c.content_hash])
            .returning(t.file_upload)
        )
        created = (await self._conn.execute(statement)).mappings().one_or_none()
        if created is not None:
            return _to_file_upload(created)
        # Lost a race with a concurrent upload of identical bytes: the other
        # writer's row is the right answer.
        existing = await self.get_by_hash(content_hash)
        assert existing is not None
        return existing

    async def import_run_ids(self, file_upload_id: int) -> list[int]:
        rows = await self._conn.execute(
            select(t.import_run.c.id)
            .where(t.import_run.c.file_upload_id == file_upload_id)
            .order_by(t.import_run.c.id.desc())
        )
        return [int(r[0]) for r in rows]


def _to_file_upload(row: Any) -> FileUploadRecord:
    return FileUploadRecord(
        id=row["id"],
        original_name=row["original_name"],
        storage_path=row["storage_path"],
        format=row["format"],
        size_bytes=row["size_bytes"],
        content_hash=row["content_hash"],
    )


class SqlAlchemyDataSourceRepository(_Base):
    async def get_by_slug(self, slug: str) -> int | None:
        return (
            await self._conn.execute(select(t.data_source.c.id).where(t.data_source.c.slug == slug))
        ).scalar_one_or_none()

    async def create(self, *, slug: str, name: str) -> int:
        statement = (
            insert(t.data_source)
            .values(slug=slug, name=name)
            .on_conflict_do_nothing(index_elements=[t.data_source.c.slug])
            .returning(t.data_source.c.id)
        )
        existing = (await self._conn.execute(statement)).scalar_one_or_none()
        if existing is not None:
            return int(existing)
        found = await self.get_by_slug(slug)
        assert found is not None
        return found


#: kind -> (table, extra key columns resolved from the request context)
_REFERENTIAL_TABLES: dict[str, Any] = {
    "provider": t.provider,
    "model": t.model,
    "agent": t.agent,
    "tool": t.tool,
    "repository": t.repository,
}


class SqlAlchemyReferentialRepository(_Base):
    """Upsert-by-name, with the composite keys DATA_MODEL.md §4 requires.

    `model` is unique on `(provider_id, name)` and `repository` on
    `(host, owner, name)`, so those two resolve their extra key components from
    the request context rather than colliding on the name alone.
    """

    async def resolve(self, kind: str, name: str, *, context: dict[str, str] | None = None) -> int:
        if kind not in _REFERENTIAL_TABLES:
            raise ValueError(f"Unknown referential kind '{kind}'")
        context = context or {}

        if kind == "model":
            provider_id = await self.resolve("provider", context.get("provider_name", "unknown"))
            return await self._upsert(
                t.model,
                {"provider_id": provider_id, "name": name},
                ["provider_id", "name"],
            )
        if kind == "repository":
            return await self._upsert(
                t.repository,
                {
                    "host": context.get("host", "github.com"),
                    "owner": context.get("owner", "unknown"),
                    "name": name,
                },
                ["host", "owner", "name"],
            )
        if kind == "agent":
            return await self._upsert(
                t.agent, {"name": name, "version": context.get("version")}, ["name", "version"]
            )
        return await self._upsert(_REFERENTIAL_TABLES[kind], {"name": name}, ["name"])

    async def _upsert(self, table: Any, values: dict[str, Any], key: list[str]) -> int:
        statement = (
            insert(table)
            .values(**values)
            .on_conflict_do_nothing(index_elements=key)
            .returning(table.c.id)
        )
        created = (await self._conn.execute(statement)).scalar_one_or_none()
        if created is not None:
            return int(created)

        query = select(table.c.id)
        for column in key:
            query = query.where(
                table.c[column].is_(values[column])
                if values[column] is None
                else table.c[column] == values[column]
            )
        return int((await self._conn.execute(query)).scalar_one())
