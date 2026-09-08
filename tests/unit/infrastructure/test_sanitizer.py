"""Nothing leaves this machine unredacted.

The fake credentials below are assembled from parts rather than written as
literals, so the repository's own secret scanner does not flag its own tests.
"""

from __future__ import annotations

import pytest

from agentlen.infrastructure.ai.sanitizer import (
    DEFAULT_MAX_RECORDS,
    TRUNCATION_MARKER,
    sanitize_samples,
    sanitize_value,
)

FAKE_ANTHROPIC_KEY = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8"
FAKE_GITHUB_TOKEN = "ghp_" + "0123456789abcdefghij"
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
FAKE_SLACK_TOKEN = "xoxb-" + "111111111111-abcdefghij"


# ── Credentials ────────────────────────────────────────────────────────────────


def test_anthropic_key_is_redacted() -> None:
    record = {"command": f"export ANTHROPIC_API_KEY={FAKE_ANTHROPIC_KEY}"}

    [out] = sanitize_samples([record])

    assert FAKE_ANTHROPIC_KEY not in out["command"]
    assert "[REDACTED_API_KEY]" in out["command"]
    # The surrounding text survives: the analyzer still sees it is an export.
    assert out["command"].startswith("export ANTHROPIC_API_KEY=")


@pytest.mark.parametrize(
    ("secret", "marker"),
    [
        (FAKE_GITHUB_TOKEN, "[REDACTED_TOKEN]"),
        (FAKE_AWS_KEY, "[REDACTED_AWS_KEY]"),
        (FAKE_SLACK_TOKEN, "[REDACTED_TOKEN]"),
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
    [out] = sanitize_samples([{"author": "someone@example.com"}])

    assert out["author"] == "[REDACTED_EMAIL]"


def test_private_key_header_is_redacted() -> None:
    [out] = sanitize_samples([{"blob": "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."}])

    assert "PRIVATE KEY" not in out["blob"]
    assert "[REDACTED_PRIVATE_KEY]" in out["blob"]


# ── Absolute paths ─────────────────────────────────────────────────────────────


def test_posix_home_path_is_redacted_and_structure_is_unchanged() -> None:
    record = {
        "cwd": "/home/loai/projets/secret/",
        "nested": {"file": "/home/loai/projets/secret/main.py"},
        "line": 42,
    }

    [out] = sanitize_samples([record])

    assert "loai" not in out["cwd"]
    assert out["cwd"] == "/home/[USER]/projets/secret/"
    assert out["nested"]["file"] == "/home/[USER]/projets/secret/main.py"
    # Same keys, same nesting, same types — only the content moved.
    assert out.keys() == record.keys()
    assert out["nested"].keys() == record["nested"].keys()
    assert out["line"] == 42


def test_windows_home_path_is_redacted() -> None:
    [out] = sanitize_samples([{"cwd": r"C:\Users\shadow\Documents\AgentLen"}])

    assert "shadow" not in out["cwd"]
    assert out["cwd"] == r"C:\Users\[USER]\Documents\AgentLen"


# ── Length budget ──────────────────────────────────────────────────────────────


def test_long_value_is_truncated_to_the_budget() -> None:
    [out] = sanitize_samples([{"stdout": "x" * 10_000}], max_value_length=200)

    assert len(out["stdout"]) == 200
    assert out["stdout"].endswith(TRUNCATION_MARKER)


def test_value_within_budget_is_untouched() -> None:
    [out] = sanitize_samples([{"stdout": "short"}], max_value_length=200)

    assert out["stdout"] == "short"


def test_secret_is_redacted_even_when_it_would_be_truncated_away() -> None:
    """Truncation is not redaction.

    A key sitting inside the first 200 characters would still ship if we
    truncated first and never looked at what we kept.
    """
    record = {"log": f"{FAKE_ANTHROPIC_KEY} " + "y" * 10_000}

    [out] = sanitize_samples([record], max_value_length=50)

    assert FAKE_ANTHROPIC_KEY not in out["log"]


# ── Record budget ──────────────────────────────────────────────────────────────


def test_record_count_is_capped() -> None:
    records = [{"i": i} for i in range(500)]

    out = sanitize_samples(records, max_records=10)

    assert len(out) == 10
    assert out[0]["i"] == 0


def test_default_record_cap() -> None:
    out = sanitize_samples([{"i": i} for i in range(500)])

    assert len(out) == DEFAULT_MAX_RECORDS


# ── Shape and types ────────────────────────────────────────────────────────────


def test_types_and_shape_survive() -> None:
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
    assert isinstance(out["tags"], list)


def test_keys_are_never_rewritten() -> None:
    """The analyzer maps on field names. Redacting them would defeat the point."""
    [out] = sanitize_samples([{"user@example.com": "value"}])

    assert "user@example.com" in out


def test_input_is_not_mutated() -> None:
    record = {"cwd": "/home/loai/x"}

    sanitize_samples([record])

    assert record["cwd"] == "/home/loai/x"


def test_pathological_nesting_is_bounded() -> None:
    node: dict[str, object] = {"leaf": "value"}
    for _ in range(60):
        node = {"child": node}

    [out] = sanitize_samples([node])

    assert out is not None  # did not blow the stack


# ── Guard rails ────────────────────────────────────────────────────────────────


def test_empty_input() -> None:
    assert sanitize_samples([]) == []


@pytest.mark.parametrize(("records", "length"), [(-1, 200), (10, 0)])
def test_invalid_budgets_are_refused(records: int, length: int) -> None:
    with pytest.raises(ValueError):
        sanitize_samples([{"a": "b"}], max_records=records, max_value_length=length)


def test_sanitize_value_is_usable_on_its_own() -> None:
    assert sanitize_value(f"key={FAKE_ANTHROPIC_KEY}") == "key=[REDACTED_API_KEY]"
