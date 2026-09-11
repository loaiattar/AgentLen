from uuid import uuid4

import pytest

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.record_normalizer import RecordNormalizer, reference_name

DATA_SOURCE_ID = 1
EXPECTED_MODEL_CALL_COUNT = 3
EXPECTED_TOOL_CALL_COUNT = 5
EXPECTED_PARENT_MISSING_ISSUE_COUNT = (
    2  # one per affected entity type (model_call, tool_call), not per child
)
EXPECTED_SURVIVING_MODEL_CALLS_AFTER_ONE_BAD_STATUS = 2

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


def test_parent_session_missing_is_reported_once_per_entity_type_not_once_per_child():
    # A rejected session with 3 model_calls + 5 tool_calls must not inflate
    # ImportReport.issues to 8 entries (one per child) for what is really one
    # root cause — one issue per affected entity type instead.
    mapping = _full_mapping()
    raw = {**RAW_RECORD, "id": None}

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    parent_missing_issues = [i for i in result.issues if i.code == "PARENT_SESSION_MISSING"]
    assert len(parent_missing_issues) == EXPECTED_PARENT_MISSING_ISSUE_COUNT


def test_reimport_after_fixing_a_bad_row_does_not_shift_sequence_index():
    # The exact scenario from the review: a malformed row in the middle gets
    # fixed and the file is reimported. Every OTHER row's sequence_index
    # (its natural key) must stay exactly what it was on the first import,
    # or the fixed reimport inserts duplicates instead of matching them.
    mapping = _full_mapping()
    broken = {
        **RAW_RECORD,
        "tool_uses": [{"name": "Bash"}, {}, {"name": "Write"}],  # index 1 is malformed
    }
    fixed = {
        **RAW_RECORD,
        "tool_uses": [{"name": "Bash"}, {"name": "Read"}, {"name": "Write"}],
    }

    normalizer = RecordNormalizer()
    first_import = normalizer.normalize(mapping, broken, data_source_id=DATA_SOURCE_ID)
    second_import = normalizer.normalize(mapping, fixed, data_source_id=DATA_SOURCE_ID)

    expected_write_index = 2  # 3rd source row, whether or not row 2 was rejected
    write_before = next(tc for tc in first_import.tool_calls if tc.tool_name == "Write")
    write_after = next(tc for tc in second_import.tool_calls if tc.tool_name == "Write")
    assert write_before.sequence_index == expected_write_index
    assert write_after.sequence_index == expected_write_index


def test_missing_optional_field_indexed_directly_produces_an_issue_not_a_crash():
    # external_id isn't in natural_key here (a plausible AI-authored mapping
    # that forgot to mark it required/key) and is absent from the source —
    # this must not raise a raw KeyError out of normalize().
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=(),
                fields=[
                    FieldRule(target="external_id", source="$.does_not_exist", required=False),
                ],
            ),
        ],
    )
    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, {"id": "sess-1"}, data_source_id=DATA_SOURCE_ID)

    assert result.sessions == ()
    assert len(result.issues) == 1
    assert result.issues[0].code == "ENTITY_CONSTRUCTION_FAILED"


def test_tool_name_missing_and_not_in_natural_key_produces_an_issue_not_a_crash():
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=[FieldRule(target="external_id", source="$.id", required=True)],
            ),
            EntityMapping(
                target="tool_call",
                natural_key=(),  # forgot to key on sequence_index too
                iterate="$.tool_uses",
                parent={"entity": "session", "via": "external_id"},
                fields=[FieldRule(target="tool_name", source="$.name", required=False)],
            ),
        ],
    )
    raw = {"id": "sess-1", "tool_uses": [{}]}  # no 'name' key at all

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    assert result.tool_calls == ()
    construction_issues = [i for i in result.issues if i.code == "ENTITY_CONSTRUCTION_FAILED"]
    assert len(construction_issues) == 1


def test_invalid_status_value_rejects_only_that_model_call_not_the_whole_import():
    # A source writing "success" instead of "ok"/"error"/"unknown" is the
    # ordinary case for an AI-proposed mapping without a map_values operator
    # — not an edge case that's allowed to take the whole run down.
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=[FieldRule(target="external_id", source="$.id", required=True)],
            ),
            EntityMapping(
                target="model_call",
                natural_key=("sequence_index",),
                iterate="$.calls",
                parent={"entity": "session", "via": "external_id"},
                fields=[FieldRule(target="status", source="$.status")],
            ),
        ],
    )
    raw = {
        "id": "sess-1",
        "calls": [{"status": "ok"}, {"status": "success"}, {"status": "error"}],
    }

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    assert len(result.model_calls) == EXPECTED_SURVIVING_MODEL_CALLS_AFTER_ONE_BAD_STATUS
    assert {mc.status for mc in result.model_calls} == {"ok", "error"}
    construction_issues = [i for i in result.issues if i.code == "ENTITY_CONSTRUCTION_FAILED"]
    assert len(construction_issues) == 1


def test_invalid_outcome_value_produces_an_issue_not_a_crash():
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
                    FieldRule(target="external_id", source="$.id", required=True),
                    FieldRule(target="outcome", source="$.status"),
                ],
            ),
        ],
    )
    raw = {"id": "sess-1", "status": "finished"}  # not in Session.VALID_OUTCOMES

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    assert result.sessions == ()
    assert len(result.issues) == 1
    assert result.issues[0].code == "ENTITY_CONSTRUCTION_FAILED"


