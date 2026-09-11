"""RunImport on the in-memory unit of work.

How referential names are resolved (#141), and the call keys of a session
spread over several lines (#188).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest

from agentlen.application.use_cases.preview_import import PreviewImport
from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.import_run import ImportReport
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

COLLISION = ("SEQUENCE_INDEX_COLLISION", "entities[target=tool_call].fields[target=sequence_index]")

# TraceLab's shape: one round per line, the session repeated, and a tool index
# that starts again at 0 on every round.
ROUNDS = [
    {"sid": "s1", "tools": [{"name": "Bash", "i": 0}, {"name": "Read", "i": 1}]} for _ in range(3)
]


def _rounds_mapping(*tool_fields: FieldRule) -> Mapping:
    return Mapping(
        id=uuid4(),
        name="rounds",
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(FieldRule(target="external_id", source="$.sid", required=True),),
            ),
            EntityMapping(
                target="tool_call",
                natural_key=("sequence_index",),
                iterate="$.tools",
                parent=PARENT,
                fields=(
                    FieldRule(target="tool_name", source="$.name", required=True),
                    *tool_fields,
                ),
            ),
        ),
    )


class _NormalizerThatAsksForNothing(RecordNormalizer):
    """Stands in for any drift between the names the normaliser asks to resolve
    and the names the import then looks up."""

    def normalize(self, *args: Any, **kwargs: Any) -> NormalizationResult:
        return dataclasses.replace(super().normalize(*args, **kwargs), reference_requests=())


async def _seed(mapping: Mapping) -> tuple[InMemoryUnitOfWork, dict[str, Any]]:
    """A unit of work holding a data source, `mapping` and a file stored at PATH."""
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        mapping_id = await uow.mappings.save(mapping, data_source_id=source)
        upload = await uow.file_uploads.create(
            original_name="t.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        await uow.commit()
    return uow, {"source": source, "file": upload.id, "mapping": mapping_id}


async def _new_run(uow: InMemoryUnitOfWork, ids: dict[str, Any]) -> int:
    async with uow:
        run_id = await uow.import_runs.create(
            data_source_id=ids["source"], file_upload_id=ids["file"], mapping_id=ids["mapping"]
        )
        await uow.commit()
    return run_id


async def _prepare(records: list[dict[str, Any]]) -> tuple[InMemoryUnitOfWork, dict[str, Any]]:
    uow, ids = await _seed(MAPPING)
    ids["run"] = await _new_run(uow, ids)
    ids["reader"] = InMemoryFileReader({PATH: records})
    return uow, ids


async def _importer(
    mapping: Mapping,
) -> tuple[Callable[[], Awaitable[ImportReport]], InMemoryUnitOfWork]:
    """Imports ROUNDS with `mapping`, as a new run on every call."""
    uow, ids = await _seed(mapping)

    async def run() -> ImportReport:
        run_id = await _new_run(uow, ids)
        return await RunImport(uow, InMemoryFileReader({PATH: ROUNDS})).execute(run_id)

    return run, uow


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


async def test_unmapped_index_keeps_every_call_of_a_split_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "2")
    run, uow = await _importer(_rounds_mapping())

    first = await run()
    second = await run()

    assert len(uow._store.tool_calls) == 6
    assert (first.records_imported, first.records_duplicate, first.records_rejected) == (7, 0, 0)
    assert (second.records_imported, second.records_duplicate, second.records_rejected) == (0, 7, 0)


@pytest.mark.parametrize("batch_size", ["500", "1"], ids=["same-batch", "later-batch"])
async def test_a_mapped_index_restarting_on_each_line_collides_instead_of_duplicating(
    monkeypatch: pytest.MonkeyPatch, batch_size: str
) -> None:
    monkeypatch.setenv("IMPORT_BATCH_SIZE", batch_size)
    run, uow = await _importer(_rounds_mapping(FieldRule(target="sequence_index", source="$.i")))

    first = await run()
    second = await run()

    assert len(uow._store.tool_calls) == 2
    # Lines 2 and 3 repeat the keys of line 1: rejected, each with its line.
    collisions = [(*COLLISION, line) for line in (2, 2, 3, 3)]
    assert [(i.code, i.field_path, i.line_number) for i in first.issues] == collisions
    assert (first.records_imported, first.records_duplicate, first.records_rejected) == (3, 0, 2)
    # A re-import meets line 1's rows again: those are duplicates, the rest still collide.
    assert (second.records_imported, second.records_duplicate, second.records_rejected) == (0, 3, 2)
    assert [
        (i.code, i.field_path, i.line_number)
        for i in second.issues
        if i.code == "SEQUENCE_INDEX_COLLISION"
    ] == collisions
