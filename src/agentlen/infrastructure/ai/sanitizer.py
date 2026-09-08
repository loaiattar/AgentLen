"""Redaction of sample records before they ever leave the machine.

Agent traces are full of things that must not reach a third-party provider:
API keys pasted into a shell command, bearer tokens in a captured HTTP call,
the author's email address, absolute paths that carry their username.

The analyzer needs the *shape* of the data to propose a mapping — which keys
exist, how they nest, what types they hold. It does not need the values. So
this module keeps the structure exactly as it is and rewrites the content.

Nothing here talks to a provider. It is deliberately a pure function over
plain dicts: no I/O, no configuration lookup, no network. That is what makes
it testable, and what makes it impossible for an adapter to "forget" it while
still passing review — see ARCHITECTURE §10 and MAPPING_CONTRACT.md §5.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

__all__ = [
    "DEFAULT_MAX_RECORDS",
    "DEFAULT_MAX_VALUE_LENGTH",
    "TRUNCATION_MARKER",
    "sanitize_samples",
    "sanitize_value",
]

DEFAULT_MAX_RECORDS = 10
DEFAULT_MAX_VALUE_LENGTH = 200
TRUNCATION_MARKER = "…[truncated]"

# Guards against a hand-crafted trace nesting itself thousands of levels deep.
_MAX_DEPTH = 20

# Every pattern is anchored on a fixed prefix and uses a bounded character
# class, so none of them can backtrack catastrophically on hostile input.
_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Private key blocks — checked first: the header would otherwise survive.
    (re.compile(r"-----BEGIN (?:[A-Z ]{0,32})PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # Anthropic, OpenAI and the wider sk-... family.
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "[REDACTED_API_KEY]"),
    # GitHub: ghp_ gho_ ghu_ ghs_ ghr_, plus fine-grained tokens.
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"), "[REDACTED_TOKEN]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "[REDACTED_TOKEN]"),
    # AWS access key ids, long-lived and temporary.
    (re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"), "[REDACTED_AWS_KEY]"),
    # Google API keys.
    (re.compile(r"AIza[A-Za-z0-9_-]{35}"), "[REDACTED_API_KEY]"),
    # Slack.
    (re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"), "[REDACTED_TOKEN]"),
    # Authorization headers, whatever the scheme carries.
    (re.compile(r"(?i:bearer)\s+[A-Za-z0-9._-]{8,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i:basic)\s+[A-Za-z0-9+/=]{12,}"), "Basic [REDACTED]"),
    # Email addresses.
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}"), "[REDACTED_EMAIL]"),
    # Absolute home paths: the shape is informative, the username is not.
    (re.compile(r"/(?:home|Users)/[^/\s\"']{1,64}"), "/home/[USER]"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']{1,64}"), "C:\\Users\\[USER]"),
)


def _replace_with(literal: str) -> Callable[[re.Match[str]], str]:
    """Return a replacement callable.

    Passing a callable to ``re.sub`` means the replacement is used verbatim.
    A plain string would have its backslashes read as group references, and
    ``C:\\Users\\[USER]`` would raise ``bad escape \\U``.
    """
    return lambda _match: literal


def sanitize_value(value: str, max_value_length: int = DEFAULT_MAX_VALUE_LENGTH) -> str:
    """Redact secrets in one string, then bound its length.

    Redaction runs first: truncating a 10 000-character value down to 200
    would otherwise be enough to hide a key from the reader while still
    shipping it, if the key happened to sit in the first 200 characters.
    """
    for pattern, replacement in _REDACTIONS:
        value = pattern.sub(_replace_with(replacement), value)

    if len(value) <= max_value_length:
        return value
    if max_value_length <= len(TRUNCATION_MARKER):
        return value[:max_value_length]
    return value[: max_value_length - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def _sanitize(node: Any, max_value_length: int, depth: int) -> Any:
    """Walk the record, rewriting strings and leaving the shape untouched.

    Keys are never rewritten: the analyzer maps on field names, so renaming
    them would defeat the entire purpose of sending a sample.
    """
    if depth > _MAX_DEPTH:
        return "[REDACTED_TOO_DEEP]"
    if isinstance(node, str):
        return sanitize_value(node, max_value_length)
    if isinstance(node, dict):
        return {key: _sanitize(item, max_value_length, depth + 1) for key, item in node.items()}
    if isinstance(node, (list, tuple)):
        return [_sanitize(item, max_value_length, depth + 1) for item in node]
    # int, float, bool, None: no content to leak, and the type is the signal.
    return node


def sanitize_samples(
    records: list[dict[str, Any]],
    max_records: int = DEFAULT_MAX_RECORDS,
    max_value_length: int = DEFAULT_MAX_VALUE_LENGTH,
) -> list[dict[str, Any]]:
    """Return at most ``max_records`` records, redacted and length-bounded.

    The input is never mutated: adapters keep working on the real records
    while only the sanitized copy travels.

    Args:
        records: raw sample records, straight from the file reader.
        max_records: how many records the provider is allowed to see.
        max_value_length: per-string budget, marker included.
    """
    if max_records < 0:
        raise ValueError("max_records must not be negative")
    if max_value_length < 1:
        raise ValueError("max_value_length must be at least 1")

    kept = records[:max_records]
    return [_sanitize(record, max_value_length, 0) for record in kept]