def test_multiple_session_rows_keeps_the_first_and_warns_about_the_rest():
    # Nothing in EntityMapping/MappingValidator forbids `iterate` on the
    # session entity — the normalizer must not drop the extra sessions with
    # zero trace of why.
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                iterate="$.sessions",
                fields=[FieldRule(target="external_id", source="$.id", required=True)],
            ),
        ],
    )
    raw = {"sessions": [{"id": "sess-1"}, {"id": "sess-2"}]}

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    assert len(result.sessions) == 1
    assert result.sessions[0].external_id == "sess-1"
    warnings = [i for i in result.issues if i.code == "MULTIPLE_SESSIONS_IGNORED"]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"


def test_model_reference_request_carries_provider_as_context():
    # 'model' is unique on (provider_id, name) — without the provider in
    # context, ResolveReferences has nothing to link the model to.
    normalizer = RecordNormalizer()
    result = normalizer.normalize(_full_mapping(), RAW_RECORD, data_source_id=DATA_SOURCE_ID)

    model_request = next(r for r in result.reference_requests if r.kind == "model")
    assert model_request.context == (("provider_name", "anthropic"),)


def test_numeric_names_are_text_before_resolution():
    # A number handed to SQL as a name used to fail the whole import (#141).
    raw = {
        "id": "sess-1",
        "agent": 42,
        "llm_calls": [{"model": 7, "provider": 3, "tokens_in": 1, "tokens_out": 1}],
        "tool_uses": [{"name": 123}],
    }

    result = RecordNormalizer().normalize(_full_mapping(), raw, data_source_id=DATA_SOURCE_ID)

    assert result.issues == ()
    assert {(r.kind, r.name, r.context) for r in result.reference_requests} == {
        ("agent", "42", ()),
        ("provider", "3", ()),
        ("model", "7", (("provider_name", "3"),)),
        ("tool", "123", ()),
    }
    assert result.tool_calls[0].tool_name == "123"


def test_a_blank_tool_name_rejects_that_call_with_an_explained_issue():
    raw = {"id": "sess-1", "tool_uses": [{"name": "Bash"}, {"name": ""}, {"name": "  "}]}

    result = RecordNormalizer().normalize(
        _full_mapping(), raw, data_source_id=DATA_SOURCE_ID, line_number=4
    )

    assert [call.tool_name for call in result.tool_calls] == ["Bash"]
    field_path = "entities[target=tool_call].fields[target=tool_name]"
    assert [(i.code, i.severity, i.field_path, i.line_number) for i in result.issues] == [
        ("REFERENCE_NAME_INVALID", "rejected", field_path, 4),
        ("REFERENCE_NAME_INVALID", "rejected", field_path, 4),
    ]
    assert [r.name for r in result.reference_requests if r.kind == "tool"] == ["Bash"]


def test_a_blank_agent_or_model_name_is_an_absent_name_not_an_issue():
    raw = {
        "id": "sess-1",
        "agent": " ",
        "llm_calls": [{"model": "", "provider": "anthropic", "tokens_in": 1, "tokens_out": 1}],
    }

    result = RecordNormalizer().normalize(_full_mapping(), raw, data_source_id=DATA_SOURCE_ID)

    assert result.issues == ()
    assert result.sessions[0].agent_name is None
    assert result.model_calls[0].model_name is None
    assert {(r.kind, r.name) for r in result.reference_requests} == {("provider", "anthropic")}


def test_a_boolean_name_is_rejected_not_stored_as_text():
    raw = {"id": "sess-1", "tool_uses": [{"name": True}]}

    result = RecordNormalizer().normalize(_full_mapping(), raw, data_source_id=DATA_SOURCE_ID)

    assert result.tool_calls == ()
    assert [(i.code, i.severity) for i in result.issues] == [("TYPE_MISMATCH", "rejected")]
    assert [r for r in result.reference_requests if r.kind == "tool"] == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [(123, "123"), (7.5, "7.5"), ("Bash", "Bash"), ("   ", None), ("", None), (None, None)],
)
def test_reference_name_turns_numbers_into_text_and_blanks_into_no_name(value, expected):
    assert reference_name(value) == expected


@pytest.mark.parametrize("value", [True, False, {"name": "Bash"}, ["Bash"]])
def test_reference_name_refuses_what_is_not_a_name(value):
    with pytest.raises(ValueError, match="expected text or a number"):
        reference_name(value)


def test_sequence_index_string_without_cast_is_rejected_as_type_mismatch():
    mapping = Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=[
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=[FieldRule(target="external_id", source="$.id", required=True)],
            ),
            EntityMapping(
                target="tool_call",
                natural_key=("sequence_index",),
                iterate="$.tool_uses",
                parent={"entity": "session", "via": "external_id"},
                fields=[
                    FieldRule(target="tool_name", source="$.name", required=True),
                    FieldRule(target="sequence_index", source="$.idx"),  # no cast operator
                ],
            ),
        ],
    )
    raw = {"id": "sess-1", "tool_uses": [{"name": "Bash", "idx": "7"}]}

    normalizer = RecordNormalizer()
    result = normalizer.normalize(mapping, raw, data_source_id=DATA_SOURCE_ID)

    assert result.tool_calls == ()
    assert len(result.sessions) == 1
    assert len(result.issues) == 1
    assert result.issues[0].code == "TYPE_MISMATCH"
    assert result.issues[0].field_path == (
        "entities[target=tool_call].fields[target=sequence_index]"
    )
