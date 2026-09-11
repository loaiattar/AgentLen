from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from agentlen.domain.errors import (
    InvalidOperatorParamError,
    MissingNaturalKeyError,
    UnknownTargetFieldError,
    UnsupportedOperatorError,
    UnsupportedPathError,
    ValidationError,
)
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.domain.model.target_schema import TARGET_FIELD_TYPES
from agentlen.domain.services import json_path
from agentlen.domain.services.json_path import JsonPath

# Fields accepted per target entity.
# Only these combinations are valid in a mapping document.
_SCHEMA: dict[str, frozenset[str]] = {
    target: frozenset(fields) for target, fields in TARGET_FIELD_TYPES.items()
}

#: The entity names a mapping may target. Derived from `_SCHEMA` so the two can
#: never drift: an entity is valid exactly when this module knows which fields
#: it accepts. `EntityMapping` used to carry its own `VALID_TARGETS` frozenset
#: and a `validate_target` method that nothing called — a second source of truth
#: for the same list, with nothing holding the two together.
VALID_TARGETS: frozenset[str] = frozenset(_SCHEMA)

OperatorCheck = Callable[[dict[str, Any]], list[tuple[str, str]]]


@dataclass(frozen=True)
class OperatorSpec:
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    check: OperatorCheck | None = None


def _choice(parameter: str, allowed: frozenset[str]) -> OperatorCheck:
    def check(operator: dict[str, Any]) -> list[tuple[str, str]]:
        value = operator.get(parameter)
        if value is None or value in allowed:
            return []
        return [(parameter, f"must be one of {sorted(allowed)}, got {value!r}")]

    return check


def _sources(operator: dict[str, Any]) -> list[tuple[str, str]]:
    sources = operator.get("sources")
    if sources is None:
        return []
    if not isinstance(sources, list) or not sources or not all(isinstance(v, str) for v in sources):
        return [("sources", "must be a non-empty list of source paths")]
    return []


def _concat(operator: dict[str, Any]) -> list[tuple[str, str]]:
    errors = _sources(operator)
    separator = operator.get("separator")
    if separator is not None and not isinstance(separator, str):
        errors.append(("separator", "must be a string"))
    return errors


def _parse_datetime_format(operator: dict[str, Any]) -> list[tuple[str, str]]:
    value = operator.get("format")
    if value is None:
        return []
    if not isinstance(value, str) or not value:
        return [("format", "must be a non-empty format string")]
    errors: list[tuple[str, str]] = []
    if value not in {"iso8601", "unix_seconds", "unix_millis"}:
        try:
            datetime.strptime("", value)  # noqa: DTZ007 - syntax probe only
        except ValueError as exc:
            text = str(exc)
            if "bad directive" in text or "stray %" in text:
                errors.append(("format", f"invalid strptime format: {text}"))
    timezone = operator.get("timezone")
    if timezone is not None and timezone != "UTC":
        errors.append(("timezone", "only UTC is supported"))
    return errors


def _unit_conversion(operator: dict[str, Any]) -> list[tuple[str, str]]:
    source = operator.get("from")
    target = operator.get("to")
    if source is None or target is None:
        return []
    supported = {("s", "ms"), ("min", "ms"), ("ns", "ms"), ("ms", "s"), ("kb", "b"), ("mb", "b")}
    if not isinstance(source, str) or not isinstance(target, str):
        return [("from", "from and to must be strings")]
    if (source.lower(), target.lower()) not in supported:
        return [("to", f"unsupported conversion {source!r} -> {target!r}")]
    return []


def _map_values(operator: dict[str, Any]) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    table = operator.get("table")
    if table is not None and not isinstance(table, dict):
        errors.append(("table", "must be an object"))
    mode = operator.get("on_unknown")
    allowed = {"passthrough", "null", "reject", "constant"}
    if mode is not None and mode not in allowed:
        errors.append(("on_unknown", f"must be one of {sorted(allowed)}"))
    if mode == "constant" and "constant" not in operator:
        errors.append(("constant", "is required when on_unknown is 'constant'"))
    return errors


def _regex(operator: dict[str, Any]) -> list[tuple[str, str]]:
    pattern = operator.get("pattern")
    group = operator.get("group", 0)
    errors: list[tuple[str, str]] = []
    compiled: re.Pattern[str] | None = None
    if pattern is not None:
        if not isinstance(pattern, str) or not pattern:
            errors.append(("pattern", "must be a non-empty string"))
        else:
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                errors.append(("pattern", f"invalid regular expression: {exc}"))
            unsupported = ("(?=", "(?!", "(?<=", "(?<!", "\\1", "\\2", "\\3")
            if any(token in pattern for token in unsupported):
                errors.append(("pattern", "uses a construct unsupported by the RE2 extractor"))
    if not isinstance(group, int) or isinstance(group, bool) or group < 0:
        errors.append(("group", "must be a non-negative integer"))
    elif compiled is not None and group > compiled.groups:
        errors.append(("group", f"capture group {group} does not exist"))
    return errors


def _positive_max_bytes(operator: dict[str, Any]) -> list[tuple[str, str]]:
    value = operator.get("max_bytes")
    if value is None:
        return []
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return [("max_bytes", "must be a positive integer")]
    return []


