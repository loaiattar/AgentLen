"""Business rules for user credentials — format, not storage.

Hashing a password is an infrastructure concern (bcrypt, reached through the
`PasswordHasher` port). What belongs here, in the domain, is deciding whether
an e-mail or a password is even acceptable *before* either reaches storage:
that is a business rule, not a wire-format detail, and it must hold whether
the request came from the HTTP API, the CLI, or a test.
"""

from __future__ import annotations

import re

from agentlen.domain.errors import InvalidEmailError, WeakPasswordError

# Deliberately simple: one "@", a local part, a domain with at least one dot.
# Exhaustively validating RFC 5322 buys nothing here — the only consequence of
# a false positive is a bounced login later, not a stored bad value.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8
# bcrypt silently ignores bytes past 72 and raises outright on some builds;
# rejecting early gives a clear 422 instead of a confusing failure at hash time.
MAX_PASSWORD_LENGTH = 72


def normalize_email(email: str) -> str:
    """Trim and lowercase, then validate the format.

    Lowercasing here — not just at the database's unique index — is what makes
    "Alice@Example.com" and "alice@example.com" collide as the same account
    instead of two, which is what a user actually expects.
    """
    normalized = email.strip().lower()
    if not normalized or not _EMAIL_PATTERN.match(normalized):
        raise InvalidEmailError(email)
    return normalized


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères."
        )
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Le mot de passe ne doit pas dépasser {MAX_PASSWORD_LENGTH} octets."
        )
