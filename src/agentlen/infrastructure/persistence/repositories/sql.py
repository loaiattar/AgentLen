"""SQLAlchemy implementations of the persistence ports.

Three rules run through the whole module:

**Insert in batches.** An import is tens of thousands of rows; one statement per
row spends the whole run on round trips. Every write here is a multi-row
`INSERT ... VALUES (...), (...), ...`, split into several statements only when
the batch would bind more parameters than asyncpg accepts (`_insert_many`).

**Conflicts are answers, not errors.** Natural-key collisions use
`ON CONFLICT DO NOTHING RETURNING id`. Re-importing a file is expected, so a
collision is reported back to the use case to be counted as a duplicate
(DATA_MODEL.md §6) rather than raised.

**Everything is bound.** No value is ever formatted into SQL text, and no
identifier comes from a request — the target schema is closed and known.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

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
from agentlen.infrastructure.persistence import tables as t

# asyncpg numbers bind parameters with a signed 16-bit integer: one statement
# accepts at most 32 767 of them. A module constant so tests can lower it.
MAX_BIND_PARAMETERS = 32_767


def _slices[T](items: list[T], width: int) -> Iterator[list[T]]:
    """Consecutive slices of `items`, each small enough for one statement.

    `width` is what one item binds: a table's column count for an INSERT row
    (an upper bound, a column left out binds nothing) or a key's arity for a
    tuple `IN` lookup.
    """
    size = max(1, MAX_BIND_PARAMETERS // width)
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def _insert_many(
    conn: AsyncConnection,
    table: Any,
    values: list[dict[str, Any]],
    *,
    constraint: str | None = None,
    returning: tuple[Any, ...] = (),
) -> list[Any]:
    """`INSERT ... VALUES` in as many statements as the bind limit requires.

    Slices keep the rows' order and share the caller's transaction, and the
    RETURNING rows of every statement are concatenated: callers reconcile, count
    and roll back a split batch exactly as they would a single statement.
    """
    returned: list[Any] = []
    for chunk in _slices(values, len(table.c)):
        statement = insert(table).values(chunk)
        if constraint is not None:
            statement = statement.on_conflict_do_nothing(constraint=constraint)
        if returning:
            returned.extend((await conn.execute(statement.returning(*returning))).all())
        else:
            await conn.execute(statement)
    return returned


class _Base:
    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn


class SqlAlchemySessionRepository(_Base):
    async def add_many(self, rows: list[SessionRow]) -> InsertOutcome:
        if not rows:
            return InsertOutcome()

        # One candidate per natural key. Several lines of one file routinely
        # carry the same session (TraceLab writes one line per round): they
        # describe one session, so the first is written and the rest attach to it.
        candidates: dict[tuple[int, str], SessionRow] = {}
        for row in rows:
            candidates.setdefault(_session_key(row), row)

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
            for r in candidates.values()
        ]
        inserted = await _insert_many(
            self._conn,
            t.session,
            values,
            constraint="uq_session_source_external",
            returning=(t.session.c.id, t.session.c.data_source_id, t.session.c.external_id),
        )
        written = {(r.data_source_id, r.external_id): r.id for r in inserted}
        # RETURNING only yields the rows actually inserted: every other key is
        # already stored, and its children still need that row's id.
        stored = await self._stored([key for key in candidates if key not in written])

        assigned: dict[UUID, int] = {}
        existing: dict[UUID, int] = {}
        duplicates: list[UUID] = []
        for row in rows:
            key = _session_key(row)
            first = candidates[key] is row
            if key in written:
                (assigned if first else existing)[row.entity.id] = written[key]
                continue
            if key not in stored:
                raise RuntimeError(f"Session {key} neither inserted nor found after conflict.")
            row_id, stored_run_id = stored[key]
            existing[row.entity.id] = row_id
            # Stored by a previous import: that is what a re-import looks like.
            # Stored earlier in this run (a previous batch): the same session.
            if first and stored_run_id != row.import_run_id:
                duplicates.append(row.entity.id)
        return InsertOutcome(assigned=assigned, existing=existing, duplicates=tuple(duplicates))

    async def _stored(self, keys: list[tuple[int, str]]) -> dict[tuple[int, str], tuple[int, int]]:
        """Id and import run of the sessions already holding these natural keys."""
        found: dict[tuple[int, str], tuple[int, int]] = {}
        # Each key binds two parameters: a large re-import hits the limit here too.
        for chunk in _slices(keys, 2):
            query = select(
                t.session.c.id,
                t.session.c.data_source_id,
                t.session.c.external_id,
                t.session.c.import_run_id,
            ).where(tuple_(t.session.c.data_source_id, t.session.c.external_id).in_(chunk))
            for r in (await self._conn.execute(query)).all():
                found[(r.data_source_id, r.external_id)] = (r.id, r.import_run_id)
        return found

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
        linked, unlinked = _link_to_sessions(rows, session_ids)
        if not linked:
            return InsertOutcome(unlinked=unlinked)

        candidates: dict[tuple[int, int], tuple[ModelCallRow, int]] = {}
        for row, sid in linked:
            candidates.setdefault((sid, row.entity.sequence_index), (row, sid))

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
            for r, sid in candidates.values()
        ]
        inserted = await _insert_many(
            self._conn,
            t.model_call,
            values,
            constraint="uq_model_call_session_sequence",
            returning=(t.model_call.c.id, t.model_call.c.session_id, t.model_call.c.sequence_index),
        )
        written = {(r.session_id, r.sequence_index): r.id for r in inserted}
        stored = await _stored_calls(
            self._conn, t.model_call, [key for key in candidates if key not in written]
        )
        return _call_outcome(linked, candidates, written, stored, unlinked)


class SqlAlchemyToolCallRepository(_Base):
    async def add_many(
        self,
        rows: list[ToolCallRow],
        *,
        session_ids: dict[Any, int],
        model_call_ids: dict[Any, int] | None = None,
    ) -> InsertOutcome:
        model_call_ids = model_call_ids or {}
        linked, unlinked = _link_to_sessions(rows, session_ids)
        if not linked:
            return InsertOutcome(unlinked=unlinked)

        candidates: dict[tuple[int, int], tuple[ToolCallRow, int]] = {}
        for row, sid in linked:
            candidates.setdefault((sid, row.entity.sequence_index), (row, sid))

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
            for r, sid in candidates.values()
        ]
        inserted = await _insert_many(
            self._conn,
            t.tool_call,
            values,
            constraint="uq_tool_call_session_sequence",
            returning=(t.tool_call.c.id, t.tool_call.c.session_id, t.tool_call.c.sequence_index),
        )
        written = {(r.session_id, r.sequence_index): r.id for r in inserted}
        stored = await _stored_calls(
            self._conn, t.tool_call, [key for key in candidates if key not in written]
        )
        return _call_outcome(linked, candidates, written, stored, unlinked)


def _session_key(row: SessionRow) -> tuple[int, str]:
    return (row.entity.data_source_id, row.entity.external_id)


def _link_to_sessions(
    rows: list[Any], session_ids: dict[Any, int]
) -> tuple[list[tuple[Any, int]], tuple[UUID, ...]]:
    """Pair each call with its session's database id; set apart those with none."""
    linked: list[tuple[Any, int]] = []
    unlinked: list[UUID] = []
    for row in rows:
        sid = session_ids.get(row.entity.session_id)
        if sid is None:
            unlinked.append(row.entity.id)
        else:
            linked.append((row, sid))
    return linked, tuple(unlinked)


