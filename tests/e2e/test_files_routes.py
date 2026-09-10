"""File routes (API.md §2): upload, metadata, profiling.

`LocalFileStorage` is swapped for one rooted in `tmp_path` via
`dependency_overrides` — otherwise every run would write real files under the
repo's `storage/uploads`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from agentlen.infrastructure.files.local_storage import LocalFileStorage
from agentlen.interfaces.http.app import create_app
from agentlen.interfaces.http.dependencies import get_file_storage
from tests.e2e.conftest import UNREACHABLE_URL, asgi_client
from tests.integration.conftest import requires_postgres

JSONL_SAMPLE = (
    b'{"session_id": "a1", "usage": {"input_tokens": 10}}\n'
    b'{"session_id": "a2", "usage": {"input_tokens": 20}}\n'
)


@pytest.fixture
async def live_client_with_storage(
    live_engine: AsyncEngine, tmp_path: Path
) -> AsyncIterator[AsyncClient]:
    """A live_client whose file storage is rooted in a throwaway directory."""
    app = create_app(engine=live_engine)
    app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(tmp_path)
    async with asgi_client(app) as c:
        yield c


@pytest.fixture
async def client_with_storage(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    """No reachable database — correct for the extension check, which is
    refused by the storage layer before any row is ever touched."""
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(tmp_path)
    async with asgi_client(app) as c:
        yield c


@requires_postgres
async def test_uploading_a_file_returns_201_with_its_metadata(
    live_client_with_storage: AsyncClient,
) -> None:
    response = await live_client_with_storage.post(
        "/api/v1/files",
        files={"file": ("session.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_name"] == "session.jsonl"
    assert body["format"] == "jsonl"
    assert body["size_bytes"] == len(JSONL_SAMPLE)
    assert body["already_seen"] is False
    assert body["previous_import_run_ids"] == []


@requires_postgres
async def test_uploading_the_same_content_twice_reports_already_seen(
    live_client_with_storage: AsyncClient,
) -> None:
    first = await live_client_with_storage.post(
        "/api/v1/files",
        files={"file": ("a.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )
    second = await live_client_with_storage.post(
        "/api/v1/files",
        files={"file": ("b.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )

    assert first.json()["id"] == second.json()["id"]
    assert second.json()["already_seen"] is True


async def test_disallowed_extension_is_a_422_not_a_500(
    client_with_storage: AsyncClient,
) -> None:
    response = await client_with_storage.post(
        "/api/v1/files",
        files={"file": ("payload.exe", b"MZ\x90\x00", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_FORMAT"


@requires_postgres
async def test_get_file_returns_the_uploaded_metadata(
    live_client_with_storage: AsyncClient,
) -> None:
    created = await live_client_with_storage.post(
        "/api/v1/files",
        files={"file": ("c.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )
    file_id = created.json()["id"]

    response = await live_client_with_storage.get(f"/api/v1/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["id"] == file_id
    assert response.json()["content_hash"] == created.json()["content_hash"]


@requires_postgres
async def test_get_unknown_file_is_404(live_client_with_storage: AsyncClient) -> None:
    response = await live_client_with_storage.get("/api/v1/files/999999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@requires_postgres
async def test_profiling_a_stored_file_returns_field_statistics(
    live_client_with_storage: AsyncClient,
) -> None:
    created = await live_client_with_storage.post(
        "/api/v1/files",
        files={"file": ("d.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )
    file_id = created.json()["id"]

    response = await live_client_with_storage.post(f"/api/v1/files/{file_id}/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == file_id
    assert body["record_count"] == 2
    paths = {f["path"] for f in body["fields"]}
    assert "$.session_id" in paths
    assert "$.usage.input_tokens" in paths


@requires_postgres
async def test_profiling_an_unknown_file_is_404(
    live_client_with_storage: AsyncClient,
) -> None:
    response = await live_client_with_storage.post("/api/v1/files/999999/profile")

    assert response.status_code == 404
