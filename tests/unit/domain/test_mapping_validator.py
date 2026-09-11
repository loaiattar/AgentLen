from uuid import uuid4

import pytest

from agentlen.domain.errors import (
    MissingNaturalKeyError,
    UnknownTargetFieldError,
    UnsupportedOperatorError,
)
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.mapping_validator import validate


def _make_mapping(entities: list[EntityMapping]) -> Mapping:
    return Mapping(
        id=uuid4(),
        name="test",
        version=1,
        source_format="jsonl",
        entities=entities,
    )


def test_valid_mapping_returns_no_errors():
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
                    )
                ],
            )
        ]
    )
    errors = validate(mapping)
    assert errors == []


def test_unsupported_operator_returns_error():
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
                        operators=[{"op": "eval_python"}],  # not in whitelist
                    )
                ],
            )
        ]
    )
    errors = validate(mapping)
    assert len(errors) == 1
    assert isinstance(errors[0], UnsupportedOperatorError)
    assert errors[0].code == "MAPPING_UNKNOWN_OPERATOR"
    assert "eval_python" in errors[0].message


def test_unknown_target_field_returns_error():
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["user_email"],
                fields=[
                    FieldRule(
                        target="user_email",  # not in session schema
                        source="$.email",
                        required=False,
                    )
                ],
            )
        ]
    )
    errors = validate(mapping)
    assert len(errors) == 1
    assert isinstance(errors[0], UnknownTargetFieldError)
    assert errors[0].code == "MAPPING_UNKNOWN_TARGET"
    assert "user_email" in errors[0].message


def test_multiple_errors_all_returned():
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(
                        target="bad_field",
                        source="$.x",
                        operators=[{"op": "not_real_op"}],
                    )
                ],
            )
        ]
    )
    errors = validate(mapping)
    assert len(errors) == 2  # unknown field + unsupported operator


def test_unknown_entity_target_returns_error():
    mapping = _make_mapping(
        [
            EntityMapping(
                target="user",  # not a valid entity
                natural_key=["id"],
                fields=[],
            )
        ]
    )
    errors = validate(mapping)
    assert len(errors) == 1
    assert errors[0].code == "MAPPING_UNKNOWN_TARGET"


def test_entity_without_a_natural_key_returns_error():
    mapping = _make_mapping(
        [
            EntityMapping(
                target="model_call",
                natural_key=[],  # nothing to deduplicate on
                fields=[FieldRule(target="sequence_index", source="$.index")],
            )
        ]
    )
    errors = validate(mapping)
    assert len(errors) == 1
    assert isinstance(errors[0], MissingNaturalKeyError)
    assert errors[0].code == "MAPPING_MISSING_NATURAL_KEY"


# ---------------------------------------------------------------------------
# Path notation (#121): only what TransformationEngine resolves passes
# ---------------------------------------------------------------------------

UNSUPPORTED_PATHS = [
    ("$.events[?(@.type=='llm_call')]", "filter"),
    ("$.events[*]", "wildcard"),
    ("$.*", "wildcard"),
    ("$.events[0]", "index"),
    ("$.events[1:3]", "index"),
    ("$..model", "recursive descent"),
    ('$["model', "unterminated"),
    ('$["model"x', "not followed by ']'"),
    ("$['model']", "double quotes"),
    ('$["a\\nb"]', "escape"),
    ("$.a-b", "unexpected '-'"),
    ("$.", "cannot end with '.'"),
    ("llm_calls", "starts with '$'"),
]


@pytest.mark.parametrize("where", ["iterate", "source"])
@pytest.mark.parametrize(("path", "reason"), UNSUPPORTED_PATHS)
def test_path_outside_the_supported_notation_is_refused_with_its_field_path(path, reason, where):
    entity = EntityMapping(
        target="tool_call",
        natural_key=["tool_name"],
        iterate=path if where == "iterate" else "$.tools[]",
        fields=[FieldRule(target="tool_name", source=path if where == "source" else "$.name")],
    )

    errors = validate(_make_mapping([entity]))

    location = ".iterate" if where == "iterate" else ".fields[target=tool_name].source"
    assert [(e.code, e.field_path) for e in errors] == [
        ("MAPPING_UNSUPPORTED_PATH", f"entities[target=tool_call]{location}")
    ]
    assert reason in errors[0].message


def test_list_marker_in_a_source_is_only_accepted_as_the_iterate_prefix():
    entity = EntityMapping(
        target="tool_call",
        natural_key=["tool_name"],
        iterate="$.tools[]",
        fields=[
            FieldRule(target="tool_name", source="$.tools[].tool_name"),
            FieldRule(
                target="status",
                source='$["status.code"]',
                operators=[{"op": "coalesce", "sources": ["$.tools[].ok", "$.results[].ok"]}],
            ),
        ],
    )

    errors = validate(_make_mapping([entity]))

    assert [(e.code, e.field_path) for e in errors] == [
        (
            "MAPPING_UNSUPPORTED_PATH",
            "entities[target=tool_call].fields[target=status].operators[0].sources[1]",
        )
    ]
    assert "iterate" in errors[0].message
