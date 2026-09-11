"""Business rules for e-mail and password format (domain/services/credentials.py)."""

from __future__ import annotations

import pytest

from agentlen.domain.errors import InvalidEmailError, WeakPasswordError
from agentlen.domain.services.credentials import normalize_email, validate_password_strength


def test_normalize_email_trims_and_lowercases() -> None:
    assert normalize_email("  Alice@Example.COM  ") == "alice@example.com"


@pytest.mark.parametrize(
    "invalid",
    ["not-an-email", "missing-domain@", "@missing-local.com", "no-at-sign.com", "   ", ""],
)
def test_normalize_email_rejects_malformed_addresses(invalid: str) -> None:
    with pytest.raises(InvalidEmailError):
        normalize_email(invalid)


def test_normalize_email_error_carries_the_field_path() -> None:
    with pytest.raises(InvalidEmailError) as exc_info:
        normalize_email("not-an-email")
    assert exc_info.value.code == "INVALID_EMAIL"
    assert exc_info.value.field_path == "email"


def test_validate_password_strength_accepts_a_reasonable_password() -> None:
    validate_password_strength("a-strong-passphrase")  # does not raise


def test_validate_password_strength_rejects_too_short() -> None:
    with pytest.raises(WeakPasswordError) as exc_info:
        validate_password_strength("short")
    assert exc_info.value.code == "WEAK_PASSWORD"


def test_validate_password_strength_rejects_too_long() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password_strength("x" * 73)
