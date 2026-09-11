"""Mapping <-> JSON document.

A mapping is stored as a JSONB document because that is what it is: a
configuration authored by a model or a human, versioned, and applied by the
engine (MAPPING_CONTRACT.md §2). Exploding it into tables would buy nothing —
nothing ever queries inside it — and would make round-tripping lossy.

The conversion is explicit rather than reflective so an unknown key in a stored
document is a decision, not a surprise.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping


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
                        "operators": [dict(op) for op in rule.operators],
                    }
                    for rule in entity.fields
                ],
            }
            for entity in mapping.entities
        ],
    }


def document_to_mapping(document: dict[str, Any], *, name: str, version: int) -> Mapping:
    return Mapping(
        # Identity of a stored mapping is its row id; the entity's UUID is not
        # persisted, so a fresh one is minted here (ADR-012).
        id=uuid4(),
        name=name,
        version=version,
        source_format=document["source_format"],
        entities=tuple(
            EntityMapping(
                target=entity["target"],
                natural_key=tuple(entity.get("natural_key", ())),
                iterate=entity.get("iterate"),
                parent=entity.get("parent"),
                fields=tuple(
                    FieldRule(
                        target=rule["target"],
                        source=rule["source"],
                        required=rule.get("required", False),
                        operators=tuple(rule.get("operators", ())),
                    )
                    for rule in entity.get("fields", ())
                ),
            )
            for entity in document.get("entities", ())
        ),
    )
