from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from agentlen.application.dto.mapping_document import mapping_to_document
from agentlen.application.errors import ConflictError, MappingInvalidError
from agentlen.application.use_cases.propose_mapping import ProposeMapping
from agentlen.application.use_cases.refine_mapping import RefineMapping
from agentlen.application.use_cases.save_mapping import SaveMapping
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping, MappingProposal
from agentlen.domain.model.profile import FieldProfile, FileProfile
from agentlen.infrastructure.ai.fake_adapter import FakeAnalyzer
from agentlen.infrastructure.ai.sanitizer import ProfileExampleSanitizer
from tests.fakes.repositories import InMemoryUnitOfWork


def valid_mapping(*, name: str = "mapping", version: int = 1) -> Mapping:
    return Mapping(
        id=uuid4(),
        name=name,
        version=version,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(FieldRule(target="external_id", source="$.id"),),
            ),
        ),
    )


class FakeProfiler:
    async def profile(
        self,
        path: str,
        *,
        sample_size: int = 500,
        format: str | None = None,
    ) -> FileProfile:
        return FileProfile(
            file_id=0,
            format="jsonl",
            record_count=1,
            sampled_records=1,
            fields=(
                FieldProfile(
                    path="$.token",
                    types=("string",),
                    null_ratio=0,
                    examples=("API_KEY=super-secret-value-123",),
                ),
            ),
        )


class RecordingFakeAnalyzer(FakeAnalyzer):
    def __init__(self, proposal: MappingProposal | None = None) -> None:
        super().__init__()
        self.proposal = proposal
        self.profile_seen: FileProfile | None = None
        self.history_seen: tuple[dict[str, str | int], ...] = ()

    async def run_agent_loop(self, profile, tool_executor, hint=None):
        self.profile_seen = profile
        if self.proposal is not None:
            return self.proposal
        return await super().run_agent_loop(profile, tool_executor, hint)

    async def refine(self, proposal, user_message, tool_executor, history=()):
        self.history_seen = history
        return replace(proposal, mapping=replace(proposal.mapping, name="refined"))


async def stored_file(uow: InMemoryUnitOfWork) -> int:
    async with uow as transaction:
        record = await transaction.file_uploads.create(
            original_name="sample.jsonl",
            storage_path="stored/sample.jsonl",
            format="jsonl",
            size_bytes=1,
            content_hash="a" * 64,
        )
        await transaction.commit()
    return record.id


async def stored_data_source(uow: InMemoryUnitOfWork, slug: str = "mapping-tests") -> int:
    async with uow as transaction:
        source_id = await transaction.data_sources.create(slug=slug, name="Mapping tests")
        await transaction.commit()
    return source_id


async def test_fake_analyzer_profile_is_sanitized_and_descriptor_persisted() -> None:
    uow = InMemoryUnitOfWork()
    file_id = await stored_file(uow)
    analyzer = RecordingFakeAnalyzer()
    result = await ProposeMapping(uow, analyzer, FakeProfiler(), ProfileExampleSanitizer()).execute(
        file_id=file_id, data_source_id=None
    )

    assert result.validation["valid"] is True
    assert analyzer.profile_seen is not None
    assert analyzer.profile_seen.fields[0].examples == ("API_KEY=[REDACTED_SECRET]",)
    async with uow as transaction:
        persisted = await transaction.mapping_proposals.get(result.id)
    assert persisted is not None
    assert persisted.analyzer_descriptor == analyzer.descriptor
    source_id = await stored_data_source(uow)
    mapping_id = await SaveMapping(uow).execute(result.proposal.mapping, data_source_id=source_id)
    async with uow as transaction:
        assert await transaction.mappings.get(mapping_id) == result.proposal.mapping


async def test_invalid_proposal_is_returned_with_localized_errors() -> None:
    uow = InMemoryUnitOfWork()
    file_id = await stored_file(uow)
    invalid = valid_mapping()
    invalid = replace(
        invalid,
        entities=(
            replace(
                invalid.entities[0],
                fields=(FieldRule(target="not_a_field", source="$.id"),),
            ),
        ),
    )
    proposal = MappingProposal(
        mapping=invalid,
        rationale=(),
        ambiguities=(),
        unmapped_fields=(),
        analyzer_descriptor={"provider": "fake", "model": "test", "prompt_version": "v1"},
    )
    result = await ProposeMapping(
        uow, RecordingFakeAnalyzer(proposal), FakeProfiler(), ProfileExampleSanitizer()
    ).execute(file_id=file_id, data_source_id=None)

    assert result.validation["valid"] is False
    assert result.validation["errors"][0]["field_path"]


