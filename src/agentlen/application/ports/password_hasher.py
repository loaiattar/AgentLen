"""Port for password hashing.

The concrete algorithm (bcrypt) is a third-party dependency, so it stays out
of `application/` and `domain/` behind this `Protocol` — the same pattern as
`Clock` and `StructureAnalyzer`. Tests can swap in a trivial double instead of
paying bcrypt's deliberately-slow cost on every use-case run.
"""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        """Return a salted hash. Never the same string twice for the same input."""
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """True if `password`, once hashed, matches `password_hash`."""
        ...
