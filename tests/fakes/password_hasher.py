"""In-memory `PasswordHasher`: no bcrypt cost, and a record of every verification."""

from __future__ import annotations


class FakePasswordHasher:
    """`hash` is deliberately not the identity function, so a test asserting
    'the hash differs from the plain password' actually proves something.

    `verified` lists the hash each `verify` call received, `None` included, so a
    test can prove an unknown e-mail still pays for a verification."""

    def __init__(self) -> None:
        self.verified: list[str | None] = []

    async def hash(self, password: str) -> str:
        return f"hashed:{password}"

    async def verify(self, password: str, password_hash: str | None) -> bool:
        self.verified.append(password_hash)
        return password_hash == f"hashed:{password}"
