"""Nothing leaves this machine unredacted.

Three axes, deliberately: what the sanitizer **catches**, what it must **leave
alone**, and what it must not **damage** on the way through. The first review of
this module found four gaps, and every one of them was a missing test of the
second or third kind.

The fake credentials below are assembled from parts rather than written as
literals, so the repository's own secret scanner does not flag its own tests.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from decimal import Decimal

import pytest

from agentlen.infrastructure.ai.sanitizer import (
    DEFAULT_MAX_LIST_ITEMS,
    DEFAULT_MAX_RECORDS,
    TRUNCATION_MARKER,
    sanitize_key,
    sanitize_samples,
    sanitize_value,
)

FAKE_ANTHROPIC_KEY = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8"
FAKE_GITHUB_TOKEN = "ghp_" + "0123456789abcdefghij"
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
FAKE_SLACK_TOKEN = "xoxb-" + "111111111111-abcdefghij"
FAKE_JWT = "eyJ" + "hbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "dBjftJeZ4CVPmB92K27u"


# ── What it catches ────────────────────────────────────────────────────────────


def test_anthropic_key_is_redacted() -> None:
    [out] = sanitize_samples([{"command": f"export ANTHROPIC_API_KEY={FAKE_ANTHROPIC_KEY}"}])

    assert FAKE_ANTHROPIC_KEY not in out["command"]
    assert "[REDACTED" in out["command"]
    # The field name survives: the analyzer still sees what kind of line this is.
    assert out["command"].startswith("export ANTHROPIC_API_KEY")


@pytest.mark.parametrize(
    ("secret", "marker"),
    [
        (FAKE_GITHUB_TOKEN, "[REDACTED_TOKEN]"),
        (FAKE_AWS_KEY, "[REDACTED_AWS_KEY]"),
        (FAKE_SLACK_TOKEN, "[REDACTED_TOKEN]"),
        (FAKE_JWT, "[REDACTED_JWT]"),
    ],
)
def test_common_credential_shapes_are_redacted(secret: str, marker: str) -> None:
    [out] = sanitize_samples([{"value": f"leaked {secret} here"}])

    assert secret not in out["value"]
    assert marker in out["value"]


def test_authorization_header_is_redacted() -> None:
    [out] = sanitize_samples([{"headers": "Authorization: Bearer abcdef0123456789"}])

    assert "abcdef0123456789" not in out["headers"]
    assert out["headers"] == "Authorization: Bearer [REDACTED]"


def test_email_is_redacted() -> None:
    assert sanitize_samples([{"author": "someone@example.com"}])[0]["author"] == "[REDACTED_EMAIL]"


def test_whole_private_key_block_is_redacted_not_only_its_header() -> None:
    """The header alone is not the secret. The base64 body is."""
    body = "MIIEpAIBAAKCAQEA7xQZ9K2mNvBcXwFhTgY3pLsRdEuVwQaZnMkJhGfDcBaXyWvUt"
    blob = f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----"

    [out] = sanitize_samples([{"blob": blob}])

    assert body not in out["blob"]
    assert "PRIVATE KEY" not in out["blob"]
    assert out["blob"] == "[REDACTED_PRIVATE_KEY]"


def test_dangling_private_key_header_still_redacted() -> None:
    """A block truncated upstream has no END marker. Redact what we can see."""
    [out] = sanitize_samples([{"blob": "-----BEGIN OPENSSH PRIVATE KEY-----\nMIIEpAIB"}])

    assert "PRIVATE KEY" not in out["blob"]


def test_connection_string_password_is_redacted() -> None:
    """The commonest shape of a secret in a trace: a printed .env."""
    [out] = sanitize_samples([{"env": "postgresql://admin:hunter2@localhost:5432/agentlen"}])

    assert "hunter2" not in out["env"]
    # Scheme, user and host survive — they are shape, not identity.
    assert out["env"] == "postgresql://admin:[REDACTED_PASSWORD]@localhost:5432/agentlen"


@pytest.mark.parametrize(
    "line",
    [
        "API_KEY=s3cr3tvalue123",
        "password: hunter2hunter2",
        "AUTH_TOKEN = abcdefghijkl",
        "aws_secret_access_key=wJalrXUtnFEMIK7MDENGbPxRfiCY",
    ],
)
def test_assignment_form_keeps_the_name_and_drops_the_value(line: str) -> None:
    [out] = sanitize_samples([{"line": line}])

    assert "[REDACTED_SECRET]" in out["line"]
    # The name is the part the analyzer needs.
    assert out["line"].split("=")[0].split(":")[0] == line.split("=")[0].split(":")[0]


# ── What it must leave alone ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "This needs basic configuration values",
        "Use bearer authentication for this endpoint",
        "The secret sauce is patience",
        "token count exceeded",
        "https://github.com/loaiattar/AgentLen",
        "SELECT * FROM session WHERE started_at > now()",
        "duration_ms",
        "claude-code",
    ],
)
def test_ordinary_prose_and_identifiers_survive(text: str) -> None:
    """Traces are full of English. Eating words costs the analyzer real signal."""
    assert sanitize_samples([{"t": text}])[0]["t"] == text


def test_ordinary_field_names_are_not_rewritten() -> None:
    record = {"session_id": 1, "input_tokens": 2, "tool_name": "Bash", "password_hint": None}

    [out] = sanitize_samples([record])

    assert list(out) == list(record)


# ── What it must not damage ────────────────────────────────────────────────────


def test_posix_home_path_keeps_its_platform() -> None:
    """/Users/ is a macOS trace and /home/ a Linux one. That is mappable shape."""
    [out] = sanitize_samples([{"mac": "/Users/alice/Documents/x", "linux": "/home/bob/proj"}])

    assert out["mac"] == "/Users/[USER]/Documents/x"
    assert out["linux"] == "/home/[USER]/proj"


def test_windows_path_keeps_its_drive_letter() -> None:
    [out] = sanitize_samples([{"c": r"C:\Users\shadow\Documents", "d": r"D:\Users\bob\proj"}])

    assert out["c"] == r"C:\Users\[USER]\Documents"
    assert out["d"] == r"D:\Users\[USER]\proj"


def test_structure_and_types_survive() -> None:
    record = {
        "count": 3,
        "ratio": 0.5,
        "ok": True,
        "missing": None,
        "tags": ["a", "b"],
        "deep": {"level": {"value": "plain"}},
    }

    [out] = sanitize_samples([record])

    assert out == record
    assert isinstance(out["count"], int)
    assert isinstance(out["ok"], bool)
    assert out["missing"] is None


def test_input_is_not_mutated() -> None:
    record = {"cwd": "/home/loai/x"}

    sanitize_samples([record])

    assert record["cwd"] == "/home/loai/x"


# ── Keys are data too ──────────────────────────────────────────────────────────


def test_secrets_used_as_keys_are_redacted() -> None:
    """A file map or an environment dump puts paths and keys in key position."""
    [out] = sanitize_samples([{"/home/loai/projets/secret/notes.md": "ok"}])

    assert "loai" not in json.dumps(out)
    assert "/home/[USER]/projets/secret/notes.md" in out


def test_key_redaction_never_drops_an_entry() -> None:
    """Two distinct keys can redact to the same string. Cardinality must hold."""
    record = {"/home/alice/x": 1, "/home/bob/x": 2}

    [out] = sanitize_samples([record])

    assert len(out) == 2


def test_sanitize_key_does_not_truncate() -> None:
    """Truncating keys would make distinct keys collide."""
    long_key = "a" * 5_000

    assert sanitize_key(long_key) == long_key


# ── Non-string scalars ─────────────────────────────────────────────────────────


def test_bytes_never_leak_and_never_break_json() -> None:
    """Polars hands back bytes on a binary column."""
    [out] = sanitize_samples([{"blob": b"sk-ant-api03-AAAABBBBCCCCDDDD"}])

    assert "sk-ant" not in json.dumps(out)
    assert out["blob"].startswith("[BINARY:")


@pytest.mark.parametrize(
    "value",
    [dt.datetime(2026, 9, 8, 12, 0, tzinfo=dt.UTC), dt.date(2026, 9, 8), Decimal("1.25")],
)
def test_typed_scalars_become_json_serialisable(value: object) -> None:
    """These would otherwise raise when the prompt is assembled."""
    out = sanitize_samples([{"v": value}])

    json.dumps(out)  # must not raise


def test_every_output_is_json_serialisable() -> None:
    record = {"b": b"x", "d": dt.date(2026, 1, 1), "n": Decimal("2"), "s": "ok", "i": 1}

    json.dumps(sanitize_samples([record]))


# ── Budgets ────────────────────────────────────────────────────────────────────


def test_long_value_is_truncated_to_the_budget() -> None:
    [out] = sanitize_samples([{"stdout": "x" * 10_000}], max_value_length=200)

    assert len(out["stdout"]) == 200
    assert out["stdout"].endswith(TRUNCATION_MARKER)


def test_value_within_budget_is_untouched() -> None:
    assert sanitize_samples([{"s": "short"}], max_value_length=200)[0]["s"] == "short"


def test_secret_is_redacted_even_when_it_would_be_truncated_away() -> None:
    """Truncation is not redaction."""
    record = {"log": f"{FAKE_ANTHROPIC_KEY} " + "y" * 10_000}

    [out] = sanitize_samples([record], max_value_length=50)

    assert FAKE_ANTHROPIC_KEY not in out["log"]


def test_record_count_is_capped() -> None:
    out = sanitize_samples([{"i": i} for i in range(500)], max_records=10)

    assert len(out) == 10
    assert out[0]["i"] == 0


def test_default_record_cap_matches_the_documented_contract() -> None:
    """AGENT.md states 50."""
    assert DEFAULT_MAX_RECORDS == 50
    assert len(sanitize_samples([{"i": i} for i in range(500)])) == 50


def test_wide_lists_are_capped() -> None:
    """max_records bounds how many records travel, not how wide one is."""
    [out] = sanitize_samples([{"items": list(range(100_000))}])

    assert len(out["items"]) == DEFAULT_MAX_LIST_ITEMS


def test_pathological_nesting_is_bounded() -> None:
    node: dict[str, object] = {"leaf": "value"}
    for _ in range(60):
        node = {"child": node}

    assert sanitize_samples([node])  # did not blow the stack


# ── Performance is a correctness property here ─────────────────────────────────


def test_a_large_value_without_secrets_is_still_fast() -> None:
    """Regression guard for the quadratic email pattern.

    Under `re`, this exact input took 52 seconds — a 200 KB value with no `@`
    in it at all, which is an ordinary logged file. Generous bound: the real
    figure is well under a millisecond.
    """
    started = time.perf_counter()
    sanitize_samples([{"content": "x" * 200_000}], max_value_length=200)

    assert time.perf_counter() - started < 2.0


# ── Guard rails ────────────────────────────────────────────────────────────────


def test_empty_input() -> None:
    assert sanitize_samples([]) == []


@pytest.mark.parametrize(
    ("records", "length", "items"),
    [(-1, 200, 20), (10, 0, 20), (10, 200, 0)],
)
def test_invalid_budgets_are_refused(records: int, length: int, items: int) -> None:
    with pytest.raises(ValueError):
        sanitize_samples(
            [{"a": "b"}], max_records=records, max_value_length=length, max_list_items=items
        )


def test_sanitize_value_refuses_an_invalid_budget() -> None:
    """It is exported, so it needs the same guard as the entry point.

    A negative budget used to take the marker branch and slice from the end,
    silently returning the value minus its last characters.
    """
    with pytest.raises(ValueError):
        sanitize_value("hello world", -3)


def test_sanitize_value_is_usable_on_its_own() -> None:
    assert sanitize_value(f"key={FAKE_ANTHROPIC_KEY}") == "key=[REDACTED_API_KEY]"
