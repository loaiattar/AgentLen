"""LoginUser: right password succeeds, wrong password and unknown e-mail don't
— and don't tell the caller which of the two happened."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentlen.application.errors import InvalidCredentialsError
from agentlen.application.use_cases.login_user import LoginUser
from agentlen.application.use_cases.register_user import RegisterUser
from tests.fakes.repositories import InMemoryUnitOfWork

FIXED_NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FixedClock:
    def now(self) -> datetime:
        return FIXED_NOW


async def _register(uow: InMemoryUnitOfWork, *, email: str, password: str) -> None:
    await RegisterUser(uow, FakePasswordHasher()).execute(email=email, password=password)


async def test_logs_in_with_valid_credentials_and_returns_a_token() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")
    use_case = LoginUser(uow, FakePasswordHasher(), FixedClock())

    result = await use_case.execute(email="alice@example.com", password="a-strong-passphrase")

    assert result.token
    assert result.user.email == "alice@example.com"


async def test_two_logins_issue_different_tokens() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")
    use_case = LoginUser(uow, FakePasswordHasher(), FixedClock())

    first = await use_case.execute(email="alice@example.com", password="a-strong-passphrase")
    second = await use_case.execute(email="alice@example.com", password="a-strong-passphrase")

    assert first.token != second.token


async def test_wrong_password_is_rejected() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")
    use_case = LoginUser(uow, FakePasswordHasher(), FixedClock())

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="alice@example.com", password="wrong-password")


async def test_unknown_email_is_rejected_with_the_same_error() -> None:
    uow = InMemoryUnitOfWork()
    use_case = LoginUser(uow, FakePasswordHasher(), FixedClock())

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="ghost@example.com", password="whatever-password")


async def test_login_is_case_insensitive_on_email() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")
    use_case = LoginUser(uow, FakePasswordHasher(), FixedClock())

    result = await use_case.execute(email="Alice@Example.com", password="a-strong-passphrase")

    assert result.user.email == "alice@example.com"
