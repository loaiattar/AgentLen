"""AuthenticateUser (the protected-route guard) and LogoutUser (revocation)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentlen.application.errors import UnauthenticatedError
from agentlen.application.use_cases.authenticate_user import AuthenticateUser
from agentlen.application.use_cases.login_user import LoginUser
from agentlen.application.use_cases.logout_user import LogoutUser
from agentlen.application.use_cases.register_user import RegisterUser
from tests.fakes.repositories import InMemoryUnitOfWork

FIXED_NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FixedClock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


async def _logged_in_token(uow: InMemoryUnitOfWork, clock: FixedClock) -> str:
    await RegisterUser(uow, FakePasswordHasher()).execute(
        email="alice@example.com", password="a-strong-passphrase"
    )
    result = await LoginUser(uow, FakePasswordHasher(), clock).execute(
        email="alice@example.com", password="a-strong-passphrase"
    )
    return result.token


async def test_a_valid_token_resolves_to_its_user() -> None:
    uow = InMemoryUnitOfWork()
    clock = FixedClock()
    token = await _logged_in_token(uow, clock)

    user = await AuthenticateUser(uow, clock).execute(f"Bearer {token}")

    assert user.email == "alice@example.com"


async def test_missing_header_is_unauthenticated() -> None:
    uow = InMemoryUnitOfWork()
    with pytest.raises(UnauthenticatedError):
        await AuthenticateUser(uow, FixedClock()).execute(None)


@pytest.mark.parametrize("header", ["not-a-bearer-token", "Bearer", "Bearer   ", "Basic abc123"])
async def test_malformed_header_is_unauthenticated(header: str) -> None:
    uow = InMemoryUnitOfWork()
    with pytest.raises(UnauthenticatedError):
        await AuthenticateUser(uow, FixedClock()).execute(header)


async def test_unknown_token_is_unauthenticated() -> None:
    uow = InMemoryUnitOfWork()
    with pytest.raises(UnauthenticatedError):
        await AuthenticateUser(uow, FixedClock()).execute("Bearer does-not-exist")


async def test_expired_token_is_unauthenticated() -> None:
    uow = InMemoryUnitOfWork()
    login_clock = FixedClock(FIXED_NOW)
    token = await _logged_in_token(uow, login_clock)

    later_clock = FixedClock(FIXED_NOW + timedelta(days=31))
    with pytest.raises(UnauthenticatedError):
        await AuthenticateUser(uow, later_clock).execute(f"Bearer {token}")


async def test_logout_invalidates_the_token() -> None:
    uow = InMemoryUnitOfWork()
    clock = FixedClock()
    token = await _logged_in_token(uow, clock)

    await LogoutUser(uow).execute(token)

    with pytest.raises(UnauthenticatedError):
        await AuthenticateUser(uow, clock).execute(f"Bearer {token}")


async def test_logout_is_idempotent() -> None:
    uow = InMemoryUnitOfWork()
    # No session ever existed for this token — must not raise.
    await LogoutUser(uow).execute("never-issued-token")
