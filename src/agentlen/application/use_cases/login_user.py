"""Exchange an e-mail/password pair for a bearer session token.

The token itself is an opaque random string (`secrets.token_urlsafe`, stdlib)
stored in `user_session` — the same "generate in-process, let the database be
the source of truth" pattern the rest of the app uses for identity (see
`application/ports/repositories.py`'s note on `uuid4()`). No JWT, no signing
key to manage: revocation is a `DELETE`, not a blocklist.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from agentlen.application.dto.persistence import UserRecord
from agentlen.application.errors import InvalidCredentialsError
from agentlen.application.ports.clock import Clock
from agentlen.application.ports.password_hasher import PasswordHasher
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.services.credentials import normalize_email

#: How long a session stays valid without further action. Not mandated by any
#: requirement; chosen as a reasonable default rather than "forever", which is
#: the usual way a token-based session quietly becomes a permanent credential.
SESSION_LIFETIME = timedelta(days=30)

TOKEN_BYTES = 32


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
            # Hashing a dummy value when the account does not exist would even
            # out the response time between "unknown e-mail" and "wrong
            # password" (a timing side-channel for account enumeration), but
            # that hardening is out of scope here — the requirement is that
            # neither case succeeds, and both raise the same error below.
            if user is None or not self._hasher.verify(password, user.password_hash):
                raise InvalidCredentialsError()

            token = secrets.token_urlsafe(TOKEN_BYTES)
            expires_at = self._clock.now() + SESSION_LIFETIME
            await uow.user_sessions.create(user_id=user.id, token=token, expires_at=expires_at)
            await uow.commit()
            return LoginResult(token=token, user=user)
