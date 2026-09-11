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
async def test_neither_endpoint_claims_an_import_for_a_stored_never_imported_file(
    live_client: AsyncClient,
) -> None:
    """`already_seen` never meant "imported", on either endpoint.

    `GET /files/{id}` used to compute it as `len(runs) > 0`, which read as an
    import history and contradicted `POST /files`, where the same flag comes
    from the content hash. The wizard believed the GET and warned "this file
    has already been imported" about an import that never happened.

    The flag is scoped to an upload event — "did this upload reuse a stored
    file" — so a GET, which uploads nothing, says false. What both endpoints
    must agree on is the import history, and that is `previous_import_run_ids`.
    """
    upload = await live_client.post(
        "/api/v1/files",
        files={"file": ("agree.jsonl", b'{"id": "a"}\n', "application/x-ndjson")},
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    fetched = await live_client.get(f"/api/v1/files/{file_id}")

    assert fetched.status_code == 200
    # The one fact that has to match, and the one the front reads.
    assert upload.json()["previous_import_run_ids"] == []
    assert fetched.json()["previous_import_run_ids"] == []
    # A fresh upload reused nothing, and a GET uploads nothing.
    assert upload.json()["already_seen"] is False
    assert fetched.json()["already_seen"] is False


@requires_postgres
async def test_get_file_does_not_repeat_the_already_seen_of_a_reusing_upload(
    live_client_with_storage: AsyncClient,
) -> None:
    """Only the upload that reused the stored file says `already_seen: true`.

    `GET /files/{id}` used to answer true for every file, so a page reloaded on
    a brand-new upload warned that it had been uploaded before.
    """
    content = b'{"session_id": "reuse-1"}\n'
    first = await live_client_with_storage.post(
        "/api/v1/files", files={"file": ("r1.jsonl", content, "application/octet-stream")}
    )
    fetched_new = await live_client_with_storage.get(f"/api/v1/files/{first.json()['id']}")
    second = await live_client_with_storage.post(
        "/api/v1/files", files={"file": ("r2.jsonl", content, "application/octet-stream")}
    )
    fetched_again = await live_client_with_storage.get(f"/api/v1/files/{second.json()['id']}")

    assert second.json()["id"] == first.json()["id"]
    assert [first.json()["already_seen"], second.json()["already_seen"]] == [False, True]
    assert fetched_new.json()["already_seen"] is False
    assert fetched_again.json()["already_seen"] is False
    assert fetched_again.json()["previous_import_run_ids"] == []


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


#: Upload limit for the refusal tests: small, but above the multipart overhead.
SMALL_LIMIT = 1024 * 1024


@pytest.fixture
async def client_with_small_limit(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    app = create_app(engine=create_async_engine(UNREACHABLE_URL))
    app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(
        tmp_path, max_bytes=SMALL_LIMIT
    )
    async with asgi_client(app) as c:
        yield c


def _stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


async def test_a_declared_oversize_body_is_refused_before_it_is_read(
    client_with_small_limit: AsyncClient, tmp_path: Path
) -> None:
    """`Content-Length` already says too much: not one byte is read or written.
    FastAPI's `UploadFile` used to spool the whole body to disk first."""
    chunks_read = 0

    async def body() -> AsyncIterator[bytes]:
        nonlocal chunks_read
        for _ in range(4):
            chunks_read += 1
            yield b"x" * SMALL_LIMIT

    response = await client_with_small_limit.post(
        "/api/v1/files",
        content=body(),
        headers={
            "Content-Type": "multipart/form-data; boundary=b",
            "Content-Length": str(4 * SMALL_LIMIT),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert chunks_read == 0
    assert _stored_files(tmp_path) == []


async def test_an_undeclared_oversize_body_is_refused_as_soon_as_it_crosses_the_limit(
    client_with_small_limit: AsyncClient, tmp_path: Path
) -> None:
    """Chunked, with no `Content-Length`: the stream is cut at the limit, and the
    partial file is removed."""
    chunks_read = 0

    async def body() -> AsyncIterator[bytes]:
        nonlocal chunks_read
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="big.jsonl"\r\n\r\n'
        for _ in range(64):  # 16 MiB offered
            chunks_read += 1
            yield b'{"a":1}\n' * (32 * 1024)  # 256 KiB

    response = await client_with_small_limit.post(
        "/api/v1/files",
        content=body(),
        headers={"Content-Type": "multipart/form-data; boundary=b"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert chunks_read <= 5
    assert _stored_files(tmp_path) == []


async def test_an_upload_without_a_file_field_is_a_400(
    client_with_small_limit: AsyncClient,
) -> None:
    response = await client_with_small_limit.post(
        "/api/v1/files",
        files={"attachment": ("session.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MALFORMED_REQUEST"


@requires_postgres
async def test_the_file_is_found_after_other_fields_and_keeps_its_name(
    live_client_with_storage: AsyncClient,
) -> None:
    response = await live_client_with_storage.post(
        "/api/v1/files",
        data={"note": "x" * 100_000},
        files={"file": ("été.jsonl", JSONL_SAMPLE, "application/octet-stream")},
    )

    assert response.status_code == 201
    assert response.json()["original_name"] == "été.jsonl"
    assert response.json()["size_bytes"] == len(JSONL_SAMPLE)


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
