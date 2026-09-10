"""User auth routes: register, login, logout, and "who am I" (API.md §Auth).

Distinct from `interfaces/http/auth.py`'s `ApiKeyMiddleware`, which gates the
whole API for the front-end application. These routes authenticate the person
using it, on top of that — every request here still needs `X-API-Key` too,
since these paths are not in `ApiKeyMiddleware.PUBLIC_PATHS`.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, status

from agentlen.application.dto.persistence import UserRecord
from agentlen.application.use_cases.login_user import LoginUser
from agentlen.application.use_cases.logout_user import LogoutUser
from agentlen.application.use_cases.register_user import RegisterUser
from agentlen.interfaces.http.dependencies import (
    ClockDep,
    CurrentUserDep,
    PasswordHasherDep,
    UnitOfWorkDep,
)
from agentlen.interfaces.http.schemas.auth import LoginIn, LoginOut, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_out(record: UserRecord) -> UserOut:
    assert record.created_at is not None  # always set by the database on insert
    return UserOut(id=record.id, email=record.email, created_at=record.created_at)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account with an e-mail and a password",
    responses={409: {"description": "An account already exists for this e-mail."}},
)
async def register(body: RegisterIn, uow: UnitOfWorkDep, hasher: PasswordHasherDep) -> UserOut:
    use_case = RegisterUser(uow, hasher)
    record = await use_case.execute(email=body.email, password=body.password)
    return _to_out(record)


@router.post(
    "/login",
    response_model=LoginOut,
    summary="Exchange an e-mail/password pair for a bearer session token",
    responses={401: {"description": "Wrong e-mail or password."}},
)
async def login(
    body: LoginIn, uow: UnitOfWorkDep, hasher: PasswordHasherDep, clock: ClockDep
) -> LoginOut:
    use_case = LoginUser(uow, hasher, clock)
    result = await use_case.execute(email=body.email, password=body.password)
    return LoginOut(token=result.token, user=_to_out(result.user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate the current session token",
)
async def logout(uow: UnitOfWorkDep, authorization: str | None = Header(default=None)) -> None:
    use_case = LogoutUser(uow)
    token = _bearer_token(authorization)
    if token is not None:
        await use_case.execute(token)


def _bearer_token(header: str | None) -> str | None:
    if not header or not header.lower().startswith("bearer "):
        return None
    token = header[len("bearer ") :].strip()
    return token or None


@router.get(
    "/me",
    response_model=UserOut,
    summary="The authenticated user for the current session token",
    responses={401: {"description": "Missing, unknown or expired session token."}},
)
async def me(current_user: CurrentUserDep) -> UserOut:
    return _to_out(current_user)
