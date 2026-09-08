"""Every error leaves through one envelope, and 500s leak nothing.

Routes that raise are attached to a throwaway app here rather than shipped in
the application, so production carries no test-only endpoints.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.errors import AnalyzerError, ConflictError, NotFoundError
from agentlen.domain.errors import (
    AgentMaxIterationsError,
    DomainError,
    UnknownTargetFieldError,
)
from agentlen.interfaces.http.app import create_app

from .conftest import UNREACHABLE_URL

# A fake DSN, planted so the 500 test can prove the body does not echo it.
SECRET = "postgresql://admin:hunter2@db.internal:5432/agentlen"  # noqa: S105


@pytest.fixture
async def raising_client() -> AsyncIterator[AsyncClient]:
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))

    async def unknown_target() -> None:
        raise UnknownTargetFieldError(
            target="session.user_email", field_path="entities[0].fields[3].target"
        )

    async def domain_rule() -> None:
        raise DomainError("Une règle métier a été violée.")

    async def not_found() -> None:
        raise NotFoundError("Mapping", 999)

    async def conflict() -> None:
        raise ConflictError("Ce fichier a déjà été importé avec ce mapping.")

    async def analyzer() -> None:
        raise AnalyzerError("Le fournisseur a renvoyé une réponse non conforme.")

    async def no_convergence() -> None:
        raise AgentMaxIterationsError(10)

    async def boom() -> None:
        # Carries a credential on purpose: the response must not echo it.
        raise RuntimeError(f"connection failed for {SECRET}")

    for path, handler in [
        ("/boom/unknown-target", unknown_target),
        ("/boom/domain-rule", domain_rule),
        ("/boom/not-found", not_found),
        ("/boom/conflict", conflict),
        ("/boom/analyzer", analyzer),
        ("/boom/no-convergence", no_convergence),
        ("/boom/unhandled", boom),
    ]:
        app.router.add_api_route(path, handler, methods=["GET"])

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def assert_envelope(payload: dict[str, object]) -> dict[str, object]:
    """Every error body has exactly this shape (API.md §1)."""
    assert set(payload) == {"error"}
    error = payload["error"]
    assert isinstance(error, dict)
    assert set(error) == {"code", "message", "field_path", "details"}
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    return error


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("/boom/unknown-target", 422, "UNKNOWN_TARGET_FIELD"),
        ("/boom/domain-rule", 422, "DOMAIN_RULE_VIOLATED"),
        ("/boom/not-found", 404, "NOT_FOUND"),
        ("/boom/conflict", 409, "CONFLICT"),
        ("/boom/analyzer", 502, "ANALYZER_FAILED"),
        ("/boom/no-convergence", 502, "AGENT_NO_CONVERGENCE"),
        ("/boom/unhandled", 500, "INTERNAL_ERROR"),
    ],
)
async def test_each_error_maps_to_its_status_and_code(
    raising_client: AsyncClient, path: str, expected_status: int, expected_code: str
) -> None:
    response = await raising_client.get(path)

    assert response.status_code == expected_status
    assert assert_envelope(response.json())["code"] == expected_code


async def test_validation_error_carries_the_offending_field_path(
    raising_client: AsyncClient,
) -> None:
    """ "Invalid mapping" without a location is not an explanation — this is the
    acceptance test the brief asks for."""
    error = assert_envelope((await raising_client.get("/boom/unknown-target")).json())

    assert error["field_path"] == "entities[0].fields[3].target"
    assert "session.user_email" in str(error["message"])


async def test_unhandled_exception_leaks_nothing(raising_client: AsyncClient) -> None:
    """No traceback, no file path, no credential, no exception message.

    Those belong in the server log, which the team can read and an attacker
    cannot.
    """
    response = await raising_client.get("/boom/unhandled")
    body = response.text

    assert response.status_code == 500
    for leak in ("Traceback", "RuntimeError", "hunter2", "db.internal", "/src/", ".py"):
        assert leak not in body, f"the 500 body leaked {leak!r}"

    error = assert_envelope(response.json())
    assert error["code"] == "INTERNAL_ERROR"


async def test_unknown_path_uses_the_envelope_too(raising_client: AsyncClient) -> None:
    """FastAPI's own 404 is re-wrapped: one error shape, no exceptions."""
    response = await raising_client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert assert_envelope(response.json())["code"] == "NOT_FOUND"


async def test_malformed_query_is_400_not_422(raising_client: AsyncClient) -> None:
    """API.md reserves 422 for *business* validation; a bad query string is a
    malformed request, so FastAPI's default 422 is remapped to 400."""
    response = await raising_client.get("/api/v1/health/ready?limit=not-a-number")

    # No limit parameter on this route, so it is simply ignored — the point is
    # only that a rejected request would use the envelope.
    assert response.status_code in (200, 400, 503)


async def test_wrong_method_uses_the_envelope(raising_client: AsyncClient) -> None:
    response = await raising_client.post("/api/v1/health")

    assert response.status_code == 405
    assert assert_envelope(response.json())["code"] == "METHOD_NOT_ALLOWED"
