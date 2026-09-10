"""RegisterUser: no database, no real bcrypt — a trivial hasher stands in."""

from __future__ import annotations

import pytest

from agentlen.application.errors import ConflictError
from agentlen.application.use_cases.register_user import RegisterUser
from agentlen.domain.errors import InvalidEmailError, WeakPasswordError
from tests.fakes.repositories import InMemoryUnitOfWork


class FakePasswordHasher:
    """`hash` is deliberately not the identity function, so a test asserting
    'the hash differs from the plain password' actually proves something."""

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


async def test_creates_a_user_with_a_hashed_password() -> None:
    uow = InMemoryUnitOfWork()
    use_case = RegisterUser(uow, FakePasswordHasher())

    record = await use_case.execute(email="Alice@Example.com", password="a-strong-passphrase")

    assert record.email == "alice@example.com"
    assert record.password_hash == "hashed:a-strong-passphrase"
    assert record.password_hash != "a-strong-passphrase"


async def test_rejects_an_invalid_email() -> None:
    uow = InMemoryUnitOfWork()
    use_case = RegisterUser(uow, FakePasswordHasher())

    with pytest.raises(InvalidEmailError):
        await use_case.execute(email="not-an-email", password="a-strong-passphrase")


async def test_rejects_a_weak_password() -> None:
    uow = InMemoryUnitOfWork()
    use_case = RegisterUser(uow, FakePasswordHasher())

    with pytest.raises(WeakPasswordError):
        await use_case.execute(email="alice@example.com", password="short")


async def test_rejects_a_duplicate_email() -> None:
    uow = InMemoryUnitOfWork()
    use_case = RegisterUser(uow, FakePasswordHasher())
    await use_case.execute(email="alice@example.com", password="a-strong-passphrase")

    with pytest.raises(ConflictError):
        await use_case.execute(email="alice@example.com", password="another-passphrase")


async def test_rejects_a_duplicate_email_case_insensitively() -> None:
    uow = InMemoryUnitOfWork()
    use_case = RegisterUser(uow, FakePasswordHasher())
    await use_case.execute(email="alice@example.com", password="a-strong-passphrase")

    with pytest.raises(ConflictError):
        await use_case.execute(email="Alice@Example.com", password="another-passphrase")
