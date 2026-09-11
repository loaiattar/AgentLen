from uuid import uuid4

from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.transformation_engine import TransformationEngine


def _make_mapping(entities: list[EntityMapping]) -> Mapping:
    return Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=entities,
    )


def test_apply_returns_issue_not_exception_on_required_field_failure():
    """A cast failure on a required field must return an ImportIssue, not raise."""
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(
                        target="external_id",
                        source="$.id",
                        required=True,
                        operators=[{"op": "cast", "to": "integer", "on_error": "reject"}],
                    )
                ],
            )
        ]
    )
    raw = {"id": "not-an-integer"}
    results, issues = engine.apply(mapping, raw, line_number=42)

    assert results == []
    assert len(issues) == 1
    assert isinstance(issues[0], ImportIssue)
    assert issues[0].severity == "rejected"
    assert issues[0].line_number == 42


def test_apply_succeeds_with_valid_cast():
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(
                        target="external_id",
                        source="$.session_id",
                        required=True,
                        operators=[{"op": "cast", "to": "string"}],
                    ),
                    FieldRule(
                        target="duration_ms",
                        source="$.duration_s",
                        required=False,
                        operators=[{"op": "unit_convert", "from": "s", "to": "ms"}],
                    ),
                ],
            )
        ]
    )
    raw = {"session_id": "abc123", "duration_s": 2.5}
    results, issues = engine.apply(mapping, raw)

    assert issues == []
    assert len(results) == 1
    assert results[0]["entity"] == "session"
    assert results[0]["data"]["external_id"] == "abc123"
    assert results[0]["data"]["duration_ms"] == 2500
    assert isinstance(results[0]["data"]["duration_ms"], int)


def test_apply_with_default_operator_fills_missing_value():
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(
                        target="external_id",
                        source="$.id",
                        required=True,
                        operators=[{"op": "cast", "to": "string"}],
                    ),
                    FieldRule(
                        target="outcome",
                        source="$.status",
                        required=False,
                        operators=[{"op": "default", "value": "unknown"}],
                    ),
                ],
            )
        ]
    )
    raw = {"id": "s1"}  # 'status' field absent
    results, issues = engine.apply(mapping, raw)

    assert issues == []
    assert results[0]["data"]["outcome"] == "unknown"


def test_apply_non_required_field_failure_produces_warning_not_rejection():
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(
                        target="external_id",
                        source="$.id",
                        required=True,
                        operators=[{"op": "cast", "to": "string"}],
                    ),
                    FieldRule(
                        target="duration_ms",
                        source="$.dur",
                        required=False,
                        operators=[{"op": "cast", "to": "integer", "on_error": "reject"}],
                    ),
                ],
            )
        ]
    )
    raw = {"id": "s1", "dur": "bad-value"}
    results, issues = engine.apply(mapping, raw)

    # Entity still produced (required field succeeded)
    assert len(results) == 1
    # Warning issue for the non-required field
    assert len(issues) == 1
    assert issues[0].severity == "warning"


def test_apply_map_values_operator():
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="tool_call",
                natural_key=["sequence_index"],
                fields=[
                    FieldRule(
                        target="sequence_index",
                        source="$.index",
                        required=True,
                        operators=[{"op": "cast", "to": "integer"}],
                    ),
                    FieldRule(
                        target="status",
                        source="$.error",
                        required=False,
                        operators=[
                            {
                                "op": "map_values",
                                "table": {"null": "ok"},
                                "on_unknown": "constant",
                                "constant": "error",
                            }
                        ],
                    ),
                ],
            )
        ]
    )
    raw = {"index": 1, "error": None}
    results, issues = engine.apply(mapping, raw)
    assert results[0]["data"]["status"] == "ok"


def test_source_index_reflects_position_before_rejection_not_survivor_rank():
    """A rejected row must not shift the source_index of the rows after it —
    that index is used downstream as part of a natural key (sequence_index),
    and a shifting key breaks reimport idempotence."""
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="tool_call",
                natural_key=["sequence_index"],
                iterate="$.tools",
                fields=[
                    FieldRule(
                        target="tool_name",
                        source="$.name",
                        required=True,
                        operators=[{"op": "cast", "to": "string"}],
                    ),
                ],
            )
        ]
    )
    # Middle row is malformed (name is a dict, cast to string still "succeeds"
    # trivially) -> use a required field that's simply absent instead, which
    # triggers MISSING_REQUIRED_FIELD and drops the row from `results`.
    raw = {"tools": [{"name": "Bash"}, {}, {"name": "Write"}]}

    results, issues = engine.apply(mapping, raw)

    expected_surviving_count = 2
    expected_third_row_source_index = 2  # it's the 3rd source row, not the 2nd survivor
    assert len(results) == expected_surviving_count
    assert len(issues) == 1
    assert results[0]["data"]["tool_name"] == "Bash"
    assert results[0]["source_index"] == 0
    assert results[1]["data"]["tool_name"] == "Write"
    assert results[1]["source_index"] == expected_third_row_source_index


def test_json_number_on_a_string_field_is_coerced_not_rejected():
    """The type gate must not refuse what RecordNormalizer would have coerced.

    `analysis.py` teaches the model to map `$.run_id` onto `external_id` with no
    cast operator, and `RecordNormalizer` does `str(data["external_id"])`. A
    trace whose `run_id` is a JSON number must keep importing: rejecting it here
    loses the session, and with it every child row under PARENT_SESSION_MISSING.
    """
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[FieldRule(target="external_id", source="$.run_id", required=True)],
            )
        ]
    )
    results, issues = engine.apply(mapping, {"run_id": 41823})

    assert issues == []
    assert len(results) == 1
    assert results[0]["data"]["external_id"] == "41823"


def test_float_on_an_integer_field_is_rounded_not_rejected():
    """A float on an int field is a unit-conversion artefact, not another value."""
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(target="external_id", source="$.id", required=True),
                    FieldRule(target="duration_ms", source="$.dur"),
                ],
            )
        ]
    )
    results, issues = engine.apply(mapping, {"id": "s1", "dur": 1004.9999999999999})

    assert issues == []
    assert results[0]["data"]["duration_ms"] == 1005


def test_type_mismatch_on_an_optional_field_warns_and_keeps_the_entity():
    """An optional field of the wrong type drops its value, it does not reject.

    Matching the established policy for a failed operator: rejecting the whole
    entity would drag its children down with PARENT_SESSION_MISSING over a field
    nobody declared necessary.
    """
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(target="external_id", source="$.id", required=True),
                    FieldRule(target="agent_name", source="$.agent"),
                ],
            )
        ]
    )
    results, issues = engine.apply(mapping, {"id": "s1", "agent": {"nested": "object"}})

    assert len(results) == 1
    assert "agent_name" not in results[0]["data"]
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].code == "TYPE_MISMATCH"


def test_type_mismatch_on_a_natural_key_field_rejects_even_when_optional():
    """A natural-key field is identity: dropping it would silently renumber the row."""
    engine = TransformationEngine()
    mapping = _make_mapping(
        [
            EntityMapping(
                target="tool_call",
                natural_key=["sequence_index"],
                fields=[
                    FieldRule(target="tool_name", source="$.name", required=True),
                    FieldRule(target="sequence_index", source="$.idx"),
                ],
            )
        ]
    )
    results, issues = engine.apply(mapping, {"name": "Bash", "idx": "7"})

    assert results == []
    assert len(issues) == 1
    assert issues[0].severity == "rejected"
    assert issues[0].code == "TYPE_MISMATCH"
