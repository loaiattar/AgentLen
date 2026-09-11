"""API-key authentication middleware.

Every route requires the `X-API-Key` header except liveness and version, which
orchestrators hit without credentials. The header value is compared in constant
time and is never written to a log line.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from agentlen.infrastructure.config.settings import Settings
from agentlen.interfaces.http.errors import error_response

logger = logging.getLogger("agentlen.http.auth")

#: Probes and the version endpoint stay public (prefixed and unprefixed).
#: So do the interactive docs and the schema they load: a browser navigating
#: to /docs cannot attach a header, and the document only describes routes
#: that all still require the key.
PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/version",
        "/api/v1/health",
        "/api/v1/version",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)

UNAUTHORIZED_MESSAGE = "Clé API manquante ou invalide."


def _keys_match(provided: str, expected: str) -> bool:
    """Constant-time compare on UTF-8 bytes so a non-ASCII header cannot raise."""
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _configured_api_key(request: Request) -> str:
    settings: Settings = request.app.state.settings
    return settings.api_key


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Rejects requests that do not carry a valid `X-API-Key`."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Preflight has no API key; CORSMiddleware answers it before routing.
        if request.method == "OPTIONS" or is_public_path(request.url.path):
            return await call_next(request)

        expected = _configured_api_key(request)
        provided = request.headers.get("x-api-key", "")
        if not expected or not _keys_match(provided, expected):
            logger.info("Rejected unauthenticated request %s %s", request.method, request.url.path)
            return error_response(
                status.HTTP_401_UNAUTHORIZED,
                "UNAUTHORIZED",
                UNAUTHORIZED_MESSAGE,
            )
        return await call_next(request)
