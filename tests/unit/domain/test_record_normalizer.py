from uuid import uuid4

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.record_normalizer import RecordNormalizer

DATA_SOURCE_ID = 1
EXPECTED_MODEL_CALL_COUNT = 3
EXPECTED_TOOL_CALL_COUNT = 5

RAW_RECORD = {
    "id": "sess-1",
    "agent": "claude-code",
    "llm_calls": [
        {"model": "claude-opus", "provider": "anthropic", "tokens_in": 10, "tokens_out": 5},
        {"model": "claude-opus", "provider": "anthropic", "tokens_in": 20, "tokens_out": 8},
        {"model": "claude-opus", "provider": "anthropic", "tokens_in": 30, "tokens_out": 12},
    ],
    "tool_uses": [
        {"name": "Bash"},
        {"name": "Read"},
        {"name": "Write"},
        {"name": "Edit"},
        {"name": "Bash"},
    ],
}


def _full_mapping() -> Mapping:
    return Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=[
                    FieldRule(target="external_id", source="$.id", required=True),
                    FieldRule(target="agent_name", source="$.agent"),
                ],
            ),
            EntityMapping(
                target="model_call",
                natural_key=("sequence_index",),
                iterate="$.llm_calls",
                parent={"entity": "session", "via": "external_id"},
                fields=[
                    FieldRule(target="model_name", source="$.model"),
                    FieldRule(target="provider_name", source="$.provider"),
                    FieldRule(
                        target="input_tokens",
                        source="$.tokens_in",
                        operators=[{"op": "cast", "to": "integer"}],
                    ),
                    FieldRule(
                        target="output_tokens",
                        source="$.tokens_out",
                        operators=[{"op": "cast", "to": "integer"}],
                    ),
                ],
            ),
            EntityMapping(
                target="tool_call",
                natural_key=("sequence_index",),
                iterate="$.tool_uses",
                parent={"entity": "session", "via": "external_id"},
                fields=[
                    FieldRule(target="tool_name", source="$.name", required=True),
                ],
            ),
        ],
    )


def test_one_record_produces_one_session_and_all_its_children():
    normalizer = RecordNormalizer()
    result = normalizer.normalize(_full_mapping(), RAW_RECORD, data_source_id=DATA_SOURCE_ID)

    assert result.issues == ()
    assert len(result.sessions) == 1
    assert len(result.model_calls) == EXPECTED_MODEL_CALL_COUNT
    assert len(result.tool_calls) == EXPECTED_TOOL_CALL_COUNT


def test_children_are_linked_to_their_session_by_id():
    normalizer = RecordNormalizer()
    result = normalizer.normalize(_full_mapping(), RAW_RECORD, data_source_id=DATA_SOURCE_ID)

    session_id = result.sessions[0].id
    assert all(mc.session_id == session_id for mc in result.model_calls)
    assert all(tc.session_id == session_id for tc in result.tool_calls)


def test_sequence_index_is_stable_across_runs_on_the_same_record():
    normalizer = RecordNormalizer()
    result_a = normalizer.normalize(_full_mapping(), RAW_RECORD, data_source_id=DATA_SOURCE_ID)
    result_b = normalizer.normalize(_full_mapping(), RAW_RECORD, data_source_id=DATA_SOURCE_ID)

    indices_a = [mc.sequence_index for mc in result_a.model_calls]
    indices_b = [mc.sequence_index for mc in result_b.model_calls]
    assert indices_a == indices_b == [0, 1, 2]


def test_missing_required_field_rejects_only_that_entity():
    mapping = _full_mapping()
    raw = {**RAW_RECORD, "tool_uses": [{"name": "Bash"}, {}]}  # second tool_use has no name

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    # session + 3 model_calls still produced; only the bad tool_call is rejected
    assert len(result.sessions) == 1
    assert len(result.model_calls) == EXPECTED_MODEL_CALL_COUNT
    assert len(result.tool_calls) == 1
    assert len(result.issues) == 1
    assert result.issues[0].severity == "rejected"


def test_missing_natural_key_field_produces_mapping_missing_natural_key_issue():
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=[
                    # 'external_id' is required-optional here but source path is wrong,
                    # so it never resolves and the natural key is missing.
                    FieldRule(target="external_id", source="$.does_not_exist", required=False),
                ],
            ),
        ],
    )
    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, {"id": "sess-1"}, data_source_id=DATA_SOURCE_ID)

    assert result.sessions == ()
    assert len(result.issues) == 1
    assert result.issues[0].code == "MAPPING_MISSING_NATURAL_KEY"


def test_collects_reference_requests_for_agent_provider_model_and_tool_names():
    normalizer = RecordNormalizer()
    result = normalizer.normalize(_full_mapping(), RAW_RECORD, data_source_id=DATA_SOURCE_ID)

    kinds_and_names = {(r.kind, r.name) for r in result.reference_requests}
    assert ("agent", "claude-code") in kinds_and_names
    assert ("provider", "anthropic") in kinds_and_names
    assert ("model", "claude-opus") in kinds_and_names
    assert ("tool", "Bash") in kinds_and_names


def test_children_are_rejected_when_their_session_is_rejected():
    mapping = _full_mapping()
    raw = {**RAW_RECORD, "id": None}  # session's required external_id fails

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    assert result.sessions == ()
    assert result.model_calls == ()
    assert result.tool_calls == ()
    codes = {issue.code for issue in result.issues}
    assert "PARENT_SESSION_MISSING" in codes
