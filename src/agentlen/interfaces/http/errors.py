"""Translation of exceptions into the single error envelope of API.md §1.

Two rules drive this module:

1. **Every** error leaves through the envelope — including the ones FastAPI
   raises before our code runs (malformed body, bad query parameter) and the
   ones we never anticipated. A front that has to handle two error shapes will
   handle one of them badly.

2. An unhandled exception returns a generic 500. No traceback, no file path, no
   SQL, no exception message. Those go to the server log, where the team can
   read them and an attacker cannot.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agentlen.application.errors import (
    AnalyzerError,
    AnalyzerTimeoutError,
    ApplicationError,
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    UnauthenticatedError,
)
from agentlen.application.ports.file_storage import FileStorageError
from agentlen.domain.errors import AgentMaxIterationsError, DomainError, ValidationError

#: Starlette is renaming its 422 constant; the literal does not churn.
HTTP_422_UNPROCESSABLE = 422

logger = logging.getLogger("agentlen.http")

#: Application errors -> HTTP status. Order matters: most specific first.
_APPLICATION_STATUS: tuple[tuple[type[ApplicationError], int], ...] = (
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (AnalyzerTimeoutError, status.HTTP_504_GATEWAY_TIMEOUT),
    (AnalyzerError, status.HTTP_502_BAD_GATEWAY),
    (InvalidCredentialsError, status.HTTP_401_UNAUTHORIZED),
    (UnauthenticatedError, status.HTTP_401_UNAUTHORIZED),
)

GENERIC_500_MESSAGE = "Une erreur interne est survenue. L'incident a été journalisé côté serveur."


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    field_path: str | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build the one and only error shape."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "field_path": field_path,
                "details": details or {},
            }
        },
    )


async def _domain_validation(_: Request, exc: Exception) -> JSONResponse:
    """A mapping (or other document) broke a business rule. -> 422

    The domain's ValidationError already carries a stable code and the exact
    path of the offending field; both go straight to the client, because
    "invalid mapping" without a location is not an explanation.
    """
    assert isinstance(exc, ValidationError)
    return error_response(HTTP_422_UNPROCESSABLE, exc.code, exc.message, field_path=exc.field_path)


async def _agent_no_convergence(_: Request, exc: Exception) -> JSONResponse:
    """The agent loop hit its iteration ceiling. -> 502

    Upstream fault, not a bug in the request, so the front can offer a retry.
    """
    assert isinstance(exc, AgentMaxIterationsError)
    return error_response(
        status.HTTP_502_BAD_GATEWAY,
        "AGENT_NO_CONVERGENCE",
        str(exc),
        details={"max_iterations": exc.max_iterations},
    )


async def _domain(_: Request, exc: Exception) -> JSONResponse:
    """Any other domain rule violation. -> 422"""
    assert isinstance(exc, DomainError)
    return error_response(HTTP_422_UNPROCESSABLE, "DOMAIN_RULE_VIOLATED", str(exc))


async def _application(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    code = HTTP_422_UNPROCESSABLE
    for error_type, mapped in _APPLICATION_STATUS:
        if isinstance(exc, error_type):
            code = mapped
            break
    return error_response(code, exc.code, exc.message, details=exc.details)


async def _file_storage(_: Request, exc: Exception) -> JSONResponse:
    """A file was refused before it could be stored. -> 422

    API.md §1 lists "format non supporté" under 422 explicitly; too-large is
    the same class of refusal — the request is well-formed, the upload itself
    is what's rejected.
    """
    assert isinstance(exc, FileStorageError)
    return error_response(HTTP_422_UNPROCESSABLE, exc.code, str(exc))


async def _request_validation(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI rejected the request before it reached a use case. -> 400/422

    Mapping documents are user-editable business documents, so their typed
    body errors are 422 as required by the mapping API. Other malformed input,
    including query strings, remains 400.
    """
    assert isinstance(exc, RequestValidationError)
    first = exc.errors()[0] if exc.errors() else {}
    parts = first.get("loc", ())
    location = ".".join(str(part) for part in parts)
    path = request.url.path
    is_proposal_route = "/mappings/proposals" in path
    mapping_body = (
        "body" in parts
        and path.startswith("/api/v1/mappings")
        and (
            not is_proposal_route
            or request.method == "PATCH"
            or (len(parts) > 1 and parts[1] == "hint")
        )
    )
    return error_response(
        HTTP_422_UNPROCESSABLE if mapping_body else status.HTTP_400_BAD_REQUEST,
        "MAPPING_INVALID" if mapping_body else "MALFORMED_REQUEST",
        first.get("msg", "La requête est malformée."),
        field_path=location or None,
        details={"errors": len(exc.errors())},
    )


async def _http_exception(_: Request, exc: Exception) -> JSONResponse:
    """Re-wrap FastAPI's own aborts (404 on an unknown path, 405, ...)."""
    assert isinstance(exc, StarletteHTTPException)
    codes = {
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    }
    return error_response(
        exc.status_code,
        codes.get(exc.status_code, "HTTP_ERROR"),
        str(exc.detail),
    )


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """The catch-all. -> 500, and the body says nothing useful to an attacker.

    The full traceback is logged server-side; the response deliberately does not
    echo `str(exc)`, which routinely leaks table names, file paths and SQL.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", GENERIC_500_MESSAGE
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire every handler. Most specific exception types first."""
    app.add_exception_handler(ValidationError, _domain_validation)
    app.add_exception_handler(AgentMaxIterationsError, _agent_no_convergence)
    app.add_exception_handler(DomainError, _domain)
    app.add_exception_handler(ApplicationError, _application)
    app.add_exception_handler(FileStorageError, _file_storage)
    app.add_exception_handler(RequestValidationError, _request_validation)
    app.add_exception_handler(StarletteHTTPException, _http_exception)
    app.add_exception_handler(Exception, _unhandled)
