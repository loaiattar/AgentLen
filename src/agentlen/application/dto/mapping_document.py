"""Provider and storage neutral conversion of mapping JSON documents."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping


def document_to_mapping(document: dict[str, Any], *, version: int = 1) -> Mapping:
    return Mapping(
        id=uuid4(),
        name=str(document.get("name", "mapping")),
        version=version,
        source_format=str(document["source_format"]),
        entities=tuple(
            EntityMapping(
                target=str(entity["target"]),
                natural_key=tuple(entity.get("natural_key", ())),
                iterate=entity.get("iterate"),
                parent=entity.get("parent"),
                fields=tuple(
                    FieldRule(
                        target=str(rule["target"]),
                        source=str(rule["source"]),
                        required=bool(rule.get("required", False)),
                        operators=tuple(rule.get("operators", ())),
                    )
                    for rule in entity.get("fields", ())
                ),
            )
            for entity in document.get("entities", ())
        ),
    )


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
