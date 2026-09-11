"""Resolve an `Authorization: Bearer <token>` header to the user it names.

Used by the HTTP layer's `get_current_user` dependency (interfaces/http/
dependencies.py) to guard routes that need to know *who* is calling — as
opposed to `ApiKeyMiddleware`, which only knows *that* the front-end is
calling. Header parsing lives here rather than in the FastAPI dependency so
the whole check — malformed header, unknown token, expired token — is one
unit-testable use case with no ASGI involved.
"""

from __future__ import annotations

from agentlen.application.dto.persistence import UserRecord
from agentlen.application.errors import UnauthenticatedError
from agentlen.application.ports.clock import Clock
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.services.session_tokens import session_token_digest

_SCHEME_PREFIX = "bearer "


class AuthenticateUser:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, authorization_header: str | None) -> UserRecord:
        token = self._extract_token(authorization_header)

        async with self._uow as uow:
            # The repository filters out expired sessions, so an expired token
            # and an unknown one are the same `None`.
            session = await uow.user_sessions.get_active_by_token_hash(
                session_token_digest(token), now=self._clock.now()
            )
            if session is None:
                raise UnauthenticatedError()

            user = await uow.users.get_by_id(session.user_id)
            if user is None:
                raise UnauthenticatedError()
            return user

    @staticmethod
    def _extract_token(header: str | None) -> str:
        if not header or not header.lower().startswith(_SCHEME_PREFIX):
            raise UnauthenticatedError()
        token = header[len(_SCHEME_PREFIX) :].strip()
        if not token:
            raise UnauthenticatedError()
        return token