OPERATOR_SPECS: dict[str, OperatorSpec] = {
    "cast": OperatorSpec(
        required=frozenset({"to"}),
        optional=frozenset({"on_error"}),
        check=lambda op: (
            _choice("to", frozenset({"string", "integer", "float", "boolean"}))(op)
            + _choice("on_error", frozenset({"reject", "null"}))(op)
        ),
    ),
    "parse_datetime": OperatorSpec(
        required=frozenset({"format"}),
        optional=frozenset({"timezone"}),
        check=_parse_datetime_format,
    ),
    "default": OperatorSpec(required=frozenset({"value"})),
    "coalesce": OperatorSpec(required=frozenset({"sources"}), check=_sources),
    "unit_convert": OperatorSpec(required=frozenset({"from", "to"}), check=_unit_conversion),
    "map_values": OperatorSpec(
        required=frozenset({"table", "on_unknown"}),
        optional=frozenset({"constant"}),
        check=_map_values,
    ),
    "trim": OperatorSpec(),
    "lower": OperatorSpec(),
    "upper": OperatorSpec(),
    "regex_extract": OperatorSpec(
        required=frozenset({"pattern"}), optional=frozenset({"group"}), check=_regex
    ),
    "concat": OperatorSpec(
        required=frozenset({"sources"}), optional=frozenset({"separator"}), check=_concat
    ),
    "hash": OperatorSpec(
        required=frozenset({"algorithm", "sources"}),
        check=lambda op: _sources(op) + _choice("algorithm", frozenset({"sha256"}))(op),
    ),
    "json_passthrough": OperatorSpec(optional=frozenset({"max_bytes"}), check=_positive_max_bytes),
}

OPERATOR_WHITELIST: frozenset[str] = frozenset(OPERATOR_SPECS)


def validate(mapping: Mapping) -> list[ValidationError]:
    """Validate a Mapping document.

    Returns a list of ValidationError (one per problem found).
    Never raises — callers decide what to do with the errors.
    """
    errors: list[ValidationError] = []

    for entity in mapping.entities:
        errors.extend(_validate_entity(entity))

    return errors


def _validate_entity(entity: EntityMapping) -> list[ValidationError]:
    errors: list[ValidationError] = []
    allowed_fields = _SCHEMA.get(entity.target)

    if allowed_fields is None:
        errors.append(
            UnknownTargetFieldError(
                target=entity.target,
                field_path=f"entities[target={entity.target}]",
            )
        )
        return errors  # no point checking fields if entity itself is unknown

    # Structural: deduplication (INSERT ... ON CONFLICT DO NOTHING) has nothing
    # to key off without a natural_key.
    if not entity.natural_key:
        errors.append(
            MissingNaturalKeyError(
                target=entity.target,
                field_path=f"entities[target={entity.target}]",
            )
        )

    # Syntactic: paths must be in the notation the engine resolves (json_path.py).
    prefix: JsonPath | None = None
    if entity.iterate:
        try:
            prefix = json_path.iterate_path(entity.iterate)
        except UnsupportedPathError as exc:
            errors.append(
                UnsupportedPathError(
                    exc.path, exc.reason, field_path=f"entities[target={entity.target}].iterate"
                )
            )

    for field_rule in entity.fields:
        errors.extend(_validate_field(field_rule, entity.target, allowed_fields, prefix))

    return errors


def _path_errors(path: str, prefix: JsonPath | None, field_path: str) -> list[ValidationError]:
    try:
        json_path.source_path(path, prefix)
    except UnsupportedPathError as exc:
        return [UnsupportedPathError(exc.path, exc.reason, field_path=field_path)]
    return []


def _validate_field(
    rule: FieldRule,
    entity_target: str,
    allowed_fields: frozenset[str],
    prefix: JsonPath | None,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    field_path = f"entities[target={entity_target}].fields[target={rule.target}]"

    # Semantic: target field must exist in the schema
    if rule.target not in allowed_fields:
        errors.append(UnknownTargetFieldError(target=rule.target, field_path=field_path))

    errors.extend(_path_errors(rule.source, prefix, f"{field_path}.source"))

    # Semantic: all operators must be whitelisted
    for i, op in enumerate(rule.operators):
        op_name = op.get("op", "")
        if op_name not in OPERATOR_WHITELIST:
            errors.append(
                UnsupportedOperatorError(
                    operator=op_name,
                    field_path=f"{field_path}.operators[{i}]",
                )
            )
            continue
        spec = OPERATOR_SPECS[op_name]
        operator_path = f"{field_path}.operators[{i}]"
        for missing in sorted(spec.required - op.keys()):
            errors.append(
                InvalidOperatorParamError(
                    field_path=f"{operator_path}.{missing}",
                    message=f"Required parameter '{missing}' is missing for '{op_name}'.",
                )
            )
        allowed_parameters = spec.required | spec.optional | {"op"}
        for unexpected in sorted(op.keys() - allowed_parameters):
            errors.append(
                InvalidOperatorParamError(
                    field_path=f"{operator_path}.{unexpected}",
                    message=f"Parameter '{unexpected}' is not allowed for '{op_name}'.",
                )
            )
        if spec.check is not None:
            for parameter, message in spec.check(op):
                errors.append(
                    InvalidOperatorParamError(
                        field_path=f"{operator_path}.{parameter}", message=message
                    )
                )

        # coalesce/concat/hash resolve their `sources` like `source`.
        sources = op.get("sources")
        for j, source in enumerate(sources if isinstance(sources, list) else []):
            if isinstance(source, str):
                errors.extend(_path_errors(source, prefix, f"{operator_path}.sources[{j}]"))

    return errors
