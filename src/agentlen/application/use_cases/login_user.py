"""Exchange an e-mail/password pair for a bearer session token.

The token itself is an opaque random string (`secrets.token_urlsafe`, stdlib)
whose SHA-256 is stored in `user_session` — the same "generate in-process, let
the database be the source of truth" pattern the rest of the app uses for
identity (see `application/ports/repositories.py`'s note on `uuid4()`). No JWT,
no signing key to manage: revocation is a `DELETE`, not a blocklist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from agentlen.application.dto.persistence import UserRecord
from agentlen.application.errors import InvalidCredentialsError
from agentlen.application.ports.clock import Clock
from agentlen.application.ports.password_hasher import PasswordHasher
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.services.credentials import normalize_email
from agentlen.domain.services.session_tokens import new_session_token, session_token_digest

#: How long a session stays valid without further action. Not mandated by any
#: requirement; chosen as a reasonable default rather than "forever", which is
#: the usual way a token-based session quietly becomes a permanent credential.
SESSION_LIFETIME = timedelta(days=30)


@dataclass(frozen=True)
class LoginResult:
    token: str
    user: UserRecord


class LoginUser:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def execute(self, *, email: str, password: str) -> LoginResult:
        normalized_email = normalize_email(email)

        async with self._uow as uow:
            user = await uow.users.get_by_email(normalized_email)

        # Outside the transaction: no connection is held during the slow hash.
        # An unknown e-mail is verified too (against a dummy hash), so both
        # failures take the same time and raise the same error.
        password_hash = user.password_hash if user is not None else None
        if not await self._hasher.verify(password, password_hash) or user is None:
            raise InvalidCredentialsError()

        token = new_session_token()
        now = self._clock.now()
        async with self._uow as uow:
            # Logins are rare and the purge is one indexed DELETE, so this is
            # where expired sessions get cleaned up — no scheduler needed.
            await uow.user_sessions.delete_expired(now=now)
            await uow.user_sessions.create(
                user_id=user.id,
                token_hash=session_token_digest(token),
                expires_at=now + SESSION_LIFETIME,
            )
            await uow.commit()
        return LoginResult(token=token, user=user)
