"""BcryptPasswordHasher — the actual algorithm, not a double this time."""

from __future__ import annotations

from agentlen.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher


def test_hash_is_not_the_plain_password() -> None:
    hasher = BcryptPasswordHasher()
    assert hasher.hash("a-strong-passphrase") != "a-strong-passphrase"


def test_hashing_the_same_password_twice_gives_different_hashes() -> None:
    """bcrypt salts automatically — a fixed hash for a fixed password would let
    two accounts with the same password be recognised by comparing rows."""
    hasher = BcryptPasswordHasher()
    assert hasher.hash("a-strong-passphrase") != hasher.hash("a-strong-passphrase")


def test_verify_accepts_the_correct_password() -> None:
    hasher = BcryptPasswordHasher()
    stored = hasher.hash("a-strong-passphrase")
    assert hasher.verify("a-strong-passphrase", stored) is True


def test_verify_rejects_the_wrong_password() -> None:
    hasher = BcryptPasswordHasher()
    stored = hasher.hash("a-strong-passphrase")
    assert hasher.verify("something-else", stored) is False


def test_verify_fails_closed_on_a_malformed_hash() -> None:
    """A corrupted or non-bcrypt value must not crash the login route."""
    hasher = BcryptPasswordHasher()
    assert hasher.verify("a-strong-passphrase", "not-a-real-bcrypt-hash") is False
