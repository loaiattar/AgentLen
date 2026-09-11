from __future__ import annotations

from agentlen.domain.errors import (
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

# Only these operator names are allowed in a field rule.
OPERATOR_WHITELIST: frozenset[str] = frozenset(
    {
        "cast",
        "parse_datetime",
        "default",
        "coalesce",
        "unit_convert",
        "map_values",
        "trim",
        "lower",
        "upper",
        "regex_extract",
        "concat",
        "hash",
        "json_passthrough",
        "split_rows",
    }
)


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
        # coalesce/concat/hash resolve their `sources` like `source`.
        sources = op.get("sources")
        for j, source in enumerate(sources if isinstance(sources, list) else []):
            if isinstance(source, str):
                errors.extend(
                    _path_errors(source, prefix, f"{field_path}.operators[{i}].sources[{j}]")
                )

    return errors
