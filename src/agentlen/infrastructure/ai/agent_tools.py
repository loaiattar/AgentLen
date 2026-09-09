"""The five tools the import agent may call (AGENT.md §5).

Declared once, provider-neutral. Each adapter converts this list into whatever
its API expects — Anthropic's `tool_use` blocks, OpenAI's `function` objects —
so the *set* of tools cannot drift between providers. A tool available to Claude
and missing from GPT would make the two runs incomparable, which is exactly what
issue #22 has to compare.

The whitelist lives in `ImportAgentToolExecutor`: anything not in it is refused
there, so a model inventing a sixth tool gets an error rather than an effect.
"""

from __future__ import annotations

from typing import Any

TOOL_NAMES = (
    "get_target_schema",
    "get_field_profile",
    "get_sample_values",
    "validate_mapping",
    "preview_import",
)

#: Provider-neutral definitions: name, description, JSON Schema for the input.
IMPORT_AGENT_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "get_target_schema",
        "description": (
            "Return the AgentLen target entities and their fields. Call this "
            "before proposing any mapping: a field that is not in this schema "
            "will be rejected by the validator."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_field_profile",
        "description": (
            "Return detailed statistics for one source field: observed types, "
            "null ratio, distinct ratio, min and max. Use it to decide whether "
            "a field can serve as a natural key."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "JSONPath, e.g. $.usage.input_tokens"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_sample_values",
        "description": (
            "Return a few real, redacted values for one field, to settle an "
            "ambiguity the statistics cannot — seconds versus milliseconds, for "
            "instance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer", "description": "At most 10."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "validate_mapping",
        "description": (
            "Validate a complete mapping document. Returns the full list of "
            "errors with their codes and field paths. Call this before "
            "answering: an invalid mapping will be refused anyway."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"mapping": {"type": "object"}},
            "required": ["mapping"],
        },
    },
    {
        "name": "preview_import",
        "description": (
            "Dry-run the mapping over a few records and report what it would "
            "produce and what it would reject. Writes nothing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mapping": {"type": "object"},
                "sample_size": {"type": "integer"},
            },
            "required": ["mapping"],
        },
    },
)


def to_anthropic(tools: tuple[dict[str, Any], ...] = IMPORT_AGENT_TOOLS) -> list[dict[str, Any]]:
    """Anthropic takes the definitions almost verbatim."""
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["input_schema"],
        }
        for tool in tools
    ]


def to_openai(tools: tuple[dict[str, Any], ...] = IMPORT_AGENT_TOOLS) -> list[dict[str, Any]]:
    """OpenAI wraps each one in a `function` object and calls the schema
    `parameters` instead of `input_schema`."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tools
    ]
