from uuid import uuid4

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
