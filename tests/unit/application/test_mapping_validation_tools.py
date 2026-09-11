"""The tool executor answers a malformed call; it never raises (#152).

The model writes every argument. A branch that raised failed the whole proposal
with a 500, where an answer lets the model correct its call.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentlen.application.use_cases.propose_mapping import MappingValidationTools
from agentlen.domain.model.profile import FieldProfile, FileProfile

EXAMPLES = tuple(f"value-{i}" for i in range(12))
RULE = {"target": "external_id", "source": "$.x"}


def tools() -> MappingValidationTools:
    field = FieldProfile(path="$.x", types=("string",), null_ratio=0, examples=EXAMPLES)
    return MappingValidationTools(
        FileProfile(file_id=1, format="jsonl", record_count=1, sampled_records=1, fields=(field,))
    )


def document(**entity: Any) -> dict[str, Any]:
    session = {"target": "session", "natural_key": ["external_id"], "fields": [RULE]}
    return {"name": "m", "source_format": "jsonl", "entities": [{**session, **entity}]}


@pytest.mark.parametrize("arguments", [["$.x"], "$.x", 42, None])
@pytest.mark.parametrize(
    "tool", ["get_target_schema", "get_field_profile", "get_sample_values", "validate_mapping"]
)
async def test_arguments_that_are_not_an_object_are_an_error(tool: str, arguments: Any) -> None:
    """What OpenAI-compatible hosts pass through when a model sends `[...]`."""
    answer = await tools().execute(tool, arguments)

    assert answer == {"error": "Tool arguments must be a JSON object."}


@pytest.mark.parametrize("limit", ["ten", "", [], {}, -1, "-2", True, float("inf"), float("nan")])
async def test_a_limit_that_is_not_a_count_is_an_error(limit: Any) -> None:
    """`int("ten")` raised; `examples[:-1]` answered eleven values for "-1"."""
    answer = await tools().execute("get_sample_values", {"path": "$.x", "limit": limit})

    assert answer == {"error": "limit must be an integer from 0 to 10."}


@pytest.mark.parametrize(
    ("arguments", "count"),
    [
        ({"path": "$.x"}, 3),
        ({"path": "$.x", "limit": None}, 3),
        ({"path": "$.x", "limit": 0}, 0),
        ({"path": "$.x", "limit": "5"}, 5),
        ({"path": "$.x", "limit": 50}, 10),
    ],
)
async def test_a_usable_limit_is_honoured_and_capped(arguments: dict[str, Any], count: int) -> None:
    answer = await tools().execute("get_sample_values", arguments)

    assert answer == {"values": list(EXAMPLES[:count])}


@pytest.mark.parametrize(
    ("mapping", "where"),
    [
        ("x", "mapping"),
        (["x"], "mapping"),
        (None, "mapping"),
        ({"source_format": "jsonl", "entities": "x"}, "entities"),
        ({"source_format": "jsonl", "entities": ["x"]}, "entities[0]"),
        (document(fields="x"), "entities[0].fields"),
        (document(fields=["x"]), "entities[0].fields[0]"),
        (document(natural_key="external_id"), "entities[0].natural_key"),
        (document(iterate=["$.calls"]), "entities[0].iterate"),
        (document(parent="session"), "entities[0].parent"),
        (document(fields=[{**RULE, "operators": "trim"}]), "entities[0].fields[0].operators"),
        (document(fields=[{**RULE, "operators": ["trim"]}]), "entities[0].fields[0].operators[0]"),
    ],
)
async def test_a_mapping_of_the_wrong_shape_is_reported_not_raised(
    mapping: Any, where: str
) -> None:
    """`{"mapping": "x"}` reached `"x".get(...)`, an `AttributeError` nothing caught."""
    answer = await tools().execute("validate_mapping", {"mapping": mapping})

    assert answer["valid"] is False
    [error] = answer["errors"]
    assert error["field_path"] == "mapping"
    assert error["message"].startswith(f"{where} must be "), error["message"]


async def test_a_well_shaped_mapping_still_validates() -> None:
    answer = await tools().execute("validate_mapping", {"mapping": document()})

    assert answer == {"valid": True, "errors": []}
