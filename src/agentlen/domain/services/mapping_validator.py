from __future__ import annotations

from agentlen.domain.errors import (
    MissingNaturalKeyError,
    UnknownTargetFieldError,
    UnsupportedOperatorError,
    ValidationError,
)
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping

# Fields accepted per target entity.
# Only these combinations are valid in a mapping document.
_SCHEMA: dict[str, frozenset[str]] = {
    "session": frozenset(
        {
            "external_id",
            "agent_name",
            "started_at",
            "ended_at",
            "duration_ms",
            "outcome",
            "repository_url",
        }
    ),
    "model_call": frozenset(
        {
            "sequence_index",
            "model_name",
            "provider_name",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_creation_tokens",
            "reasoning_tokens",
            "duration_ms",
            "stop_reason",
            "status",
            "error_code",
        }
    ),
    "tool_call": frozenset(
        {
            "sequence_index",
            "tool_name",
            "status",
            "duration_ms",
            "error_message",
            "arguments",
        }
    ),
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

    for field_rule in entity.fields:
        errors.extend(_validate_field(field_rule, entity.target, allowed_fields))

    return errors


def _validate_field(
    rule: FieldRule,
    entity_target: str,
    allowed_fields: frozenset[str],
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    field_path = f"entities[target={entity_target}].fields[target={rule.target}]"

    # Semantic: target field must exist in the schema
    if rule.target not in allowed_fields:
        errors.append(UnknownTargetFieldError(target=rule.target, field_path=field_path))

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

    return errors
