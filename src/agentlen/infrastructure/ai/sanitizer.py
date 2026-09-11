"""Redaction of sample records before they ever leave the machine.

Agent traces are full of things that must not reach a third-party provider:
API keys pasted into a shell command, bearer tokens in a captured HTTP call,
connection strings from a printed `.env`, the author's email address, absolute
paths that carry their username.

The analyzer needs the *shape* of the data to propose a mapping — which keys
exist, how they nest, what types they hold. It does not need the values. So
this module keeps the structure and rewrites the content.

Nothing here talks to a provider. It is deliberately a pure function over
plain dicts: no I/O, no configuration lookup, no network. That is what makes
it testable, and what makes it impossible for an adapter to "forget" it while
still passing review — see ARCHITECTURE §10 and MAPPING_CONTRACT.md §5.

**Why RE2 and not `re`.** Redaction runs before truncation, so every pattern is
applied to unbounded strings taken straight from a trace file. Under `re`, the
email pattern was quadratic: `[A-Za-z0-9._%+-]+` consumed the whole string,
failed on the missing `@`, backed off one character and started again. A 200 KB
value with no `@` in it at all — an ordinary logged file, a large JSON response
— took **52 seconds**. RE2 has no backtracking by construction, so the same
input takes 0.4 ms and no future edit to these patterns can reintroduce the
problem. The cost is no lookahead and no backreferences; the checks that would
have needed them live in the replacement callables instead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, NewType

import re2

from agentlen.domain.model.profile import FileProfile

__all__ = [
    "DEFAULT_MAX_LIST_ITEMS",
    "DEFAULT_MAX_RECORDS",
    "DEFAULT_MAX_VALUE_LENGTH",
    "TRUNCATION_MARKER",
    "sanitize_key",
    "sanitize_samples",
    "sanitize_value",
    "SanitizedSamples",
    "ProfileExampleSanitizer",
]

# The prompt builder asks for this type, and only sanitize_samples can produce
# it. Handing it raw records is a type error rather than a review comment —
# which is what the module docstring's "impossible to forget" is meant to mean.
SanitizedSamples = NewType("SanitizedSamples", list[dict[str, Any]])


class ProfileExampleSanitizer:
    """Defense in depth for profiles supplied by any profiler adapter.

    **`path` is deliberately left alone.** Everywhere else in this module a key
    is data; here it is not. `FieldProfile.path` is the JSONPath the analyzer
    copies verbatim into `FieldRule.source`, and the rules below fire on real
    path text: `$["/home/alice/project"]` becomes `$["/home/[USER]/project"]`,
    `$["alice@example.com"]` becomes `$["[REDACTED_EMAIL]"]`. The saved mapping
    would then point at a path that does not exist in the file, and the field
    would resolve to null at import time with no validation error to show for
    it. The values reachable through that path — `min_value`, `max_value`,
    `examples` — are what has to be redacted, and they are.
    """

    def sanitize(self, profile: FileProfile) -> FileProfile:
        return replace(
            profile,
            fields=tuple(
                replace(
                    field,
                    min_value=(
                        sanitize_value(field.min_value)
                        if isinstance(field.min_value, str)
                        else field.min_value
                    ),
                    max_value=(
                        sanitize_value(field.max_value)
                        if isinstance(field.max_value, str)
                        else field.max_value
                    ),
                    examples=tuple(sanitize_value(value) for value in field.examples),
                )
                for field in profile.fields
            ),
        )


# AGENT.md §"Taille max de l'échantillon envoyé au LLM" states 50.
DEFAULT_MAX_RECORDS = 50
DEFAULT_MAX_VALUE_LENGTH = 200
# `max_records` bounds how many records travel, not how wide one record is. A
# single trace row holding a 100 000-element array would otherwise produce a
# multi-megabyte prompt. Volume belongs in the profile, not in the sample.
DEFAULT_MAX_LIST_ITEMS = 20
TRUNCATION_MARKER = "…[truncated]"

# Guards against a hand-crafted trace nesting itself thousands of levels deep.
_MAX_DEPTH = 20

# An auth token with no digit in it is almost certainly an English word, unless
# it is long enough to be base64. Below this length, a digitless match is prose.
_CREDENTIAL_MIN_OPAQUE_LENGTH = 24

_Replacer = Callable[[Any], str]


def _constant(literal: str) -> _Replacer:
    """A replacement that ignores the match and returns a fixed string."""
    return lambda _match: literal


def _keep_prefix(suffix: str) -> _Replacer:
    """Keep capture group 1, replace the rest.

    Used for paths and connection strings, where the prefix is shape the
    analyzer may legitimately map on — the platform, the drive letter, the
    scheme — and only the tail is identity.
    """
    return lambda match: match.group(1) + suffix


def _credential_after(scheme: str) -> _Replacer:
    """Redact an auth token, but only when it actually looks like one.

    `bearer\\s+[A-Za-z0-9._-]{8,}` matches "bearer authentication" as happily as
    it matches a real token, and agent traces are full of ordinary English. A
    token carries digits or is long; a word does neither.
    """

    def replace(match: Any) -> str:
        token = match.group(1)
        has_digit = any(character.isdigit() for character in token)
        if has_digit or len(token) >= _CREDENTIAL_MIN_OPAQUE_LENGTH:
            return f"{scheme} [REDACTED]"
        return str(match.group(0))

    return replace


def _redact_credentials_assignment(match: Any) -> str:
    """Keep the field name, drop the value.

    `API_KEY=…`, `PASSWORD: …`, `token = …` — the assignment form is how a
    secret usually appears in a shell trace, and the name is exactly the part
    the analyzer needs to see.
    """
    return f"{match.group(1)}{match.group(2)}[REDACTED_SECRET]"


def _redact_email_unless_vcs_remote(match: Any) -> str:
    """`git@github.com:acme/api.git` is a repository URL, not an address.

    The email rule matched the `git@github.com` inside it and blanked the whole
    value, so every example the analyzer saw for a remote read
    `[REDACTED_EMAIL]` — and `repository_url` is a target field it is expected
    to map. Keeping the shape here costs nothing: what is preserved is an
    address followed immediately by `:path/to/repo.git` or `/path/to/repo.git`
    — the SCP and `ssh://` forms of a remote, and not how a human address is
    ever written. Anything else, including an address followed by a colon in
    prose, still goes.
    """
    if match.group(1):
        return str(match.group(0))
    return "[REDACTED_EMAIL]"


def _redact_connection_password(match: Any) -> str:
    """`scheme://user:password@host` — keep scheme and user, drop the password."""
    return f"{match.group(1)}{match.group(2)}:[REDACTED_PASSWORD]@"


# Order matters. Connection strings and assignments run before the email rule,
# which would otherwise chew through `user:pass@host` and leave `user:` visible.
_VALUE_RULES: tuple[tuple[Any, _Replacer], ...] = (
    # Whole private-key block. The header-only rule below is the fallback for a
    # block that was itself truncated upstream.
    (
        re2.compile(
            r"(?s)-----BEGIN [A-Z ]{0,32}PRIVATE KEY-----.*?-----END [A-Z ]{0,32}PRIVATE KEY-----"
        ),
        _constant("[REDACTED_PRIVATE_KEY]"),
    ),
    (
        re2.compile(r"-----BEGIN [A-Z ]{0,32}PRIVATE KEY-----"),
        _constant("[REDACTED_PRIVATE_KEY]"),
    ),
    # scheme://user:password@host
    (
        re2.compile(r"([a-zA-Z][a-zA-Z0-9+.\-]{1,20}://)([^:@/\s]{1,64}):[^@/\s]{1,128}@"),
        _redact_connection_password,
    ),
    # NAME=value / NAME: value
    (
        re2.compile(
            r"(?i:(api[_-]?key|secret[a-z_]{0,12}|passwo?rd|passwd|pwd|access[_-]?key|"
            r"auth[_-]?token|token))(\s{0,4}[=:]\s{0,4})[\"']?[^\s\"',;]{8,512}"
        ),
        _redact_credentials_assignment,
    ),
    # JSON Web Tokens.
    (
        re2.compile(r"eyJ[A-Za-z0-9_-]{10,512}\.[A-Za-z0-9_-]{10,512}\.[A-Za-z0-9_-]{10,512}"),
        _constant("[REDACTED_JWT]"),
    ),
    # Anthropic, OpenAI and the wider sk-... family.
    (re2.compile(r"sk-[A-Za-z0-9_-]{8,256}"), _constant("[REDACTED_API_KEY]")),
    # GitHub: ghp_ gho_ ghu_ ghs_ ghr_, plus fine-grained tokens.
    (re2.compile(r"gh[pousr]_[A-Za-z0-9]{16,256}"), _constant("[REDACTED_TOKEN]")),
    (re2.compile(r"github_pat_[A-Za-z0-9_]{20,256}"), _constant("[REDACTED_TOKEN]")),
    # AWS access key ids, long-lived and temporary.
    (re2.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"), _constant("[REDACTED_AWS_KEY]")),
    # Google API keys.
    (re2.compile(r"AIza[A-Za-z0-9_-]{35}"), _constant("[REDACTED_API_KEY]")),
    # Slack.
    (re2.compile(r"xox[abprs]-[A-Za-z0-9-]{10,256}"), _constant("[REDACTED_TOKEN]")),
    # Authorization headers, whatever the scheme carries.
    (re2.compile(r"(?i:bearer)\s{1,4}([A-Za-z0-9._-]{8,512})"), _credential_after("Bearer")),
    (re2.compile(r"(?i:basic)\s{1,4}([A-Za-z0-9+/=]{12,512})"), _credential_after("Basic")),
    # Email addresses. RFC 5321 caps the local part at 64 octets and the domain
    # at 255, so these bounds are the specification, not a guess. The optional
    # tail is what tells an address apart from an SCP-style git remote — see
    # `_redact_email_unless_vcs_remote`.
    (
        re2.compile(
            r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}"
            r"([:/][A-Za-z0-9._/~-]{1,200}\.git)?"
        ),
        _redact_email_unless_vcs_remote,
    ),
    # Absolute home paths. The prefix is kept: /Users/ is a macOS trace and
    # /home/ a Linux one, and a mapping may legitimately care.
    (re2.compile(r"(/(?:home|Users)/)[^/\s\"']{1,64}"), _keep_prefix("[USER]")),
    (re2.compile(r"([A-Za-z]:\\Users\\)[^\\\s\"']{1,64}"), _keep_prefix("[USER]")),
)

# Keys go through the same rules. A trace often carries absolute paths or
# credentials *as* keys — a file map, an environment dump — and there the key is
# data, not structure. Ordinary field names match none of these patterns, so
# they survive untouched, which is what the analyzer needs.
_KEY_RULES = _VALUE_RULES


def _apply(rules: tuple[tuple[Any, _Replacer], ...], text: str) -> str:
    for pattern, replacement in rules:
        text = pattern.sub(replacement, text)
    return text


def sanitize_value(value: str, max_value_length: int = DEFAULT_MAX_VALUE_LENGTH) -> str:
    """Redact secrets in one string, then bound its length.

    Redaction runs first. Truncating a 10 000-character value down to 200 would
    otherwise be enough to hide a key from a reviewer while still shipping it,
    if the key happened to sit in the part we keep.
    """
    if max_value_length < 1:
        raise ValueError("max_value_length must be at least 1")

    value = _apply(_VALUE_RULES, value)

    if len(value) <= max_value_length:
        return value
    if max_value_length <= len(TRUNCATION_MARKER):
        return value[:max_value_length]
    return value[: max_value_length - len(TRUNCATION_MARKER)] + TRUNCATION_MARKER


def sanitize_key(key: str) -> str:
    """Redact a mapping key, without truncating it.

    Length-bounding a key could make two distinct keys collide, silently
    dropping an entry and changing the very structure we promise to preserve.
    """
    return _apply(_KEY_RULES, key)


def _sanitize_scalar(node: Any, max_value_length: int) -> Any:
    """Everything that is not a container.

    `int`, `float`, `bool` and `None` carry no text to leak and their type is
    itself the signal, so they pass through. Everything else is coerced to a
    string and redacted: records arrive straight from the file reader, and
    Polars hands back `bytes` on a binary column and `datetime`/`Decimal` on
    typed ones. Left alone, those would both leak and break `json.dumps` when
    the prompt is assembled.
    """
    if isinstance(node, str):
        return sanitize_value(node, max_value_length)
    if isinstance(node, bool) or node is None or isinstance(node, (int, float)):
        return node
    if isinstance(node, (bytes, bytearray, memoryview)):
        # Never decoded: a binary blob has no shape worth showing, and decoding
        # it would be a new way to leak.
        return f"[BINARY:{len(bytes(node))} bytes]"
    return sanitize_value(str(node), max_value_length)


def _sanitize(node: Any, max_value_length: int, max_list_items: int, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        return "[REDACTED_TOO_DEEP]"

    if isinstance(node, dict):
        result: dict[str, Any] = {}
        for key, item in node.items():
            clean_key = sanitize_key(key) if isinstance(key, str) else str(key)
            # Redaction can map two distinct keys onto the same string. Keeping
            # the cardinality matters more than the exact name here.
            if clean_key in result:
                suffix = 2
                while f"{clean_key}#{suffix}" in result:
                    suffix += 1
                clean_key = f"{clean_key}#{suffix}"
            result[clean_key] = _sanitize(item, max_value_length, max_list_items, depth + 1)
        return result

    if isinstance(node, (list, tuple)):
        return [
            _sanitize(item, max_value_length, max_list_items, depth + 1)
            for item in node[:max_list_items]
        ]

    return _sanitize_scalar(node, max_value_length)


def sanitize_samples(
    records: list[dict[str, Any]],
    max_records: int = DEFAULT_MAX_RECORDS,
    max_value_length: int = DEFAULT_MAX_VALUE_LENGTH,
    max_list_items: int = DEFAULT_MAX_LIST_ITEMS,
) -> SanitizedSamples:
    """Return at most ``max_records`` records, redacted and bounded.

    The input is never mutated: adapters keep working on the real records while
    only the sanitized copy travels. The result is JSON-serialisable whatever
    the reader produced.

    Args:
        records: raw sample records, straight from the file reader.
        max_records: how many records the provider is allowed to see.
        max_value_length: per-string budget, truncation marker included.
        max_list_items: per-list budget, so one wide record cannot blow up the
            prompt.
    """
    if max_records < 0:
        raise ValueError("max_records must not be negative")
    if max_value_length < 1:
        raise ValueError("max_value_length must be at least 1")
    if max_list_items < 1:
        raise ValueError("max_list_items must be at least 1")

    return SanitizedSamples(
        [_sanitize(record, max_value_length, max_list_items, 0) for record in records[:max_records]]
    )
