"""Wire shapes for the auth routes.

`UserOut` deliberately has no `password` or `password_hash` field — not
"excluded at serialization time", but structurally absent, so there is no
value to forget to strip.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(examples=["alice@example.com"])
    password: str = Field(examples=["a-strong-passphrase"])


class LoginIn(BaseModel):
    email: str = Field(examples=["alice@example.com"])
    password: str = Field(examples=["a-strong-passphrase"])


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime


class LoginOut(BaseModel):
    token: str
    user: UserOut
