"""Call keys of a session spread over several lines, on the in-memory fakes (#188)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.import_run import ImportReport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from tests.fakes.file_reader import InMemoryFileReader
from tests.fakes.repositories import InMemoryUnitOfWork

PATH = "memory://rounds"
COLLISION = ("SEQUENCE_INDEX_COLLISION", "entities[target=tool_call].fields[target=sequence_index]")

# TraceLab's shape: one round per line, the session repeated, and a tool index
# that starts again at 0 on every round.
ROUNDS = [
    {"sid": "s1", "tools": [{"name": "Bash", "i": 0}, {"name": "Read", "i": 1}]} for _ in range(3)
]


def _mapping(*tool_fields: FieldRule) -> Mapping:
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
                parent={"entity": "session", "via": "external_id"},
                fields=(
                    FieldRule(target="tool_name", source="$.name", required=True),
                    *tool_fields,
                ),
            ),
        ),
    )


async def _importer(
    mapping: Mapping,
) -> tuple[Callable[[], Awaitable[ImportReport]], InMemoryUnitOfWork]:
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        mapping_id = await uow.mappings.save(mapping, data_source_id=source)
        stored = await uow.file_uploads.create(
            original_name="rounds.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        await uow.commit()

    async def run() -> ImportReport:
        async with uow:
            run_id = await uow.import_runs.create(
                data_source_id=source, file_upload_id=stored.id, mapping_id=mapping_id
            )
            await uow.commit()
        return await RunImport(uow, InMemoryFileReader({PATH: ROUNDS})).execute(run_id)

    return run, uow


async def test_unmapped_index_keeps_every_call_of_a_split_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "2")
    run, uow = await _importer(_mapping())

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
    run, uow = await _importer(_mapping(FieldRule(target="sequence_index", source="$.i")))

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
