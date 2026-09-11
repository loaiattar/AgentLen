"""Show what a mapping would produce, without producing it.

API.md §9.6 makes previewing the step before every import, and `AGENT.md` §5
exposes the same capability to the AI agent as the `preview_import` tool. So
this use case has two callers with the same requirement: tell me what would
happen, change nothing.

**Nothing is written. Not one row.** No `import_run`, no `raw_record`, not even
a referential upsert — resolving `tool = "Bash"` to an id would create a `tool`
row, and a dry-run that leaves rows behind is not a dry-run. Referential names
are reported as they appear in the data instead.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from agentlen.application.dto.preview import PreviewEntities, PreviewIssue, PreviewResult
from agentlen.application.errors import MappingInvalidError, NotFoundError
from agentlen.application.ports.file_reader import FileReader
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.application.use_cases.run_import import split_source_items
from agentlen.domain.services import mapping_validator
from agentlen.domain.services.record_normalizer import RecordNormalizer

DEFAULT_SAMPLE_SIZE = 20

#: The preview reads this many records from the file, so it is a work bound,
#: not a display one. Left open, `sample_size: 9999999` made the server read a
#: whole trace file to render five rows per entity. 500 matches
#: `PROFILE_SAMPLE_SIZE`, the budget already accepted for profiling the same
#: file, and is far above what judging a mapping needs.
MAX_SAMPLE_SIZE = 500

#: How many transformed rows to show per entity. Enough to judge a mapping,
#: few enough that the response stays readable.
_ROWS_SHOWN = 5


class PreviewImport:
    def __init__(
        self,
        uow: UnitOfWork,
        reader: FileReader,
        normalizer: RecordNormalizer | None = None,
    ) -> None:
        self._uow = uow
        self._reader = reader
        self._normalizer = normalizer or RecordNormalizer()

    async def execute(
        self, *, file_id: int, mapping_id: int, sample_size: int = DEFAULT_SAMPLE_SIZE
    ) -> PreviewResult:
        if sample_size < 1:
            raise ValueError("sample_size must be at least 1")
        if sample_size > MAX_SAMPLE_SIZE:
            raise ValueError(f"sample_size must not exceed {MAX_SAMPLE_SIZE}")

        # Reads only. The block is left without commit, so even the lookups
        # roll back — there is no path from here to a write.
        async with self._uow as uow:
            mapping = await uow.mappings.get(mapping_id)
            if mapping is None:
                raise NotFoundError("Mapping", mapping_id)
            stored_file = await uow.file_uploads.get_by_id(file_id)
            if stored_file is None:
                raise NotFoundError("File", file_id)
            storage_path, file_format = stored_file.storage_path, stored_file.format

        # Validated before a single record is read: an invalid mapping cannot
        # produce a meaningful preview, and the user needs every error at once.
        errors = mapping_validator.validate(mapping)
        if errors:
            raise MappingInvalidError(
                [{"code": e.code, "field_path": e.field_path, "message": e.message} for e in errors]
            )

        # Reading the file is blocking IO and parsing: done in a worker thread,
        # so a preview does not hold up every other request on the event loop.
        records = await asyncio.to_thread(
            self._reader.read_records, storage_path, limit=sample_size, format=file_format
        )

        would_import: dict[str, int] = defaultdict(int)
        rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        # Lines that cannot be read or stored: rejected here as at import.
        readable, rejections = split_source_items(records, start_line=1)
        issues = [
            PreviewIssue(r.line_number, r.severity, r.code, r.message, r.field_path)
            for r in rejections
        ]
        rejected_lines = {r.line_number for r in rejections if r.line_number is not None}

        for line_number, record in readable:
            result = self._normalizer.normalize(
                mapping,
                record,
                # A preview is not attached to a source yet; 0 is a sentinel
                # that never reaches storage because nothing is stored.
                data_source_id=0,
                line_number=line_number,
            )

            for target, entities in (
                ("session", result.sessions),
                ("model_call", result.model_calls),
                ("tool_call", result.tool_calls),
            ):
                would_import[target] += len(entities)
                for entity in entities:
                    if len(rows[target]) < _ROWS_SHOWN:
                        rows[target].append(_summarise(entity))

            for issue in result.issues:
                issues.append(
                    PreviewIssue(
                        line_number=issue.line_number or line_number,
                        severity=issue.severity,
                        code=issue.code,
                        message=issue.message,
                        field_path=issue.field_path,
                    )
                )
                if issue.severity == "rejected":
                    rejected_lines.add(issue.line_number or line_number)

        issues.sort(key=lambda issue: issue.line_number or 0)
        return PreviewResult(
            sampled=len(records),
            would_import=dict(would_import),
            # Counted per source line, not per issue: one bad line producing
            # three issues is one rejected record, not three.
            would_reject=len(rejected_lines),
            entities=[PreviewEntities(target=target, rows=shown) for target, shown in rows.items()],
            issues=issues,
        )


def _summarise(entity: Any) -> dict[str, Any]:
    """A displayable row: public scalar fields, no internal correlation id."""
    from dataclasses import fields, is_dataclass

    if not is_dataclass(entity):  # pragma: no cover - entities are dataclasses
        return {}
    out: dict[str, Any] = {}
    for f in fields(entity):
        if f.name in {"id", "session_id", "model_call_id"}:
            continue
        value = getattr(entity, f.name)
        if is_dataclass(value):
            # TokenUsage and friends: flattened, so the preview shows the
            # fields a user recognises rather than a nested object.
            out.update(_summarise(value))
        elif hasattr(value, "isoformat"):
            out[f.name] = value.isoformat()
        else:
            out[f.name] = value
    return out
