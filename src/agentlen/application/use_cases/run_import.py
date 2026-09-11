"""Read a file, transform it, and write the result — with a full account of it.

The governing rule is that **a bad batch does not stop the import**. The point
is a complete, explained report, not a halt on the first awkward line. A file
where three rows in a hundred are malformed should import ninety-seven and say
precisely what happened to the other three (MAPPING_CONTRACT.md §7.4).

Records are processed in batches, and each batch is one transaction. That is a
deliberate middle ground:

- one transaction for the whole file would hold a write lock for minutes and
  lose everything on the last row;
- one transaction per record would be correct and unusably slow.

A batch is small enough to be cheap to retry and large enough that the round
trips disappear.

The report's counters are saved in each batch's transaction too, so what
`import_run` shows is always what was committed: a run that fails at batch N
keeps the counters of batches 1 to N-1 (DATA_MODEL.md §6). The end of the run
only adds its status and finish time.
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from agentlen.application.dto.persistence import ModelCallRow, SessionRow, ToolCallRow
from agentlen.application.errors import MappingInvalidError, NotFoundError
from agentlen.application.ports.file_reader import FileReader
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.model.import_run import ImportIssue, ImportReport
from agentlen.domain.services import mapping_validator
from agentlen.domain.services.record_normalizer import RecordNormalizer

DEFAULT_BATCH_SIZE = 500


def batch_size() -> int:
    return int(os.environ.get("IMPORT_BATCH_SIZE", DEFAULT_BATCH_SIZE))


class _Counters:
    """Running totals for the report, plus the missing-field tally."""

    def __init__(self) -> None:
        self.read = 0
        self.imported = 0
        self.duplicate = 0
        self.rejected = 0
        self.fields_missing: dict[str, int] = defaultdict(int)
        # A session already stored by a previous import is one duplicate for the
        # whole run, however many batches refer to it.
        self.duplicate_sessions: set[int] = set()

    def note_missing(self, target: str, entity: Any) -> None:
        """Count fields the source did not provide.

        Feeds `fields_missing`, which drives the data-quality view. A field that
        is absent everywhere is a mapping problem worth surfacing, not a
        silently empty column.
        """
        from dataclasses import fields, is_dataclass

        if not is_dataclass(entity):
            return
        for f in fields(entity):
            value = getattr(entity, f.name)
            if is_dataclass(value):
                self.note_missing(target, value)
            elif value is None:
                self.fields_missing[f"{target}.{f.name}"] += 1

    def to_report(self, issues: list[ImportIssue]) -> ImportReport:
        return ImportReport(
            records_read=self.read,
            records_imported=self.imported,
            records_duplicate=self.duplicate,
            records_rejected=self.rejected,
            issues=tuple(issues),
            fields_missing=dict(self.fields_missing),
        )

    @property
    def status(self) -> str:
        # `partial` as soon as anything was rejected: a run that silently
        # dropped rows must not read as a clean success.
        return "partial" if self.rejected else "succeeded"


@dataclass(frozen=True)
class _RunContext:
    """What stays fixed for the whole run.

    Grouped rather than threaded through as separate parameters: these three
    are constant from the first batch to the last, and passing them individually
    invited getting the order wrong.
    """

    mapping: Any
    data_source_id: int
    import_run_id: int


class RunImport:
    def __init__(
        self,
        uow: UnitOfWork,
        reader: FileReader,
        normalizer: RecordNormalizer | None = None,
    ) -> None:
        self._uow = uow
        self._reader = reader
        self._normalizer = normalizer or RecordNormalizer()

    async def execute(self, import_run_id: int) -> ImportReport:
        async with self._uow as uow:
            run = await uow.import_runs.get(import_run_id)
            if run is None:
                raise NotFoundError("ImportRun", import_run_id)
            mapping = await uow.mappings.get(run["mapping_id"])
            if mapping is None:
                raise NotFoundError("Mapping", run["mapping_id"])
            stored = await uow.file_uploads.get_by_id(run["file_upload_id"])
            if stored is None:
                raise NotFoundError("File", run["file_upload_id"])

        errors = mapping_validator.validate(mapping)
        if errors:
            raise MappingInvalidError(
                [{"code": e.code, "field_path": e.field_path, "message": e.message} for e in errors]
            )

        counters = _Counters()
        all_issues: list[ImportIssue] = []
        # Referential ids are cached for the whole run: the same tool name
        # appears on most records, and resolving it once per row would be one
        # round trip per row.
        reference_cache: dict[tuple[str, str, str], int] = {}
        line_number = 0

        for batch in self._reader.iter_batches(
            stored.storage_path, batch_size=batch_size(), format=stored.format
        ):
            start_line = line_number + 1
            line_number += len(batch)
            batch_issues = await self._import_batch(
                batch,
                start_line=start_line,
                context=_RunContext(
                    mapping=mapping,
                    data_source_id=run["data_source_id"],
                    import_run_id=import_run_id,
                ),
                counters=counters,
                reference_cache=reference_cache,
            )
            all_issues.extend(batch_issues)

        report = counters.to_report(all_issues)
        async with self._uow as uow:
            await uow.import_runs.save_report(import_run_id, report, status=counters.status)
            await uow.commit()
        return report

    async def _import_batch(
        self,
        batch: list[dict[str, Any]],
        *,
        start_line: int,
        context: _RunContext,
        counters: _Counters,
        reference_cache: dict[tuple[str, str, str], int],
    ) -> list[ImportIssue]:
        counters.read += len(batch)
        issues: list[ImportIssue] = []

        async with self._uow as uow:
            raw_ids = await uow.raw_records.add_many(
                import_run_id=context.import_run_id,
                records=[(start_line + i, record) for i, record in enumerate(batch)],
            )

            sessions: list[SessionRow] = []
            model_calls: list[tuple[ModelCallRow, str | None]] = []
            tool_calls: list[tuple[ToolCallRow, str]] = []
            pending_references: set[tuple[str, str, str]] = set()
            normalised: list[Any] = []

            for offset, record in enumerate(batch):
                line = start_line + offset
                result = self._normalizer.normalize(
                    context.mapping,
                    record,
                    data_source_id=context.data_source_id,
                    line_number=line,
                )
                normalised.append((line, result))
                issues.extend(result.issues)
                for request in result.reference_requests:
                    pending_references.add((request.kind, request.name, _context_key(request)))

            resolved = await self._resolve(uow, pending_references, reference_cache)

            for line, result in normalised:
                raw_id = raw_ids.get(line)
                if raw_id is None:
                    # Line already stored by a previous attempt of this run.
                    continue
                for session in result.sessions:
                    sessions.append(
                        SessionRow(
                            entity=session,
                            import_run_id=context.import_run_id,
                            raw_record_id=raw_id,
                            agent_id=resolved.get(("agent", session.agent_name or "", "")),
                        )
                    )
                    counters.note_missing("session", session)
                for call in result.model_calls:
                    model_calls.append(
                        (
                            ModelCallRow(
                                entity=call,
                                raw_record_id=raw_id,
                                model_id=resolved.get(
                                    ("model", call.model_name or "", _model_key(call))
                                ),
                            ),
                            None,
                        )
                    )
                    counters.note_missing("model_call", call)
                for call in result.tool_calls:
                    tool_id = resolved.get(("tool", call.tool_name, ""))
                    if tool_id is None:
                        continue
                    tool_calls.append(
                        (
                            ToolCallRow(entity=call, raw_record_id=raw_id, tool_id=tool_id),
                            call.tool_name,
                        )
                    )
                    counters.note_missing("tool_call", call)

            session_outcome = await uow.sessions.add_many(sessions)
            # `ids`, not `assigned`: a session stored by an earlier batch or an
            # earlier import still owns the calls this batch brings (#123).
            model_outcome = await uow.model_calls.add_many(
                [row for row, _ in model_calls], session_ids=session_outcome.ids
            )
            tool_outcome = await uow.tool_calls.add_many(
                [row for row, _ in tool_calls],
                session_ids=session_outcome.ids,
                model_call_ids=model_outcome.ids,
            )

            counters.imported += (
                session_outcome.inserted_count
                + model_outcome.inserted_count
                + tool_outcome.inserted_count
            )
            new_duplicate_sessions = {
                session_outcome.existing[entity_id] for entity_id in session_outcome.duplicates
            } - counters.duplicate_sessions
            counters.duplicate_sessions |= new_duplicate_sessions
            duplicates = (
                len(new_duplicate_sessions)
                + model_outcome.duplicate_count
                + tool_outcome.duplicate_count
            )
            counters.duplicate += duplicates
            if duplicates:
                issues.append(
                    ImportIssue(
                        severity="duplicate",
                        code="ALREADY_IMPORTED",
                        message=(
                            f"{duplicates} enregistrement(s) déjà présent(s), "
                            "reconnus par leur clé naturelle."
                        ),
                    )
                )

            unlinked = len(model_outcome.unlinked) + len(tool_outcome.unlinked)
            if unlinked:
                issues.append(
                    ImportIssue(
                        severity="warning",
                        code="PARENT_SESSION_MISSING",
                        message=(
                            f"{unlinked} appel(s) non enregistré(s) : "
                            "leur session n'a pas pu être rattachée."
                        ),
                    )
                )

            rejected_lines = {issue.line_number for issue in issues if issue.severity == "rejected"}
            counters.rejected += len(rejected_lines - {None})

            await uow.import_issues.add_many(
                import_run_id=context.import_run_id,
                issues=[(issue, raw_ids.get(issue.line_number or -1)) for issue in issues],
            )
            # Same transaction as the batch: a later failure keeps these counters,
            # a failure of this batch rolls them back with its rows.
            await uow.import_runs.save_progress(context.import_run_id, counters.to_report([]))
            await uow.commit()

        return issues

    async def _resolve(
        self,
        uow: UnitOfWork,
        requests: set[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], int],
    ) -> dict[tuple[str, str, str], int]:
        for key in requests:
            if key in cache:
                continue
            kind, name, marker = key
            if not name:
                continue
            context = dict(part.split("=", 1) for part in marker.split(";") if "=" in part)
            cache[key] = await uow.referentials.resolve(kind, name, context=context or None)
        return cache


def _context_key(request: Any) -> str:
    context = dict(getattr(request, "context", ()) or ())
    return ";".join(f"{k}={v}" for k, v in sorted(context.items()))


def _model_key(call: Any) -> str:
    provider = getattr(call, "provider_name", None)
    return f"provider_name={provider}" if provider else ""
