"""Import routes (API.md §5): preview, launch, history, status, issues.

Seeding goes through the repositories themselves (`SqlAlchemyUnitOfWork`
against `live_engine`, the same connection `live_client` is wired to) rather
than hand-written SQL — there is no `/mappings` router yet to do it over HTTP.
"""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.integration.conftest import requires_postgres


def _valid_mapping(*, name: str = "tracelab-jsonl") -> Mapping:
    return Mapping(
        id=uuid4(),
        name=name,
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(FieldRule(target="external_id", source="$.sid", required=True),),
            ),
        ),
    )


def _invalid_mapping() -> Mapping:
    return Mapping(
        id=uuid4(),
        name="broken",
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(
                    FieldRule(
                        target="external_id", source="$.sid", operators=({"op": "eval_python"},)
                    ),
                ),
            ),
        ),
    )


async def _seed(live_engine: AsyncEngine) -> dict[str, int | str]:
    """A data source, a stored file record and an active mapping — the minimum
    an import run needs. The file's bytes are never read by these tests.

    `live_client`/`live_engine` share one Postgres across the whole run with no
    truncation between tests (unlike the contract suite's `clean_db`), and
    `mappings.save()` has no idempotence to fall back on the way
    `data_sources.create()`/`file_uploads.create()` do — so every call needs
    its own unique name, or the second test to call this collides on
    `uq_mapping_name_version`.
    """
    unique = uuid4().hex[:8]
    slug = f"tracelab-{unique}"
    mapping_name = f"tracelab-jsonl-{unique}"
    async with SqlAlchemyUnitOfWork(live_engine) as uow:
        source_id = await uow.data_sources.create(slug=slug, name="TraceLab")
        file_record = await uow.file_uploads.create(
            original_name="s.jsonl",
            storage_path="unused/does-not-need-to-exist.jsonl",
            format="jsonl",
            size_bytes=10,
            content_hash=f"{unique}".rjust(64, "0"),
        )
        mapping_id = await uow.mappings.save(
            _valid_mapping(name=mapping_name), data_source_id=source_id
        )
        await uow.commit()
    return {
        "source_id": source_id,
        "slug": slug,
        "file_id": file_record.id,
        "mapping_id": mapping_id,
        "mapping_name": mapping_name,
    }


async def test_creating_an_import_with_a_missing_field_is_400(client: AsyncClient) -> None:
    """No reachable database needed: rejected before the route body runs.

    422 is reserved for business validation (API.md §1) — a malformed request
    is remapped to 400, same as everywhere else.
    """
    response = await client.post("/api/v1/imports", json={"data_source_id": 1, "file_upload_id": 1})

    assert response.status_code == 400


@requires_postgres
async def test_creating_an_import_returns_202_pending(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    seed = await _seed(live_engine)

    response = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": seed["source_id"],
            "file_upload_id": seed["file_id"],
            "mapping_id": seed["mapping_id"],
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["import_run_id"] is not None


@requires_postgres
async def test_creating_an_import_for_unknown_mapping_is_404(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    seed = await _seed(live_engine)

    response = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": seed["source_id"],
            "file_upload_id": seed["file_id"],
            "mapping_id": 999999,
        },
    )

    assert response.status_code == 404


@requires_postgres
async def test_get_import_returns_full_status_with_joined_refs(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    seed = await _seed(live_engine)
    created = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": seed["source_id"],
            "file_upload_id": seed["file_id"],
            "mapping_id": seed["mapping_id"],
        },
    )
    run_id = created.json()["import_run_id"]

    response = await live_client.get(f"/api/v1/imports/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["data_source"] == {"id": seed["source_id"], "slug": seed["slug"]}
    assert body["file"] == {"id": seed["file_id"], "original_name": "s.jsonl"}
    assert body["mapping"]["name"] == seed["mapping_name"]
    assert body["mapping"]["version"] == 1
    assert body["report"]["records_read"] == 0
    assert body["started_at"] is None
    assert body["finished_at"] is None


@requires_postgres
async def test_get_unknown_import_is_404(live_client: AsyncClient) -> None:
    response = await live_client.get("/api/v1/imports/999999")

    assert response.status_code == 404


@requires_postgres
async def test_list_imports_returns_the_history_paginated(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    seed = await _seed(live_engine)
    for _ in range(2):
        await live_client.post(
            "/api/v1/imports",
            json={
                "data_source_id": seed["source_id"],
                "file_upload_id": seed["file_id"],
                "mapping_id": seed["mapping_id"],
            },
        )

    response = await live_client.get("/api/v1/imports?limit=1&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["total"] >= 2


@requires_postgres
async def test_import_issues_are_listed_and_filterable_by_severity(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    seed = await _seed(live_engine)
    created = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": seed["source_id"],
            "file_upload_id": seed["file_id"],
            "mapping_id": seed["mapping_id"],
        },
    )
    run_id = created.json()["import_run_id"]

    async with SqlAlchemyUnitOfWork(live_engine) as uow:
        await uow.import_issues.add_many(
            import_run_id=run_id,
            issues=[
                (ImportIssue(severity="rejected", code="CAST_FAILED", message="nope"), None),
                (ImportIssue(severity="warning", code="MISSING", message="meh"), None),
            ],
        )
        await uow.commit()

    everything = await live_client.get(f"/api/v1/imports/{run_id}/issues")
    assert everything.status_code == 200
    assert everything.json()["total"] == 2

    rejected_only = await live_client.get(f"/api/v1/imports/{run_id}/issues?severity=rejected")
    assert rejected_only.json()["total"] == 1
    assert rejected_only.json()["items"][0]["code"] == "CAST_FAILED"


@requires_postgres
async def test_preview_rejects_an_invalid_mapping_with_422(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    async with SqlAlchemyUnitOfWork(live_engine) as uow:
        # Own unique slug: data_sources.create() is idempotent by slug, so a
        # bare "tracelab" would silently work today, but only because of
        # pytest's current file collection order relative to
        # test_data_sources_routes.py's own (non-idempotent, HTTP-level)
        # "tracelab" — fragile enough to fix outright.
        source_id = await uow.data_sources.create(
            slug=f"tracelab-{uuid4().hex[:8]}", name="TraceLab"
        )
        file_record = await uow.file_uploads.create(
            original_name="s.jsonl",
            storage_path="unused/does-not-need-to-exist.jsonl",
            format="jsonl",
            size_bytes=1,
            content_hash="c" * 64,
        )
        mapping_id = await uow.mappings.save(_invalid_mapping(), data_source_id=source_id)
        await uow.commit()

    response = await live_client.post(
        "/api/v1/imports/preview",
        json={"file_id": file_record.id, "mapping_id": mapping_id},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MAPPING_INVALID"


@requires_postgres
async def test_preview_for_unknown_mapping_is_404(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    seed = await _seed(live_engine)

    response = await live_client.post(
        "/api/v1/imports/preview",
        json={"file_id": seed["file_id"], "mapping_id": 999999},
    )

    assert response.status_code == 404
