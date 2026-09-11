"""Invalidate a session token.

Idempotent by construction: deleting a token that is already gone (already
logged out, or never existed) is not an error — the caller's goal ("this
token must not work any more") is already satisfied.
"""

from __future__ import annotations

from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.services.session_tokens import session_token_digest


class LogoutUser:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, token: str) -> None:
        async with self._uow as uow:
            await uow.user_sessions.delete_by_token_hash(session_token_digest(token))
            await uow.commit()
