"""Business rules for e-mail and password format (domain/services/credentials.py)."""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

from agentlen.domain.errors import InvalidEmailError, WeakPasswordError
from agentlen.domain.services.credentials import (
    _EMAIL_PATTERN,
    MAX_EMAIL_LENGTH,
    normalize_email,
    validate_password_strength,
)

#: Adversarial shapes of about 50 000 characters, in order: a second "@", a
#: trailing dot, no dot, no "@". Only the first one made the previous pattern backtrack
#: quadratically (0.83 s at 16 003 characters); the others guard the new one.
ADVERSARIAL_EMAILS = [
    "a@" + "a." * 25_000 + "@",
    "a@" + "a." * 25_000,
    "a@" + "a" * 50_000,
    "a" * 50_000,
]

#: Generous next to the ~3 ms a linear match takes, tight next to the seconds a
#: quadratic one takes: the test cannot pass by luck, nor fail on a slow runner.
BUDGET_SECONDS = 0.050


def _best_of_three(call: Callable[[], object]) -> float:
    durations = []
    for _ in range(3):
        start = time.perf_counter()
        call()
        durations.append(time.perf_counter() - start)
    return min(durations)


def test_normalize_email_trims_and_lowercases() -> None:
    assert normalize_email("  Alice@Example.COM  ") == "alice@example.com"


@pytest.mark.parametrize(
    "invalid",
    [
        "not-an-email",
        "missing-domain@",
        "@missing-local.com",
        "no-at-sign.com",
        "   ",
        "",
        "a@@example.com",
        "a@example",
        "a b@example.com",
        "a@example..com",
        "a@.example.com",
        "a@example.com.",
    ],
)
def test_normalize_email_rejects_malformed_addresses(invalid: str) -> None:
    with pytest.raises(InvalidEmailError):
        normalize_email(invalid)


@pytest.mark.parametrize("valid", ["x@y.z", "first.last+tag@mail.example.co.uk"])
def test_normalize_email_accepts_ordinary_addresses(valid: str) -> None:
    assert normalize_email(valid) == valid


def test_normalize_email_accepts_the_longest_allowed_address() -> None:
    longest = "a" * 64 + "@" + "b" * (MAX_EMAIL_LENGTH - 69) + ".com"
    assert len(longest) == MAX_EMAIL_LENGTH

    assert normalize_email(longest) == longest


def test_normalize_email_rejects_one_character_too_many() -> None:
    too_long = "a" * 64 + "@" + "b" * (MAX_EMAIL_LENGTH - 68) + ".com"

    with pytest.raises(InvalidEmailError) as exc_info:
        normalize_email(too_long)

    assert exc_info.value.field_path == "email"


@pytest.mark.parametrize("adversarial", ADVERSARIAL_EMAILS)
def test_normalize_email_rejects_a_huge_input_quickly(adversarial: str) -> None:
    def reject() -> None:
        with pytest.raises(InvalidEmailError) as exc_info:
            normalize_email(adversarial)
        # The message echoes a bounded prefix, not the 50 000 characters.
        assert len(exc_info.value.message) < 2 * MAX_EMAIL_LENGTH

    assert _best_of_three(reject) < BUDGET_SECONDS


@pytest.mark.parametrize("adversarial", ADVERSARIAL_EMAILS)
def test_email_pattern_is_linear_even_without_the_length_guard(adversarial: str) -> None:
    """Regression test for issue #190: fails in seconds with the old pattern.

    The length check in `normalize_email` already stops these inputs; this test
    holds the pattern itself to linear time, so removing the guard later cannot
    bring the denial of service back.
    """
    assert _best_of_three(lambda: _EMAIL_PATTERN.fullmatch(adversarial)) < BUDGET_SECONDS


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
