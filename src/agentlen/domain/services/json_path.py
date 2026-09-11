"""Path notation shared by `mapping_validator` and `TransformationEngine`.

It is the notation `PolarsFileProfiler` writes into a `FileProfile`, so a path
the agent copies from the profile is a path the engine resolves: `$` for the
record, `.name` for a plain identifier, `["name"]` for any other name (a
backslash escapes a backslash or a double quote), `[]` for each element of a
list. How `[]` reads in `iterate` and in `source`, and what is refused, is
specified in MAPPING_CONTRACT.md §2.1. Nothing is ever evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from agentlen.domain.errors import UnsupportedPathError

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_EACH_HINT = "[] reads every element of a list"
# What a path most often tries that the notation does not have.
_UNSUPPORTED = (
    ("..", "recursive descent '..' is not supported"),
    ("[?", f"filter expressions [?(...)] are not supported; {_EACH_HINT}"),
    ("[*", f"wildcards are not supported; {_EACH_HINT}"),
    (".*", f"wildcards are not supported; {_EACH_HINT}"),
    ("['", 'names are quoted with double quotes: ["name"]'),
)
_JSON_TYPES: dict[type[object], str] = {
    dict: "an object",
    list: "a list",
    str: "a string",
    bool: "a boolean",
    int: "a number",
    float: "a number",
}


@dataclass(frozen=True)
class Key:
    """`.name` or `["name"]`: the member `name` of an object."""

    name: str


@dataclass(frozen=True)
class Each:
    """`[]`: every element of a list."""


JsonPath = tuple[Key | Each, ...]


@lru_cache(maxsize=512)
def parse_path(path: str) -> JsonPath:
    """Split `path` into segments, or raise UnsupportedPathError saying why."""
    if not path.startswith("$"):
        raise UnsupportedPathError(path, "a path starts with '$' (e.g. $.session_id)")
    segments: list[Key | Each] = []
    position = 1
    while position < len(path):
        identifier = _IDENTIFIER.match(path, position + 1)
        if path[position] == "." and identifier:
            segments.append(Key(identifier.group()))
            position = identifier.end()
        elif path.startswith("[]", position):
            segments.append(Each())
            position += 2
        elif path.startswith('["', position):
            name, position = _read_quoted(path, position + 2)
            segments.append(Key(name))
        else:
            raise UnsupportedPathError(path, _why(path[position:], position))
    return tuple(segments)


def iterate_path(path: str) -> JsonPath:
    """Segments of an `iterate` path; `$.calls` reads as `$.calls[]`."""
    segments = parse_path(path)
    return segments if segments and isinstance(segments[-1], Each) else (*segments, Each())


def source_path(path: str, iterate: JsonPath | None = None) -> JsonPath:
    """Segments of a `source` path relative to the row, `iterate` prefix removed."""
    segments = parse_path(path)
    if iterate and segments[: len(iterate)] == iterate:
        segments = segments[len(iterate) :]
    if any(isinstance(segment, Each) for segment in segments):
        raise UnsupportedPathError(
            path,
            "[] in a field source is only allowed as the prefix repeating the entity's "
            "iterate path (iterate $.tools[], source $.tools[].tool_name); "
            "a field holds one value, a whole list is kept with $.tools",
        )
    return segments


def resolve(document: object, segments: JsonPath) -> object | None:
    """The value at `segments`, or None when a step is absent or not an object."""
    current = document
    for segment in segments:
        if isinstance(segment, Each) or not isinstance(current, dict):
            return None
        current = current.get(segment.name)
    return current


def resolve_rows(document: object, segments: JsonPath) -> tuple[list[object], str | None]:
    """Every element `segments` reaches, and what stood where a list or an object
    was expected. An absent or null step is not a problem: a record with no
    tool calls simply has none."""
    current: list[object] = [document]
    wrong: dict[str, None] = {}  # ordered set of explanations
    for segment in segments:
        found: list[object] = []
        for value in current:
            if isinstance(segment, Each) and isinstance(value, list):
                found.extend(value)
            elif isinstance(segment, Key) and isinstance(value, dict):
                if (child := value.get(segment.name)) is not None:
                    found.append(child)
            else:
                expected = "a list" if isinstance(segment, Each) else "an object"
                kind = _JSON_TYPES.get(
                    type(value), "null" if value is None else type(value).__name__
                )
                wrong[f"{kind} where {expected} was expected"] = None
        current = found
    return current, "; ".join(wrong) or None


def _why(rest: str, position: int) -> str:
    for start, reason in _UNSUPPORTED:
        if rest.startswith(start):
            return reason
    if re.match(r"\[[-:\d]", rest):
        return f"list indexes and slices are not supported; {_EACH_HINT}"
    if rest == ".":
        return "a path cannot end with '.'"
    return f"""unexpected {rest[0]!r} at position {position}; expected .name, ["name"] or []"""


def _read_quoted(path: str, position: int) -> tuple[str, int]:
    """Read a `["…"]` name from just after `["`; return it and the position after `"]`."""
    name: list[str] = []
    while position < len(path):
        char = path[position]
        if char == '"':
            if not path.startswith("]", position + 1):
                raise UnsupportedPathError(path, "the quoted name is not followed by ']'")
            return "".join(name), position + 2
        if char == "\\":
            position += 1
            char = path[position : position + 1]
            if char not in ("\\", '"'):
                raise UnsupportedPathError(path, "unsupported escape in a quoted name")
        name.append(char)
        position += 1
    raise UnsupportedPathError(path, "unterminated quoted name")
