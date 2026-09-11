"""bcrypt implementation of `PasswordHasher`.

bcrypt salts automatically and encodes the salt into its own output, so the
stored hash is self-contained — no separate salt column, and two calls with
the same password never produce the same string.

Each call runs in a worker thread (`asyncio.to_thread`): bcrypt releases the
GIL, so the event loop keeps serving other requests during the ~250 ms of work.
"""

from __future__ import annotations

import asyncio
import secrets

import bcrypt

#: Verified against when the account does not exist. Built with the same
#: `gensalt()` as real hashes, so it has the same cost factor and takes the same
#: time. Its password is random and discarded: nothing can ever match it.
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt())


def _check(password: str, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except ValueError:
        # A hash that isn't valid bcrypt output (corrupted row, or a
        # future migration away from bcrypt) must fail closed, not crash
        # the login route with a 500.
        return False


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


class BcryptPasswordHasher:
    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(_hash, password)

    async def verify(self, password: str, password_hash: str | None) -> bool:
        if password_hash is None:
            await asyncio.to_thread(_check, password, _DUMMY_HASH)
            return False
        return await asyncio.to_thread(_check, password, password_hash.encode("ascii"))
