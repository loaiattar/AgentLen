"""An import that stops says where it stopped, never on what (#189, #153)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest

from agentlen.application.errors import ImportInterruptedError
from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.record_normalizer import RecordNormalizer
from tests.fakes import repositories
from tests.fakes.file_reader import InMemoryFileReader
from tests.fakes.repositories import InMemoryUnitOfWork

PATH = "memory://run"
RECORDS = [{"sid": "a"}, {"sid": "b"}, {"sid": "c"}]
MAPPING = Mapping(
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
    ),
)


@pytest.fixture(autouse=True)
def _batches_of_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMPORT_BATCH_SIZE", "2")


async def _interrupted(
    reader: InMemoryFileReader, normalizer: RecordNormalizer | None = None
) -> ImportInterruptedError:
    uow = InMemoryUnitOfWork()
    async with uow:
        source = await uow.data_sources.create(slug="m", name="M")
        mapping_id = await uow.mappings.save(MAPPING, data_source_id=source)
        stored = await uow.file_uploads.create(
            original_name="f.jsonl",
            storage_path=PATH,
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        run_id = await uow.import_runs.create(
            data_source_id=source, file_upload_id=stored.id, mapping_id=mapping_id
        )
        await uow.commit()
    with pytest.raises(ImportInterruptedError) as caught:
        await RunImport(uow, reader, normalizer).execute(run_id)
    assert "TRACE" not in str(caught.value)
    return caught.value


async def test_a_record_that_breaks_the_normalizer_names_its_own_line() -> None:
    class Breaks(RecordNormalizer):
        def normalize(self, mapping: Mapping, raw: dict[str, Any], **kwargs: Any) -> Any:
            if raw["sid"] == "c":
                raise KeyError("TRACE-CONTENT")
            return super().normalize(mapping, raw, **kwargs)

    error = await _interrupted(InMemoryFileReader({PATH: RECORDS}), Breaks())

    assert (error.first_line, error.last_line) == (3, 3)
    assert isinstance(error.__cause__, KeyError)


async def test_a_failing_batch_names_its_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fails(self: Any, rows: Any) -> Any:
        raise RuntimeError("TRACE-CONTENT")

    monkeypatch.setattr(repositories.InMemorySessionRepository, "add_many", fails)

    error = await _interrupted(InMemoryFileReader({PATH: RECORDS}))

    assert (error.first_line, error.last_line) == (1, 2)


async def test_a_failing_read_names_the_line_it_stopped_before() -> None:
    class Breaks(InMemoryFileReader):
        def iter_batches(
            self, path: str, *, batch_size: int, format: str | None = None
        ) -> Iterator[Any]:
            yield from super().iter_batches(path, batch_size=batch_size, format=format)
            raise OSError("TRACE-CONTENT")

    error = await _interrupted(Breaks({PATH: RECORDS}))

    assert (error.first_line, error.last_line) == (4, None)
