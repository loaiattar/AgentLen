"""Provider and storage neutral conversion of mapping JSON documents."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping


def document_to_mapping(document: dict[str, Any], *, version: int = 1) -> Mapping:
    """Build a `Mapping` from its JSON document, checking its shape on the way.

    The document can come straight from a model: the `validate_mapping` tool and
    the final answer both pass through here, so no level of it is assumed to have
    the type the contract gives it. `"x".get(...)` used to raise `AttributeError`,
    which no caller caught, and the proposal failed with a 500 (#152). A wrong
    shape is a `TypeError` naming where it is; a missing key is still a
    `KeyError`. Callers turn both into an answer.
    """
    document = _object(document, "mapping")
    return Mapping(
        id=uuid4(),
        name=str(document.get("name", "mapping")),
        version=version,
        source_format=str(document["source_format"]),
        entities=tuple(
            _entity(entity, f"entities[{i}]")
            for i, entity in enumerate(_list(document.get("entities", ()), "entities"))
        ),
    )


def _entity(value: Any, where: str) -> EntityMapping:
    entity = _object(value, where)
    iterate = entity.get("iterate")
    if iterate is not None and not isinstance(iterate, str):
        raise TypeError(f"{where}.iterate must be a string, got {type(iterate).__name__}")
    parent = entity.get("parent")
    return EntityMapping(
        target=str(entity["target"]),
        natural_key=tuple(
            str(key) for key in _list(entity.get("natural_key", ()), f"{where}.natural_key")
        ),
        iterate=iterate,
        parent=None if parent is None else _object(parent, f"{where}.parent"),
        fields=tuple(
            _rule(rule, f"{where}.fields[{j}]")
            for j, rule in enumerate(_list(entity.get("fields", ()), f"{where}.fields"))
        ),
    )


def _rule(value: Any, where: str) -> FieldRule:
    rule = _object(value, where)
    operators = _list(rule.get("operators", ()), f"{where}.operators")
    return FieldRule(
        target=str(rule["target"]),
        source=str(rule["source"]),
        required=bool(rule.get("required", False)),
        operators=tuple(
            _object(operator, f"{where}.operators[{k}]") for k, operator in enumerate(operators)
        ),
    )


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object, got {type(value).__name__}")
    return value


def _list(value: Any, where: str) -> list[Any] | tuple[Any, ...]:
    if not isinstance(value, list | tuple):
        raise TypeError(f"{where} must be a list, got {type(value).__name__}")
    return value


def mapping_to_document(mapping: Mapping) -> dict[str, Any]:
    return {
        "mapping_version": "1.0",
        "name": mapping.name,
        "source_format": mapping.source_format,
        "entities": [
            {
                "target": entity.target,
                "natural_key": list(entity.natural_key),
                "iterate": entity.iterate,
                "parent": entity.parent,
                "fields": [
                    {
                        "target": rule.target,
                        "source": rule.source,
                        "required": rule.required,
                        "operators": [dict(operator) for operator in rule.operators],
                    }
                    for rule in entity.fields
                ],
            }
            for entity in mapping.entities
        ],
    }
