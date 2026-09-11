from uuid import uuid4

import pytest

from agentlen.domain.errors import (
    MissingNaturalKeyError,
    UnknownTargetFieldError,
    UnsupportedOperatorError,
)
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.services.mapping_validator import OPERATOR_WHITELIST, validate


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


@pytest.mark.parametrize(
    ("operator", "parameter"),
    [
        ({"op": "cast"}, "to"),
        ({"op": "cast", "to": "decimal"}, "to"),
        ({"op": "unit_convert", "from": "fortnight", "to": "ms"}, "to"),
        ({"op": "regex_extract", "pattern": "(unclosed"}, "pattern"),
        ({"op": "regex_extract", "pattern": "value-(.*)", "group": 2}, "group"),
        ({"op": "regex_extract", "pattern": "value(?=x)"}, "pattern"),
        ({"op": "coalesce", "sources": []}, "sources"),
        ({"op": "map_values", "table": {}, "on_unknown": "constant"}, "constant"),
        ({"op": "json_passthrough", "max_bytes": 0}, "max_bytes"),
        ({"op": "trim", "unexpected": True}, "unexpected"),
    ],
)
def test_invalid_operator_parameters_are_localized(operator, parameter):  # type: ignore[no-untyped-def]
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
                        operators=[operator],
                    )
                ],
            )
        ]
    )

    errors = validate(mapping)

    assert len(errors) == 1
    assert errors[0].code == "INVALID_OPERATOR_PARAM"
    assert errors[0].field_path.endswith(f".{parameter}")


def test_split_rows_is_refused_until_it_is_implemented():
    assert "split_rows" not in OPERATOR_WHITELIST
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[
                    FieldRule(
                        target="external_id",
                        source="$.id",
                        operators=[{"op": "split_rows", "path": "$.items"}],
                    )
                ],
            )
        ]
    )

    assert validate(mapping)[0].code == "MAPPING_UNKNOWN_OPERATOR"


def test_target_schema_matches_the_fields_consumed_by_domain_entities():
    from agentlen.domain.model.model_call import ModelCall, TokenUsage
    from agentlen.domain.model.session import Session
    from agentlen.domain.model.target_schema import TARGET_FIELD_TYPES
    from agentlen.domain.model.tool_call import ToolCall

    session_fields = set(Session.__annotations__) - {"id", "data_source_id"}
    model_call_fields = (
        set(ModelCall.__annotations__) - {"id", "session_id", "token_usage"}
    ) | set(TokenUsage.__annotations__)
    tool_call_fields = set(ToolCall.__annotations__) - {"id", "session_id", "model_call_id"}

    assert set(TARGET_FIELD_TYPES["session"]) == session_fields
    assert set(TARGET_FIELD_TYPES["model_call"]) == model_call_fields
    assert set(TARGET_FIELD_TYPES["tool_call"]) == tool_call_fields


@pytest.mark.parametrize(
    "operator",
    [
        {"op": "cast", "to": "integer", "on_error": "null"},
        {"op": "parse_datetime", "format": "iso8601", "timezone": "UTC"},
        {"op": "default", "value": "unknown"},
        {"op": "coalesce", "sources": ["$.a", "$.b"]},
        {"op": "unit_convert", "from": "s", "to": "ms"},
        {"op": "map_values", "table": {}, "on_unknown": "null"},
        {"op": "trim"},
        {"op": "lower"},
        {"op": "upper"},
        {"op": "regex_extract", "pattern": "value-(.*)", "group": 1},
        {"op": "concat", "sources": ["$.a"], "separator": "-"},
        {"op": "hash", "algorithm": "sha256", "sources": ["$.id"]},
        {"op": "json_passthrough", "max_bytes": 1024},
    ],
)
def test_every_supported_operator_has_a_valid_parameter_shape(operator):  # type: ignore[no-untyped-def]
    mapping = _make_mapping(
        [
            EntityMapping(
                target="session",
                natural_key=["external_id"],
                fields=[FieldRule(target="external_id", source="$.id", operators=[operator])],
            )
        ]
    )

    assert validate(mapping) == []
