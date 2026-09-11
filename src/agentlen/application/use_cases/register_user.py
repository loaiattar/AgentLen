"""Create an account with an e-mail and a password.

The password is hashed before it ever reaches the unit of work — no code path
in this use case has a way to persist it in clear, because nothing here holds
a table or a column name, only the `UserRepository` port.
"""

from __future__ import annotations

from agentlen.application.dto.persistence import UserRecord
from agentlen.application.errors import ConflictError
from agentlen.application.ports.password_hasher import PasswordHasher
from agentlen.application.ports.unit_of_work import UnitOfWork
from agentlen.domain.services.credentials import normalize_email, validate_password_strength


class RegisterUser:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher) -> None:
        self._uow = uow
        self._hasher = hasher

    async def execute(self, *, email: str, password: str) -> UserRecord:
        normalized_email = normalize_email(email)
        validate_password_strength(password)

        async with self._uow as uow:
            if await uow.users.get_by_email(normalized_email) is not None:
                raise ConflictError(
                    f"Un compte existe déjà pour l'adresse '{normalized_email}'.",
                    details={"email": normalized_email},
                )

            password_hash = self._hasher.hash(password)
            record = await uow.users.create(email=normalized_email, password_hash=password_hash)
            await uow.commit()
            return record
