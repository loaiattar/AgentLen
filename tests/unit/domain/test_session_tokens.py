"""Session tokens: the client gets the token, storage gets its SHA-256."""

from __future__ import annotations

import re

from agentlen.domain.services.session_tokens import new_session_token, session_token_digest


def test_digest_is_sha256_hex_and_never_the_token() -> None:
    token = new_session_token()
    digest = session_token_digest(token)

    # The exact shape the `user_session` CHECK constraint accepts.
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest != token
    assert session_token_digest(token) == digest, "lookup needs a deterministic digest"


def test_new_tokens_are_unique_and_not_digests() -> None:
    first, second = new_session_token(), new_session_token()

    assert first != second
    # A token mistakenly stored as is would be refused by the CHECK constraint.
    assert not re.fullmatch(r"[0-9a-f]{64}", first)
