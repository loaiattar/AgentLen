"""Port for password hashing.

The concrete algorithm (bcrypt) is a third-party dependency, so it stays out
of `application/` and `domain/` behind this `Protocol` — the same pattern as
`Clock` and `StructureAnalyzer`. Tests can swap in a trivial double instead of
paying bcrypt's deliberately-slow cost on every use-case run.

The methods are async because a real hash takes about 250 ms of CPU: run on
the event loop, ten concurrent logins would freeze every other request. An
adapter does that work off the loop; a caller cannot forget to, since it has
to `await`.
"""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str:
        """Return a salted hash. Never the same string twice for the same input."""
        ...

    async def verify(self, password: str, password_hash: str | None) -> bool:
        """True if `password`, once hashed, matches `password_hash`.

        `None` means there is no account. The implementation still does the
        full work, against a dummy hash, and returns False: an unknown e-mail
        must take as long as a wrong password, or timing reveals which
        e-mails have an account.
        """
        ...
