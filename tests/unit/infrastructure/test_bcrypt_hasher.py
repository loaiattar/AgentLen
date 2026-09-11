"""BcryptPasswordHasher — the actual algorithm, not a double this time."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable

import bcrypt
import pytest

from agentlen.infrastructure.security.bcrypt_hasher import BcryptPasswordHasher


async def test_hash_is_not_the_plain_password() -> None:
    hasher = BcryptPasswordHasher()
    assert await hasher.hash("a-strong-passphrase") != "a-strong-passphrase"


async def test_hashing_the_same_password_twice_gives_different_hashes() -> None:
    """bcrypt salts automatically — a fixed hash for a fixed password would let
    two accounts with the same password be recognised by comparing rows."""
    hasher = BcryptPasswordHasher()
    assert await hasher.hash("a-strong-passphrase") != await hasher.hash("a-strong-passphrase")


async def test_verify_accepts_the_correct_password() -> None:
    hasher = BcryptPasswordHasher()
    stored = await hasher.hash("a-strong-passphrase")
    assert await hasher.verify("a-strong-passphrase", stored) is True


async def test_verify_rejects_the_wrong_password() -> None:
    hasher = BcryptPasswordHasher()
    stored = await hasher.hash("a-strong-passphrase")
    assert await hasher.verify("something-else", stored) is False


async def test_verify_fails_closed_on_a_malformed_hash() -> None:
    """A corrupted or non-bcrypt value must not crash the login route."""
    hasher = BcryptPasswordHasher()
    assert await hasher.verify("a-strong-passphrase", "not-a-real-bcrypt-hash") is False


async def test_verify_without_an_account_does_the_same_bcrypt_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No account must not mean no work, or the fast answer names unknown e-mails."""
    checked: list[bytes] = []
    real_checkpw = bcrypt.checkpw

    def spy(password: bytes, hashed_password: bytes) -> bool:
        checked.append(hashed_password)
        return real_checkpw(password, hashed_password)

    monkeypatch.setattr(bcrypt, "checkpw", spy)
    hasher = BcryptPasswordHasher()

    assert await hasher.verify("a-strong-passphrase", None) is False

    assert len(checked) == 1
    # Same algorithm and cost factor as a real hash ("$2b$12$"): same time.
    real_hash = await hasher.hash("a-strong-passphrase")
    assert checked[0].decode("ascii")[:7] == real_hash[:7]


async def _loop_ticks_during(operation: Awaitable[object]) -> int:
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.001)

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    before = ticks
    await operation
    during = ticks - before
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return during


async def test_hashing_and_verifying_leave_the_event_loop_free() -> None:
    """Run on the loop, ~250 ms of bcrypt freezes every other request: the
    ticker would not advance at all while the hash runs."""
    hasher = BcryptPasswordHasher()
    stored = await hasher.hash("a-strong-passphrase")

    assert await _loop_ticks_during(hasher.hash("a-strong-passphrase")) > 5
    assert await _loop_ticks_during(hasher.verify("a-strong-passphrase", stored)) > 5
