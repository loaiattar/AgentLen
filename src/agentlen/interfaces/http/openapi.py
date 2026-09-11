"""Make the generated OpenAPI say what the running API does.

Authentication lives in `ApiKeyMiddleware` and error shaping in `errors.py`,
both outside FastAPI's dependency graph, so the default document knows about
neither: no security scheme, and FastAPI's own 422 `HTTPValidationError` where
the API really answers 400 with the error envelope. This module patches the
document only. It adds no dependency to any route, so runtime behaviour is
exactly what the middleware and the handlers already enforce.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from fastapi import FastAPI, routing
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from pydantic.json_schema import models_json_schema

from agentlen.interfaces.http.auth import is_public_path
from agentlen.interfaces.http.dependencies import (
    get_analyzer_factory,
    get_current_user,
    get_structure_analyzer,
)
from agentlen.interfaces.http.schemas.common import ErrorResponse

API_KEY_SCHEME = "ApiKeyAuth"
BEARER_SCHEME = "BearerAuth"

SECURITY_SCHEMES: dict[str, Any] = {
    API_KEY_SCHEME: {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "Application key (`API_KEY`). Required on every route but the probes.",
    },
    BEARER_SCHEME: {
        "type": "http",
        "scheme": "bearer",
        "description": "Opaque session token returned by `POST /auth/login`.",
    },
}

#: Statuses whose body is always the envelope. 503 is not one: readiness
#: answers it with its own report.
ENVELOPE_DESCRIPTIONS = {
    400: "Malformed request (`MALFORMED_REQUEST`).",
    401: "Missing or invalid `X-API-Key`.",
    404: "Resource not found.",
    409: "Conflict.",
    422: "Business validation failed.",
    500: "Unexpected server error (`INTERNAL_ERROR`). Leaks nothing.",
    502: "The AI provider failed or answered out of contract.",
}

_ERROR_REF = {"$ref": "#/components/schemas/ErrorResponse"}
_FASTAPI_VALIDATION_SCHEMAS = ("HTTPValidationError", "ValidationError")


def _schema_routes(app: FastAPI) -> Iterator[Any]:
    """Every documented API route, with its router prefix applied.

    Recent FastAPI includes routers lazily: `app.routes` holds wrappers, and
    the flattened view the schema generator itself uses comes from
    `iter_route_contexts`. Older versions list `APIRoute`s directly.
    """
    flatten = getattr(routing, "iter_route_contexts", None)
    routes: Iterable[Any] = flatten(app.routes) if flatten else app.routes
    for route in routes:
        if isinstance(getattr(route, "original_route", route), APIRoute) and (
            route.include_in_schema
        ):
            yield route


def _calls(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for sub in dependant.dependencies:
        if sub.call is not None:
            yield sub.call
        yield from _calls(sub)


def _envelope(responses: dict[str, Any], status_code: int) -> None:
    """Declare the envelope on `status_code`, keeping a route's own description."""
    entry = responses.setdefault(str(status_code), {})
    entry.setdefault("description", ENVELOPE_DESCRIPTIONS[status_code])
    entry["content"] = {"application/json": {"schema": _ERROR_REF}}


def _document_operation(route: Any, method: str, operation: dict[str, Any]) -> None:
    """`route` is an `APIRoute` or FastAPI's context proxying one."""
    calls = set(_calls(route.dependant))
    responses: dict[str, Any] = operation.setdefault("responses", {})
    public = is_public_path(route.path_format)

    if public:
        operation["security"] = []
    elif get_current_user in calls:
        operation["security"] = [{API_KEY_SCHEME: [], BEARER_SCHEME: []}]

    # FastAPI declares 422 for any route with parameters; errors.py answers 400.
    validation = responses.get("422", {}).get("content", {}).get("application/json", {})
    if validation.get("schema", {}).get("$ref", "").endswith("/HTTPValidationError"):
        del responses["422"]
        _envelope(responses, 400)

    declared = {int(code) for code in responses if code.isdigit()}
    statuses = {500} | (declared & ENVELOPE_DESCRIPTIONS.keys())
    if not public:
        statuses.add(401)
    if "{" in route.path_format:
        statuses.add(404)
    if method in {"post", "put", "patch"} and "requestBody" in operation:
        statuses.add(422)
    if calls & {get_structure_analyzer, get_analyzer_factory}:
        statuses.add(502)
    for status_code in sorted(statuses):
        _envelope(responses, status_code)


def document_runtime_contract(app: FastAPI, schema: dict[str, Any]) -> dict[str, Any]:
    """Add security and the error envelope to an already generated document."""
    components = schema.setdefault("components", {})
    components["securitySchemes"] = SECURITY_SCHEMES
    schema["security"] = [{API_KEY_SCHEME: []}]

    for route in _schema_routes(app):
        for method in route.methods or ():
            operation = schema["paths"][route.path_format].get(method.lower())
            if operation is not None:
                _document_operation(route, method.lower(), operation)

    _, definitions = models_json_schema(
        [(ErrorResponse, "serialization")], ref_template="#/components/schemas/{model}"
    )
    schemas = components.setdefault("schemas", {})
    schemas.update(definitions["$defs"])
    # FastAPI's validation schemas describe a body the API never sends.
    for name in _FASTAPI_VALIDATION_SCHEMAS:
        if f'"#/components/schemas/{name}"' not in json.dumps(schema):
            schemas.pop(name, None)
    return schema


def install_openapi(app: FastAPI) -> None:
    """Replace `app.openapi` with a generator that documents the runtime contract."""
    generate = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = document_runtime_contract(app, generate())
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
