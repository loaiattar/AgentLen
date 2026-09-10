"""bcrypt implementation of `PasswordHasher`.

bcrypt salts automatically and encodes the salt into its own output, so the
stored hash is self-contained — no separate salt column, and two calls with
the same password never produce the same string.
"""

from __future__ import annotations

import bcrypt


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
        except ValueError:
            # A hash that isn't valid bcrypt output (corrupted row, or a
            # future migration away from bcrypt) must fail closed, not crash
            # the login route with a 500.
            return False