async def test_refinement_context_contains_only_latest_turns() -> None:
    uow = InMemoryUnitOfWork()
    analyzer = RecordingFakeAnalyzer()
    proposal = MappingProposal(
        mapping=valid_mapping(),
        rationale=(),
        ambiguities=(),
        unmapped_fields=(),
        analyzer_descriptor=analyzer.descriptor,
    )
    async with uow as transaction:
        proposal_id = await transaction.mapping_proposals.save(proposal, file_upload_id=1)
        for index in range(12):
            await transaction.mapping_proposals.add_message(
                proposal_id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"message-{index}",
            )
        await transaction.commit()

    await RefineMapping(uow, analyzer, max_conversation_turns=5).execute(
        proposal_id,
        "new turn",
        FileProfile(file_id=1, format="jsonl", record_count=0, sampled_records=0),
    )
    assert [message["content"] for message in analyzer.history_seen] == [
        "message-2",
        "message-3",
        "message-4",
        "message-5",
        "message-6",
        "message-7",
        "message-8",
        "message-9",
        "message-10",
        "message-11",
    ]
    assert uow._store.proposal_messages[-2] == (proposal_id, "user", "new turn")
    assistant_document = json.loads(uow._store.proposal_messages[-1][2])
    assert uow._store.proposal_messages[-1][0:2] == (proposal_id, "assistant")
    assert assistant_document["name"] == "refined"
    assert [message["turn_index"] for message in analyzer.history_seen] == list(range(2, 12))


async def test_save_mapping_validates_before_any_write_and_versions() -> None:
    uow = InMemoryUnitOfWork()
    source_id = await stored_data_source(uow, "portable")
    first = valid_mapping(name="portable")
    first_id = await SaveMapping(uow).execute(first, data_source_id=source_id)
    second_id = await SaveMapping(uow).execute(
        replace(first, entities=first.entities),
        data_source_id=source_id,
        previous_mapping_id=first_id,
    )
    async with uow as transaction:
        second = await transaction.mappings.get(second_id)
    assert second is not None
    assert second.version == 2
    document = mapping_to_document(second)
    serialized = str(document).lower()
    assert "provider" not in serialized
    assert "model" not in serialized

    invalid = replace(
        first,
        entities=(
            replace(
                first.entities[0],
                fields=(FieldRule(target="bad", source="$.bad"),),
            ),
        ),
    )
    before = len(uow._store.mappings)
    with pytest.raises(MappingInvalidError) as caught:
        await SaveMapping(uow).execute(invalid, data_source_id=source_id)
    assert caught.value.details["errors"][0]["field_path"]
    assert len(uow._store.mappings) == before


async def test_versioning_rejects_a_data_source_change() -> None:
    uow = InMemoryUnitOfWork()
    source_id = await stored_data_source(uow, "first-source")
    other_source_id = await stored_data_source(uow, "other-source")
    first_id = await SaveMapping(uow).execute(valid_mapping(), data_source_id=source_id)

    with pytest.raises(ConflictError):
        await SaveMapping(uow).execute(
            valid_mapping(),
            data_source_id=other_source_id,
            previous_mapping_id=first_id,
        )


def test_profile_sanitizer_redacts_paths_and_extrema() -> None:
    field = FieldProfile(
        path="$.nested./home/alice/private",
        types=("string",),
        null_ratio=0,
        min_value="/home/alice/private",
        max_value="API_KEY=secret-value-123",
        examples=(),
    )
    profile = FileProfile(
        file_id=1,
        format="jsonl",
        record_count=1,
        sampled_records=1,
        fields=(field,),
    )

    sanitized = ProfileExampleSanitizer().sanitize(profile).fields[0]

    assert "alice" not in sanitized.path
    assert "alice" not in str(sanitized.min_value)
    assert "secret-value-123" not in str(sanitized.max_value)


async def test_in_memory_message_window_matches_persisted_indices_and_zero_limit() -> None:
    uow = InMemoryUnitOfWork()
    proposal = MappingProposal(valid_mapping(), (), (), (), {})
    async with uow as transaction:
        proposal_id = await transaction.mapping_proposals.save(proposal, file_upload_id=1)
        for index in range(7):
            await transaction.mapping_proposals.add_message(
                proposal_id, role="user", content=str(index)
            )
        last_three = await transaction.mapping_proposals.list_messages(proposal_id, limit=3)
        empty = await transaction.mapping_proposals.list_messages(proposal_id, limit=0)

    assert [message["turn_index"] for message in last_three] == [4, 5, 6]
    assert empty == []
