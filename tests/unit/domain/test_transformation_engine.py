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
    assert results[0]["data"]["duration_ms"] == 2500.0


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
