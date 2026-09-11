"""Session tokens: what the client holds versus what the database keeps.

A bearer token is a credential. Stored as is, a read of `user_session` (a
backup, a read-only role) hands out working sessions. Only its SHA-256 is
stored, so the row is useless without the token.

A plain SHA-256 is enough here, unlike passwords: the token is 32 random bytes,
so there is nothing to brute-force, and the lookup must stay a single indexed
equality.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def new_session_token() -> str:
    """A fresh opaque token, to hand to the client and never to persist."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def session_token_digest(token: str) -> str:
    """The only form of a token that reaches storage: 64 lowercase hex characters."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
