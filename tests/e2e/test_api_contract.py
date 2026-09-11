"""The generated contract says what the API does (issue #162).

The OpenAPI declares the key the middleware enforces and the envelope the error
handlers send, the docs open without a key, and ids outside BIGINT are refused
before any query is built.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.ids import MAX_ID
from tests.e2e.conftest import UNREACHABLE_URL
from tests.integration.conftest import requires_postgres

ERROR_REF = "#/components/schemas/ErrorResponse"
TOO_BIG = MAX_ID + 1


@pytest.fixture
def spec() -> dict[str, Any]:
    return create_app(engine=create_async_engine(UNREACHABLE_URL)).openapi()


@pytest.fixture
async def anonymous() -> AsyncIterator[AsyncClient]:
    """No `X-API-Key` at all, as a browser opening /docs would be."""
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _operations(spec: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            yield path, method, operation


def _error_ref(operation: dict[str, Any], status: int) -> str:
    content = operation["responses"][str(status)]["content"]
    return str(content["application/json"]["schema"]["$ref"])


def test_security_schemes_match_the_middleware(spec: dict[str, Any]) -> None:
    schemes = spec["components"]["securitySchemes"]
    assert (schemes["ApiKeyAuth"]["in"], schemes["ApiKeyAuth"]["name"]) == ("header", "X-API-Key")
    assert (schemes["BearerAuth"]["type"], schemes["BearerAuth"]["scheme"]) == ("http", "bearer")
    assert spec["security"] == [{"ApiKeyAuth": []}]


def test_only_the_public_probes_opt_out_of_the_key(spec: dict[str, Any]) -> None:
    public = {path for path, _, op in _operations(spec) if op.get("security") == []}
    assert public == {"/api/v1/health", "/api/v1/version"}


def test_bearer_is_declared_where_a_session_token_is_required(spec: dict[str, Any]) -> None:
    me = spec["paths"]["/api/v1/auth/me"]["get"]
    assert me["security"] == [{"ApiKeyAuth": [], "BearerAuth": []}]


def test_every_operation_documents_its_auth_and_server_errors(spec: dict[str, Any]) -> None:
    for path, method, op in _operations(spec):
        if op.get("security") == []:
            assert "401" not in op["responses"], (method, path)
        else:
            assert _error_ref(op, 401) == ERROR_REF, (method, path)
        assert _error_ref(op, 500) == ERROR_REF, (method, path)


def test_request_validation_is_documented_as_the_400_it_really_is(spec: dict[str, Any]) -> None:
    for path, method, op in _operations(spec):
        assert "HTTPValidationError" not in str(op["responses"]), (method, path)
    assert "HTTPValidationError" not in spec["components"]["schemas"]
    assert _error_ref(spec["paths"]["/api/v1/sessions"]["get"], 400) == ERROR_REF


@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        ("/api/v1/sessions/{id}", "get", 404),
        ("/api/v1/files/{file_id}", "get", 404),
        ("/api/v1/data-sources", "post", 409),
        ("/api/v1/data-sources", "post", 422),
        ("/api/v1/mappings/proposals", "post", 502),
    ],
)
def test_standard_error_statuses_reference_the_envelope(
    spec: dict[str, Any], path: str, method: str, status: int
) -> None:
    assert _error_ref(spec["paths"][path][method], status) == ERROR_REF


def test_the_envelope_schema_is_published(spec: dict[str, Any]) -> None:
    schemas = spec["components"]["schemas"]
    assert set(schemas["ErrorResponse"]["properties"]) == {"error"}
    assert set(schemas["ErrorBody"]["properties"]) == {"code", "message", "field_path", "details"}


def test_ids_are_bounded_in_the_contract(spec: dict[str, Any]) -> None:
    session = spec["paths"]["/api/v1/sessions/{id}"]["get"]["parameters"][0]["schema"]
    assert (session["minimum"], session["maximum"]) == (1, MAX_ID)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
async def test_docs_open_without_a_key(anonymous: AsyncClient, path: str) -> None:
    assert (await anonymous.get(path)).status_code == 200


async def test_documenting_security_does_not_loosen_it(anonymous: AsyncClient) -> None:
    response = await anonymous.get("/api/v1/metrics/definitions")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", f"files/{TOO_BIG}"),
        ("GET", "files/0"),
        ("POST", f"files/{TOO_BIG}/profile"),
        ("GET", f"sessions/{TOO_BIG}"),
        ("GET", f"sessions/{TOO_BIG}/timeline"),
        ("GET", "records/-1"),
        ("GET", f"records/{TOO_BIG}"),
        ("GET", f"sessions?data_source_id={TOO_BIG}"),
        ("GET", "sessions?agent_id=0"),
        ("GET", f"metrics/tools?model_id={TOO_BIG}"),
        ("GET", f"metrics/overview?import_run_id={TOO_BIG}"),
    ],
)
async def test_ids_outside_bigint_are_400_not_500(
    client: AsyncClient, method: str, path: str
) -> None:
    """`client` has no database: an id that reached a query would end as 500."""
    response = await client.request(method, "/api/v1/" + path)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_REQUEST"


@requires_postgres
@pytest.mark.parametrize(
    "path",
    [f"files/{MAX_ID}", f"sessions/{MAX_ID}", f"sessions/{MAX_ID}/timeline", f"records/{MAX_ID}"],
)
async def test_the_largest_bigint_is_a_plain_404(live_client: AsyncClient, path: str) -> None:
    response = await live_client.get("/api/v1/" + path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@requires_postgres
async def test_the_largest_bigint_filter_matches_nothing(live_client: AsyncClient) -> None:
    response = await live_client.get("/api/v1/sessions", params={"tool_id": MAX_ID})
    assert response.status_code == 200
    assert response.json()["total"] == 0
