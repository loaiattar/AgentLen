from uuid import uuid4

import pytest

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


# ---------------------------------------------------------------------------
# Path notation (#121): the one PolarsFileProfiler writes and the prompt teaches
# ---------------------------------------------------------------------------


def _calls(iterate: str, source: str) -> Mapping:
    entity = EntityMapping(
        target="model_call",
        natural_key=["model_name"],
        iterate=iterate,
        fields=[FieldRule(target="model_name", source=source)],
    )
    return _make_mapping([entity])


@pytest.mark.parametrize(
    ("source", "raw"),
    [
        ("$.run.id", {"run": {"id": "r1"}}),
        ('$["run.id"]', {"run.id": "r1", "run": {"id": "wrong"}}),
        ('$["say \\"hi\\""]["back\\\\slash"]', {'say "hi"': {"back\\slash": "r1"}}),
    ],
)
def test_source_notation_reads_the_member_it_names(source, raw):
    rule = FieldRule(target="external_id", source=source)
    mapping = _make_mapping(
        [EntityMapping(target="session", natural_key=["external_id"], fields=[rule])]
    )

    results, issues = TransformationEngine().apply(mapping, raw)

    assert issues == []
    assert results[0]["data"] == {"external_id": "r1"}


CALLS = {"name": "top-level", "calls": [{"name": "a"}, {"name": "b"}]}


@pytest.mark.parametrize(
    ("iterate", "source", "raw"),
    [
        ("$.calls[]", "$.name", CALLS),
        ("$.calls", "$.name", CALLS),
        ("$.calls[]", "$.calls[].name", CALLS),  # the form the profile shows
        ("$.turns[].calls[]", "$.name", {"turns": [CALLS, {"calls": []}]}),
    ],
)
def test_iterate_notation_yields_one_row_per_list_element(iterate, source, raw):
    results, issues = TransformationEngine().apply(_calls(iterate, source), raw)

    assert issues == []
    assert [r["data"]["model_name"] for r in results] == ["a", "b"]


def test_iterate_on_a_value_that_is_not_a_list_is_explained_not_silent():
    results, issues = TransformationEngine().apply(
        _calls("$.calls[]", "$.name"), {"calls": "oops"}, line_number=7
    )

    assert results == []
    assert [(i.severity, i.code, i.field_path, i.line_number) for i in issues] == [
        ("rejected", "ITERATE_NOT_A_LIST", "entities[target=model_call].iterate", 7)
    ]
    assert "a string where a list was expected" in issues[0].message


@pytest.mark.parametrize("raw", [{}, {"calls": None}, {"calls": []}])
def test_iterate_on_an_absent_or_empty_list_yields_no_row_and_no_issue(raw):
    assert TransformationEngine().apply(_calls("$.calls[]", "$.name"), raw) == ([], [])


def test_unsupported_path_in_an_unvalidated_mapping_is_an_issue_not_an_exception():
    _, issues = TransformationEngine().apply(_calls("$.calls[]", "$.x[0]"), CALLS)

    assert {(i.code, i.field_path) for i in issues} == {
        ("MAPPING_UNSUPPORTED_PATH", "entities[target=model_call].fields[target=model_name].source")
    }
