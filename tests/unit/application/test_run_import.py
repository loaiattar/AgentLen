"""RunImport on the in-memory unit of work: how referential names are resolved (#141)."""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import uuid4

from agentlen.application.use_cases.preview_import import PreviewImport
from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.record_normalizer import NormalizationResult, RecordNormalizer
from tests.fakes.file_reader import InMemoryFileReader
from tests.fakes.repositories import InMemoryUnitOfWork

PATH = "memory://traces"
PARENT = {"entity": "session", "via": "external_id"}
MAPPING = Mapping(
    id=uuid4(),
    name="names",
    version=1,
    source_format="jsonl",
    entities=(
        EntityMapping(
            target="session",
            natural_key=("external_id",),
            fields=(
                FieldRule(target="external_id", source="$.sid", required=True),
                FieldRule(target="agent_name", source="$.agent"),
            ),
        ),
        EntityMapping(
            target="model_call",
            natural_key=("sequence_index",),
            iterate="$.calls",
            parent=PARENT,
            fields=(
                FieldRule(target="model_name", source="$.model"),
                FieldRule(target="provider_name", source="$.provider"),
            ),
        ),
        EntityMapping(
            target="tool_call",
            natural_key=("sequence_index",),
            iterate="$.tools",
            parent=PARENT,
            fields=(FieldRule(target="tool_name", source="$.name", required=True),),
        ),
    ),
)
RECORD = {
    "sid": "s1",
    "agent": "claude-code",
    "calls": [{"model": "opus"}],
    "tools": [{"name": "Bash"}],
}


class _NormalizerThatAsksForNothing(RecordNormalizer):
    """Stands in for any drift between the names the normaliser asks to resolve
    and the names the import then looks up."""

    def normalize(self, *args: Any, **kwargs: Any) -> NormalizationResult:
        return dataclasses.replace(super().normalize(*args, **kwargs), reference_requests=())


async def _prepare(records: list[dict[str, Any]]) -> tuple[InMemoryUnitOfWork, dict[str, Any]]:
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        mapping_id = await uow.mappings.save(MAPPING, data_source_id=source)
        upload = await uow.file_uploads.create(
            original_name="t.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        run_id = await uow.import_runs.create(
            data_source_id=source, file_upload_id=upload.id, mapping_id=mapping_id
        )
        await uow.commit()
    reader = InMemoryFileReader({PATH: records})
    return uow, {"run": run_id, "file": upload.id, "mapping": mapping_id, "reader": reader}


async def test_an_unresolved_reference_is_reported_and_the_rest_of_the_record_imports() -> None:
    uow, ids = await _prepare([RECORD])

    report = await RunImport(uow, ids["reader"], _NormalizerThatAsksForNothing()).execute(
        ids["run"]
    )

    unresolved = {
        (issue.field_path, issue.severity, issue.line_number)
        for issue in report.issues
        if issue.code == "REFERENCE_UNRESOLVED"
    }
    assert unresolved == {
        ("entities[target=session].fields[target=agent_name]", "warning", 1),
        ("entities[target=model_call].fields[target=model_name]", "warning", 1),
        ("entities[target=tool_call].fields[target=tool_name]", "rejected", 1),
    }
    assert report.records_rejected == 1
    assert uow._store.tool_calls == []  # a tool call cannot be stored without its tool
    ((_, session_row),) = uow._store.sessions.values()
    ((_, model_row),) = uow._store.model_calls
    assert (session_row.agent_id, model_row.model_id) == (None, None)


async def test_a_provider_name_with_separators_keeps_its_model_attached() -> None:
    """The cache key used to be `"provider_name=a;b=c"` re-split on `;` and `=`,
    which attached the model to a provider called `a`."""
    uow, ids = await _prepare([{**RECORD, "calls": [{"model": "opus", "provider": "a;b=c"}]}])

    await RunImport(uow, ids["reader"]).execute(ids["run"])

    ((_, model_row),) = uow._store.model_calls
    async with uow:
        right = await uow.referentials.resolve("model", "opus", context={"provider_name": "a;b=c"})
        wrong = await uow.referentials.resolve("model", "opus", context={"provider_name": "a"})
    assert model_row.model_id == right != wrong


async def test_preview_and_import_count_the_same_rows() -> None:
    uow, ids = await _prepare(
        [
            {"sid": "s1", "agent": 42, "calls": [{"model": 7}], "tools": [{"name": 123}]},
            {"sid": "s2", "tools": [{"name": ""}, {"name": "   "}]},  # blank names, reported
            {"tools": [{"name": "Read"}]},  # no session
        ]
    )

    preview = await PreviewImport(uow, ids["reader"]).execute(
        file_id=ids["file"], mapping_id=ids["mapping"]
    )
    report = await RunImport(uow, ids["reader"]).execute(ids["run"])

    assert report.records_imported == sum(preview.would_import.values()) == 4
    assert report.records_rejected == preview.would_reject == 2
    blank = [issue.line_number for issue in report.issues if issue.code == "REFERENCE_NAME_INVALID"]
    assert blank == [2, 2]
