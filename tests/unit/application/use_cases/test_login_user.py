"""LoginUser: right password succeeds, wrong password and unknown e-mail don't
— and don't tell the caller which of the two happened."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentlen.application.errors import InvalidCredentialsError
from agentlen.application.use_cases.login_user import LoginUser
from agentlen.application.use_cases.register_user import RegisterUser
from agentlen.domain.services.session_tokens import session_token_digest
from tests.fakes.password_hasher import FakePasswordHasher
from tests.fakes.repositories import InMemoryUnitOfWork

FIXED_NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


class FixedClock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


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


async def test_unknown_email_still_pays_for_a_password_verification() -> None:
    """Skipping the hash for an unknown e-mail makes that failure measurably
    faster than a wrong password: a timing oracle for which e-mails exist."""
    hasher = FakePasswordHasher()
    use_case = LoginUser(InMemoryUnitOfWork(), hasher, FixedClock())

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(email="ghost@example.com", password="whatever-password")

    assert hasher.verified == [None]


async def test_login_is_case_insensitive_on_email() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")
    use_case = LoginUser(uow, FakePasswordHasher(), FixedClock())

    result = await use_case.execute(email="Alice@Example.com", password="a-strong-passphrase")

    assert result.user.email == "alice@example.com"


async def test_only_the_digest_of_the_token_is_stored() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")

    result = await LoginUser(uow, FakePasswordHasher(), FixedClock()).execute(
        email="alice@example.com", password="a-strong-passphrase"
    )

    stored = [record.token_hash for record in uow._store.user_sessions.values()]
    assert stored == [session_token_digest(result.token)]
    assert result.token not in stored


async def test_login_purges_expired_sessions() -> None:
    uow = InMemoryUnitOfWork()
    await _register(uow, email="alice@example.com", password="a-strong-passphrase")
    credentials = {"email": "alice@example.com", "password": "a-strong-passphrase"}
    await LoginUser(uow, FakePasswordHasher(), FixedClock()).execute(**credentials)

    later = FixedClock(FIXED_NOW + timedelta(days=31))
    latest = await LoginUser(uow, FakePasswordHasher(), later).execute(**credentials)

    stored = [record.token_hash for record in uow._store.user_sessions.values()]
    assert stored == [session_token_digest(latest.token)]
