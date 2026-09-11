from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from agentlen.application.dto.mapping_document import mapping_to_document
from agentlen.application.errors import ConflictError, MappingInvalidError, NotFoundError
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


async def test_proposal_reports_404_when_the_file_disappears_during_the_agent_loop() -> None:
    """The existence check has to be inside the write transaction.

    It used to run before the agent loop and never again, so a file deleted
    during the loop — up to `max_iterations` provider calls long — let the
    insert violate the `file_upload_id` foreign key. The operator saw a driver
    error and a 500 where the answer is a 404.
    """
    uow = InMemoryUnitOfWork()
    file_id = await stored_file(uow)

    class DeletingAnalyzer(RecordingFakeAnalyzer):
        async def run_agent_loop(self, profile, tool_executor, hint=None):
            uow._store.file_uploads.clear()
            return await super().run_agent_loop(profile, tool_executor, hint)

    with pytest.raises(NotFoundError):
        await ProposeMapping(
            uow, DeletingAnalyzer(), FakeProfiler(), ProfileExampleSanitizer()
        ).execute(file_id=file_id, data_source_id=None)


async def test_versioning_reports_the_missing_mapping_before_validating() -> None:
    """`update_mapping` cannot know the name it is versioning.

    It passes `name=""` / `version=1` placeholders and lets `SaveMapping`
    resolve the real ones from the previous row. Validating before that
    resolution checked the placeholders, and answered a PUT against an unknown
    id with 422 MAPPING_INVALID instead of 404.
    """
    uow = InMemoryUnitOfWork()
    invalid = replace(
        valid_mapping(name=""),
        entities=(
            replace(
                valid_mapping().entities[0],
                fields=(FieldRule(target="bad", source="$.bad"),),
            ),
        ),
    )

    with pytest.raises(NotFoundError):
        await SaveMapping(uow).execute(invalid, data_source_id=None, previous_mapping_id=99999)


async def test_versioning_validates_the_resolved_name_and_version() -> None:
    """And the document that is actually written is the one that is checked."""
    uow = InMemoryUnitOfWork()
    source_id = await stored_data_source(uow, "resolved")
    first_id = await SaveMapping(uow).execute(
        valid_mapping(name="resolved"), data_source_id=source_id
    )

    second_id = await SaveMapping(uow).execute(
        valid_mapping(name="", version=1),
        data_source_id=None,
        previous_mapping_id=first_id,
    )

    async with uow as transaction:
        second = await transaction.mappings.get(second_id)
    assert second is not None
    assert (second.name, second.version) == ("resolved", 2)


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
    assert uow._store.proposal_messages[-1][0:2] == (proposal_id, "assistant")
    # The assistant turn is a summary, not the document. These rows are replayed
    # into the next refinement prompt, so storing the whole mapping in each of
    # them made the prompt grow without bound across a conversation.
    assistant_turn = uow._store.proposal_messages[-1][2]
    assert assistant_turn == "Proposition mise à jour : 1 règle(s) sur session."
    assert "$.id" not in assistant_turn
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


async def test_versioning_a_superseded_version_is_refused() -> None:
    """Two PUTs against v1 both used to compute v1 + 1.

    The version was derived from the row the caller named rather than from the
    highest one stored, so the second insert violated
    `uq_mapping_name_version` — an unhandled IntegrityError, i.e. a 500 on an
    ordinary double click. Refusing is deliberate: the caller was editing a
    document someone has since replaced.
    """
    uow = InMemoryUnitOfWork()
    source_id = await stored_data_source(uow, "superseded-src")
    first_id = await SaveMapping(uow).execute(
        valid_mapping(name="versioned"), data_source_id=source_id
    )
    await SaveMapping(uow).execute(
        valid_mapping(), data_source_id=None, previous_mapping_id=first_id
    )
    before = len(uow._store.mappings)

    with pytest.raises(ConflictError) as caught:
        await SaveMapping(uow).execute(
            valid_mapping(), data_source_id=None, previous_mapping_id=first_id
        )

    assert caught.value.details["version"] == 1
    assert caught.value.details["latest_version"] == 2
    assert len(uow._store.mappings) == before, "nothing should have been written"


async def test_versioning_the_latest_version_still_works() -> None:
    """The refusal must not catch the ordinary case."""
    uow = InMemoryUnitOfWork()
    source_id = await stored_data_source(uow, "chain-src")
    first_id = await SaveMapping(uow).execute(
        valid_mapping(name="chained"), data_source_id=source_id
    )
    second_id = await SaveMapping(uow).execute(
        valid_mapping(), data_source_id=None, previous_mapping_id=first_id
    )
    third_id = await SaveMapping(uow).execute(
        valid_mapping(), data_source_id=None, previous_mapping_id=second_id
    )

    async with uow as transaction:
        third = await transaction.mappings.get(third_id)
    assert third is not None
    assert (third.name, third.version) == ("chained", 3)


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


def test_profile_sanitizer_redacts_values_and_keeps_the_path_addressable() -> None:
    """The path is structure, not data — redacting it broke the mapping.

    `FieldProfile.path` is what the analyzer copies verbatim into
    `FieldRule.source`. Rewriting `/home/alice/…` to `/home/[USER]/…` produced a
    mapping addressing a path that does not exist in the file, and the field
    resolved to null at import time with nothing to show the operator. The
    values reachable through the path are what must be redacted.
    """
    field = FieldProfile(
        path="$.nested./home/alice/private",
        types=("string",),
        null_ratio=0,
        min_value="/home/alice/private",
        max_value="API_KEY=secret-value-123",
        examples=("alice@example.com",),
    )
    profile = FileProfile(
        file_id=1,
        format="jsonl",
        record_count=1,
        sampled_records=1,
        fields=(field,),
    )

    sanitized = ProfileExampleSanitizer().sanitize(profile).fields[0]

    assert sanitized.path == "$.nested./home/alice/private"
    assert "alice" not in str(sanitized.min_value)
    assert "secret-value-123" not in str(sanitized.max_value)
    assert sanitized.examples == ("[REDACTED_EMAIL]",)


def test_profile_sanitizer_keeps_distinct_paths_distinct() -> None:
    """Two users' paths used to collapse onto one key.

    `sanitize_key` has no collision handling, so `/home/alice/x` and
    `/home/bob/x` both became `/home/[USER]/x` and
    `MappingValidationTools.get_field_profile` returned the first for both.
    """

    def field(path: str) -> FieldProfile:
        return FieldProfile(path=path, types=("string",), null_ratio=0, examples=())

    profile = FileProfile(
        file_id=1,
        format="jsonl",
        record_count=1,
        sampled_records=1,
        fields=(field('$["/home/alice/x"]'), field('$["/home/bob/x"]')),
    )

    paths = [f.path for f in ProfileExampleSanitizer().sanitize(profile).fields]

    assert paths == ['$["/home/alice/x"]', '$["/home/bob/x"]']
    assert len(set(paths)) == 2


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