async def _stored_calls(
    conn: AsyncConnection, table: Any, keys: list[tuple[int, int]]
) -> dict[tuple[int, int], int]:
    """Id of the calls already holding these (session, sequence) keys."""
    found: dict[tuple[int, int], int] = {}
    for chunk in _slices(keys, 2):
        query = select(table.c.id, table.c.session_id, table.c.sequence_index).where(
            tuple_(table.c.session_id, table.c.sequence_index).in_(chunk)
        )
        for r in (await conn.execute(query)).all():
            found[(r.session_id, r.sequence_index)] = r.id
    return found


def _call_outcome(
    linked: list[tuple[Any, int]],
    candidates: dict[tuple[int, int], tuple[Any, int]],
    written: dict[tuple[int, int], int],
    stored: dict[tuple[int, int], int],
    unlinked: tuple[UUID, ...],
) -> InsertOutcome:
    """A call is an event: the same key twice, in this batch or already stored,
    is the same call recorded twice — a duplicate, still resolvable by id."""
    assigned: dict[UUID, int] = {}
    existing: dict[UUID, int] = {}
    duplicates: list[UUID] = []
    for row, sid in linked:
        key = (sid, row.entity.sequence_index)
        if key in written and candidates[key][0] is row:
            assigned[row.entity.id] = written[key]
            continue
        if key not in written and key not in stored:
            raise RuntimeError(f"Call {key} neither inserted nor found after conflict.")
        existing[row.entity.id] = written[key] if key in written else stored[key]
        duplicates.append(row.entity.id)
    return InsertOutcome(
        assigned=assigned, existing=existing, duplicates=tuple(duplicates), unlinked=unlinked
    )


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
        returned = await _insert_many(
            self._conn,
            t.raw_record,
            values,
            constraint="uq_raw_record_run_line",
            returning=(t.raw_record.c.id, t.raw_record.c.line_number),
        )
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

    async def get(self, import_run_id: int) -> dict[str, Any] | None:
        row = (
            (
                await self._conn.execute(
                    select(t.import_run).where(t.import_run.c.id == import_run_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row else None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        query = (
            select(t.import_run)
            .order_by(t.import_run.c.created_at.desc(), t.import_run.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [dict(r) for r in (await self._conn.execute(query)).mappings()]

    async def count(self) -> int:
        from sqlalchemy import func

        return int(
            (await self._conn.execute(select(func.count()).select_from(t.import_run))).scalar_one()
        )

    @staticmethod
    def _report_columns(report: ImportReport) -> dict[str, Any]:
        return {
            "records_read": report.records_read,
            "records_imported": report.records_imported,
            "records_duplicate": report.records_duplicate,
            "records_rejected": report.records_rejected,
            "fields_missing": dict(report.fields_missing),
        }

    async def save_progress(self, import_run_id: int, report: ImportReport) -> None:
        await self._conn.execute(
            t.import_run.update()
            .where(t.import_run.c.id == import_run_id)
            .values(**self._report_columns(report))
        )

    async def save_report(self, import_run_id: int, report: ImportReport, *, status: str) -> None:
        from sqlalchemy import func

        await self._conn.execute(
            t.import_run.update()
            .where(t.import_run.c.id == import_run_id)
            .values(status=status, finished_at=func.now(), **self._report_columns(report))
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
            fields_missing=dict(row["fields_missing"] or {}),
        )


class SqlAlchemyImportIssueRepository(_Base):
    async def add_many(
        self, *, import_run_id: int, issues: list[tuple[ImportIssue, int | None]]
    ) -> None:
        if not issues:
            return
        await _insert_many(
            self._conn,
            t.import_issue,
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
            ],
        )

    async def list(
        self, *, import_run_id: int, severity: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[ImportIssueRecord]:
        # `import_issue` stores no line number: it is read from the raw_record
        # the issue points at. Outer join, so run-level issues with no
        # raw_record are still listed, with a null line.
        query = (
            select(t.import_issue, t.raw_record.c.line_number)
            .select_from(
                t.import_issue.outerjoin(
                    t.raw_record, t.raw_record.c.id == t.import_issue.c.raw_record_id
                )
            )
            .where(t.import_issue.c.import_run_id == import_run_id)
        )
        if severity is not None:
            query = query.where(t.import_issue.c.severity == severity)
        query = query.order_by(t.import_issue.c.id).limit(limit).offset(offset)
        return [
            ImportIssueRecord(
                issue=ImportIssue(
                    severity=r["severity"],
                    code=r["code"],
                    message=r["message"],
                    field_path=r["field_path"],
                    line_number=r["line_number"],
                ),
                raw_record_id=r["raw_record_id"],
            )
            for r in (await self._conn.execute(query)).mappings()
        ]

    async def count(self, *, import_run_id: int, severity: str | None = None) -> int:
        from sqlalchemy import func

        query = (
            select(func.count())
            .select_from(t.import_issue)
            .where(t.import_issue.c.import_run_id == import_run_id)
        )
        if severity is not None:
            query = query.where(t.import_issue.c.severity == severity)
        return int((await self._conn.execute(query)).scalar_one())


class SqlAlchemyMappingRepository(_Base):
    # Ordered so no method named `list` precedes a bare `list[...]` return
    # annotation in this class body — mypy resolves that bare name against the
    # class's own namespace once `list` the method exists, not the builtin.
    async def get_by_id(self, mapping_id: int) -> dict[str, Any] | None:
        row = (
            (await self._conn.execute(select(t.mapping).where(t.mapping.c.id == mapping_id)))
            .mappings()
            .one_or_none()
        )
        return dict(row) if row else None

    async def list_records(
        self,
        *,
        data_source_id: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = select(t.mapping)
        if data_source_id is not None:
            query = query.where(t.mapping.c.data_source_id == data_source_id)
        if status is not None:
            query = query.where(t.mapping.c.status == status)
        query = (
            query.order_by(t.mapping.c.created_at.desc(), t.mapping.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [dict(r) for r in (await self._conn.execute(query)).mappings()]

    async def count(self, *, data_source_id: int | None = None, status: str | None = None) -> int:
        from sqlalchemy import func

        query = select(func.count()).select_from(t.mapping)
        if data_source_id is not None:
            query = query.where(t.mapping.c.data_source_id == data_source_id)
        if status is not None:
            query = query.where(t.mapping.c.status == status)
        return int((await self._conn.execute(query)).scalar_one())

    async def latest_version(self, *, data_source_id: int, name: str) -> int | None:
        from sqlalchemy import func

        query = select(func.max(t.mapping.c.version)).where(
            t.mapping.c.data_source_id == data_source_id,
            t.mapping.c.name == name,
        )
        highest = (await self._conn.execute(query)).scalar_one_or_none()
        return int(highest) if highest is not None else None

    async def supersede(self, mapping_id: int) -> None:
        await self._conn.execute(
            t.mapping.update().where(t.mapping.c.id == mapping_id).values(status="superseded")
        )

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


class SqlAlchemyMappingProposalRepository(_Base):
    async def save(
        self,
        proposal: MappingProposal,
        *,
        file_upload_id: int,
        data_source_id: int | None = None,
    ) -> int:
        from agentlen.infrastructure.persistence.repositories.mapping_codec import (
            mapping_to_document,
        )

        descriptor = proposal.analyzer_descriptor
        statement = (
            insert(t.mapping_proposal)
            .values(
                data_source_id=data_source_id,
                file_upload_id=file_upload_id,
                document=mapping_to_document(proposal.mapping),
                validation=_validation_document(proposal.mapping),
                rationale=list(proposal.rationale),
                ambiguities=list(proposal.ambiguities),
                unmapped_fields=list(proposal.unmapped_fields),
                analyzer_provider=descriptor.get("provider", "unknown"),
                analyzer_model=descriptor.get("model", "unknown"),
                prompt_version=descriptor.get("prompt_version"),
            )
            .returning(t.mapping_proposal.c.id)
        )
        return int((await self._conn.execute(statement)).scalar_one())

    async def get(self, proposal_id: int) -> MappingProposal | None:
        row = (
            (
                await self._conn.execute(
                    select(t.mapping_proposal).where(t.mapping_proposal.c.id == proposal_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        return _to_mapping_proposal(row) if row else None

    async def update(self, proposal_id: int, proposal: MappingProposal) -> None:
        from sqlalchemy import update

        from agentlen.infrastructure.persistence.repositories.mapping_codec import (
            mapping_to_document,
        )

        await self._conn.execute(
            update(t.mapping_proposal)
            .where(t.mapping_proposal.c.id == proposal_id)
            .values(
                document=mapping_to_document(proposal.mapping),
                validation=_validation_document(proposal.mapping),
                rationale=list(proposal.rationale),
                ambiguities=list(proposal.ambiguities),
                unmapped_fields=list(proposal.unmapped_fields),
            )
        )

    async def add_message(self, proposal_id: int, *, role: str, content: str) -> None:
        from sqlalchemy import func

        next_turn = select(
            func.coalesce(func.max(t.mapping_proposal_message.c.turn_index), -1) + 1
        ).where(t.mapping_proposal_message.c.mapping_proposal_id == proposal_id)
        await self._conn.execute(
            insert(t.mapping_proposal_message).values(
                mapping_proposal_id=proposal_id,
                turn_index=next_turn.scalar_subquery(),
                role=role,
                content=content,
            )
        )

    async def list_messages(self, proposal_id: int, *, limit: int) -> list[dict[str, str | int]]:
        # Postgres refuses a negative LIMIT outright — it does not read it as
        # "no limit" — and `LIMIT 0` costs a round trip to learn nothing. The
        # in-memory double already answered `[]` for both; this is the contract,
        # now pinned in tests/contract.
        if limit <= 0:
            return []
        recent = (
            select(t.mapping_proposal_message)
            .where(t.mapping_proposal_message.c.mapping_proposal_id == proposal_id)
            .order_by(t.mapping_proposal_message.c.turn_index.desc())
            .limit(limit)
            .subquery()
        )
        rows = (await self._conn.execute(select(recent).order_by(recent.c.turn_index))).mappings()
        return [
            {
                "turn_index": int(row["turn_index"]),
                "role": str(row["role"]),
                "content": str(row["content"]),
            }
            for row in rows
        ]


def _validation_document(mapping: Mapping) -> dict[str, Any]:
    from agentlen.domain.services.mapping_validator import validate

    errors = validate(mapping)
    return {
        "valid": not errors,
        "errors": [
            {"code": error.code, "field_path": error.field_path, "message": error.message}
            for error in errors
        ],
    }


def _to_mapping_proposal(row: Any) -> MappingProposal:
    from agentlen.infrastructure.persistence.repositories.mapping_codec import document_to_mapping

    document = dict(row["document"])
    return MappingProposal(
        mapping=document_to_mapping(document, name=document["name"], version=1),
        rationale=tuple(row["rationale"] or ()),
        ambiguities=tuple(row["ambiguities"] or ()),
        unmapped_fields=tuple(row["unmapped_fields"] or ()),
        analyzer_descriptor={
            "provider": row["analyzer_provider"],
            "model": row["analyzer_model"],
            "prompt_version": row["prompt_version"],
        },
    )


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

    async def get_by_id(self, data_source_id: int) -> DataSourceRecord | None:
        row = (
            (
                await self._conn.execute(
                    select(t.data_source).where(t.data_source.c.id == data_source_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        return _to_data_source(row) if row else None

    async def list(self) -> list[DataSourceRecord]:
        rows = (
            (await self._conn.execute(select(t.data_source).order_by(t.data_source.c.name)))
            .mappings()
            .all()
        )
        return [_to_data_source(row) for row in rows]

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
        statement = (
            insert(t.data_source)
            .values(
                slug=slug,
                name=name,
                description=description,
                url=url,
                license=license,
                dataset_version=dataset_version,
                retrieved_at=retrieved_at,
            )
            .on_conflict_do_nothing(index_elements=[t.data_source.c.slug])
            .returning(t.data_source.c.id)
        )
        existing = (await self._conn.execute(statement)).scalar_one_or_none()
        if existing is not None:
            return int(existing)
        found = await self.get_by_slug(slug)
        assert found is not None
        return found


def _to_data_source(row: Any) -> DataSourceRecord:
    return DataSourceRecord(
        id=row["id"],
        slug=row["slug"],
        name=row["name"],
        description=row["description"],
        url=row["url"],
        license=row["license"],
        dataset_version=row["dataset_version"],
        retrieved_at=row["retrieved_at"],
        created_at=row["created_at"],
    )


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


class SqlAlchemyUserRepository(_Base):
    async def get_by_email(self, email: str) -> UserRecord | None:
        row = (
            (await self._conn.execute(select(t.user).where(t.user.c.email == email)))
            .mappings()
            .one_or_none()
        )
        return _to_user(row) if row else None

    async def get_by_id(self, user_id: int) -> UserRecord | None:
        row = (
            (await self._conn.execute(select(t.user).where(t.user.c.id == user_id)))
            .mappings()
            .one_or_none()
        )
        return _to_user(row) if row else None

    async def create(self, *, email: str, password_hash: str) -> UserRecord:
        statement = (
            insert(t.user).values(email=email, password_hash=password_hash).returning(t.user)
        )
        try:
            row = (await self._conn.execute(statement)).mappings().one()
        except IntegrityError as exc:
            # Defense in depth: the use case already checks get_by_email
            # first, this only fires on a genuine race between two concurrent
            # registrations for the same address. The message does not echo
            # the address (same wording as RegisterUser).
            raise ConflictError(
                "Impossible de créer un compte avec cette adresse e-mail. "
                "Si elle vous appartient, connectez-vous."
            ) from exc
        return _to_user(row)


def _to_user(row: Any) -> UserRecord:
    return UserRecord(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


class SqlAlchemyUserSessionRepository(_Base):
    async def create(
        self, *, user_id: int, token_hash: str, expires_at: datetime | None
    ) -> UserSessionRecord:
        statement = (
            insert(t.user_session)
            .values(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
            .returning(t.user_session)
        )
        row = (await self._conn.execute(statement)).mappings().one()
        return _to_user_session(row)

    async def get_active_by_token_hash(
        self, token_hash: str, *, now: datetime
    ) -> UserSessionRecord | None:
        c = t.user_session.c
        query = select(t.user_session).where(
            c.token_hash == token_hash, or_(c.expires_at.is_(None), c.expires_at > now)
        )
        row = (await self._conn.execute(query)).mappings().one_or_none()
        return _to_user_session(row) if row else None

    async def delete_by_token_hash(self, token_hash: str) -> None:
        await self._conn.execute(
            delete(t.user_session).where(t.user_session.c.token_hash == token_hash)
        )

    async def delete_expired(self, *, now: datetime) -> int:
        result = await self._conn.execute(
            delete(t.user_session).where(t.user_session.c.expires_at <= now)
        )
        return result.rowcount


def _to_user_session(row: Any) -> UserSessionRecord:
    return UserSessionRecord(
        token_hash=row["token_hash"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )
