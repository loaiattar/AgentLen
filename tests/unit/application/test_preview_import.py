"""Previewing an import: everything reported, nothing written."""

from __future__ import annotations

import threading
from typing import Any
from uuid import uuid4

import pytest

from agentlen.application.errors import MappingInvalidError, NotFoundError
from agentlen.application.use_cases.preview_import import MAX_SAMPLE_SIZE, PreviewImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from tests.fakes.file_reader import InMemoryFileReader
from tests.fakes.repositories import InMemoryUnitOfWork

PATH = "memory://sample"

RECORDS = [
    {"sid": "a", "tools": [{"name": "Bash"}, {"name": "Read"}]},
    {"sid": "b", "tools": [{"name": "Write"}]},
    {"tools": [{"name": "Bash"}]},  # no sid: the session is rejected
]


def valid_mapping() -> Mapping:
    return Mapping(
        id=uuid4(),
        name="m",
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
                fields=(FieldRule(target="tool_name", source="$.name", required=True),),
            ),
        ),
    )


def invalid_mapping() -> Mapping:
    return Mapping(
        id=uuid4(),
        name="m",
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(
                    FieldRule(
                        target="external_id", source="$.sid", operators=({"op": "eval_python"},)
                    ),
                    FieldRule(target="user_email", source="$.mail"),
                ),
            ),
        ),
    )


async def build(mapping: Mapping, records: list[dict[str, Any]] | None = None):  # type: ignore[no-untyped-def]
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        mapping_id = await uow.mappings.save(mapping, data_source_id=source)
        record = await uow.file_uploads.create(
            original_name="s.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        await uow.commit()
    reader = InMemoryFileReader({PATH: records if records is not None else RECORDS})
    return PreviewImport(uow, reader), uow, reader, record.id, mapping_id


# ---------------------------------------------------------------------------
# Nothing is written — the property the feature exists for
# ---------------------------------------------------------------------------


async def test_a_preview_writes_absolutely_nothing() -> None:
    preview, uow, _, file_id, mapping_id = await build(valid_mapping())

    async with uow:
        before = (
            await uow.sessions.count(),
            len(uow._store.raw_records),
            len(uow._store.import_runs),
            len(uow._store.referentials),
        )

    await preview.execute(file_id=file_id, mapping_id=mapping_id)

    async with uow:
        after = (
            await uow.sessions.count(),
            len(uow._store.raw_records),
            len(uow._store.import_runs),
            len(uow._store.referentials),
        )
    assert before == after


async def test_referential_names_are_not_upserted() -> None:
    """Resolving `tool = "Bash"` to an id would create a `tool` row. A dry-run
    that leaves rows behind is not a dry-run."""
    preview, uow, _, file_id, mapping_id = await build(valid_mapping())

    await preview.execute(file_id=file_id, mapping_id=mapping_id)

    async with uow:
        assert uow._store.referentials == {}


# ---------------------------------------------------------------------------
# What it reports
# ---------------------------------------------------------------------------


async def test_would_import_counts_the_entities_the_normaliser_produced() -> None:
    preview, _, _, file_id, mapping_id = await build(valid_mapping())

    result = await preview.execute(file_id=file_id, mapping_id=mapping_id)

    assert result.sampled == 3
    assert result.would_import["session"] == 2  # third record has no sid
    assert result.would_import["tool_call"] == 3  # 2 + 1, the third is orphaned


async def test_a_bad_line_is_reported_with_its_line_number_and_field_path() -> None:
    preview, _, _, file_id, mapping_id = await build(valid_mapping())

    result = await preview.execute(file_id=file_id, mapping_id=mapping_id)

    rejected = [i for i in result.issues if i.severity == "rejected"]
    assert rejected, "a record without sid should have been rejected"
    assert rejected[0].line_number == 3
    assert rejected[0].field_path is not None
    assert rejected[0].code


async def test_one_bad_line_counts_as_one_rejection_not_one_per_issue() -> None:
    """A record producing three issues is one rejected record."""
    preview, _, _, file_id, mapping_id = await build(valid_mapping())

    result = await preview.execute(file_id=file_id, mapping_id=mapping_id)

    assert result.would_reject == 1


async def test_sample_rows_are_shown_without_internal_identifiers() -> None:
    preview, _, _, file_id, mapping_id = await build(valid_mapping())

    result = await preview.execute(file_id=file_id, mapping_id=mapping_id)

    sessions = next(e for e in result.entities if e.target == "session")
    assert sessions.rows
    assert "external_id" in sessions.rows[0]
    # The in-batch correlation UUID means nothing to a reader.
    assert "id" not in sessions.rows[0]


async def test_the_limit_is_pushed_down_to_the_reader() -> None:
    """Reading a 500 MB file to preview twenty rows would make the feature
    unusable on the files that need it most."""
    preview, _, reader, file_id, mapping_id = await build(valid_mapping())

    await preview.execute(file_id=file_id, mapping_id=mapping_id, sample_size=2)

    assert reader.last_limit == 2


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


async def test_an_invalid_mapping_reports_every_error_and_reads_nothing() -> None:
    preview, _, reader, file_id, mapping_id = await build(invalid_mapping())

    with pytest.raises(MappingInvalidError) as exc:
        await preview.execute(file_id=file_id, mapping_id=mapping_id)

    assert exc.value.code == "MAPPING_INVALID"
    assert len(exc.value.errors) >= 2  # unknown operator AND unknown target
    for error in exc.value.errors:
        assert error["code"] and error["field_path"]
    # Validation happens before any record is read.
    assert reader.last_limit is None


async def test_an_unknown_mapping_is_a_not_found() -> None:
    preview, _, _, file_id, _ = await build(valid_mapping())

    with pytest.raises(NotFoundError):
        await preview.execute(file_id=file_id, mapping_id=99999)


async def test_an_unknown_file_is_a_not_found() -> None:
    preview, _, _, _, mapping_id = await build(valid_mapping())

    with pytest.raises(NotFoundError):
        await preview.execute(file_id=99999, mapping_id=mapping_id)


async def test_a_nonsense_sample_size_is_refused() -> None:
    preview, _, _, file_id, mapping_id = await build(valid_mapping())

    with pytest.raises(ValueError):
        await preview.execute(file_id=file_id, mapping_id=mapping_id, sample_size=0)


async def test_an_unbounded_sample_size_is_refused() -> None:
    """`sample_size` is how many records the server reads, not how many it shows.

    Left open, one request could ask the server to read a whole trace file to
    render five rows per entity.
    """
    preview, _, reader, file_id, mapping_id = await build(valid_mapping())

    with pytest.raises(ValueError):
        await preview.execute(
            file_id=file_id, mapping_id=mapping_id, sample_size=MAX_SAMPLE_SIZE + 1
        )
    assert reader.last_limit is None, "nothing should have been read"


async def test_the_sample_size_ceiling_itself_is_accepted() -> None:
    preview, _, reader, file_id, mapping_id = await build(valid_mapping())

    await preview.execute(file_id=file_id, mapping_id=mapping_id, sample_size=MAX_SAMPLE_SIZE)

    assert reader.last_limit == MAX_SAMPLE_SIZE


async def test_the_file_is_read_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading and parsing a file blocks: on the event loop, a preview would
    hold up every other request until it finished."""
    preview, _, reader, file_id, mapping_id = await build(valid_mapping())
    loop_thread = threading.get_ident()
    reading_threads: list[int] = []
    read_records = reader.read_records

    def spy(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        reading_threads.append(threading.get_ident())
        return read_records(*args, **kwargs)

    monkeypatch.setattr(reader, "read_records", spy)

    result = await preview.execute(file_id=file_id, mapping_id=mapping_id)

    assert result.sampled == len(RECORDS)
    assert reading_threads and loop_thread not in reading_threads
