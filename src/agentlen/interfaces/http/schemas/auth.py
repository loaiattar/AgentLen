"""Wire shapes for the auth routes.

`UserOut` deliberately has no `password` or `password_hash` field — not
"excluded at serialization time", but structurally absent, so there is no
value to forget to strip.

Both credentials are bounded here, before any use case runs: these routes
answer without a session, so an unbounded field is an unauthenticated way to
make the server work. An over-long value is a malformed request, answered with
`400 MALFORMED_REQUEST` in the usual envelope (API.md §1, §10).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

from agentlen.domain.services.credentials import MAX_EMAIL_LENGTH, MAX_PASSWORD_LENGTH


def _within_password_bytes(password: str) -> str:
    """bcrypt's limit is in bytes; `max_length` alone only counts characters."""
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise PydanticCustomError(
            "password_too_long",
            "Le mot de passe ne doit pas dépasser {max_bytes} octets.",
            {"max_bytes": MAX_PASSWORD_LENGTH},
        )
    return password


# `max_length` rejects the bulk of an oversized value before it is encoded and
# publishes `maxLength` in the OpenAPI; the validator enforces the byte limit.
Email = Annotated[str, Field(max_length=MAX_EMAIL_LENGTH, examples=["alice@example.com"])]
Password = Annotated[
    str,
    Field(max_length=MAX_PASSWORD_LENGTH, examples=["a-strong-passphrase"]),
    AfterValidator(_within_password_bytes),
]


class RegisterIn(BaseModel):
    email: Email
    password: Password


class LoginIn(BaseModel):
    email: Email
    password: Password


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class LoginOut(BaseModel):
    token: str
    user: UserOut
