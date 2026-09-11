"""Import routes (API.md §5): preview, launch, history, status, issues.

Seeding goes through the repositories themselves (`SqlAlchemyUnitOfWork`
against `live_engine`, the same connection `live_client` is wired to) rather
than hand-written SQL — there is no `/mappings` router yet to do it over HTTP.
"""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.import_run import ImportIssue, ImportReport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes.file_reader import InMemoryFileReader
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
        "storage_path": file_record.storage_path,
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
async def test_a_mapping_from_another_source_is_422(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    """Each resource is valid on its own; the combination is not.

    `session` is unique on `(data_source_id, external_id)`, so the source is
    part of a session's identity. Importing under the wrong one deduplicates in
    the wrong namespace and stamps the rows with a provenance that is false.
    """
    mine = await _seed(live_engine)
    other = await _seed(live_engine)

    response = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": mine["source_id"],
            "file_upload_id": mine["file_id"],
            "mapping_id": other["mapping_id"],
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MAPPING_SOURCE_MISMATCH"
    assert error["details"]["data_source_id"] == mine["source_id"]
    assert error["details"]["mapping_data_source_id"] == other["source_id"]


@requires_postgres
async def test_a_superseded_mapping_is_422(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    """A replaced version must not start a new import.

    It stays readable so past runs can be explained, but it is no longer what
    this source says its files mean.
    """
    seed = await _seed(live_engine)
    async with SqlAlchemyUnitOfWork(live_engine) as uow:
        await uow.mappings.supersede(seed["mapping_id"])
        await uow.commit()

    response = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": seed["source_id"],
            "file_upload_id": seed["file_id"],
            "mapping_id": seed["mapping_id"],
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MAPPING_NOT_ACTIVE"
    assert error["details"]["status"] == "superseded"


@requires_postgres
async def test_a_mapping_for_another_format_is_422(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    """A JSONL mapping read over a CSV file produces nothing useful."""
    seed = await _seed(live_engine)
    async with SqlAlchemyUnitOfWork(live_engine) as uow:
        csv_file = await uow.file_uploads.create(
            original_name="traces.csv",
            storage_path="unused/traces.csv",
            format="csv",
            size_bytes=10,
            content_hash=uuid4().hex.rjust(64, "f"),
        )
        await uow.commit()

    response = await live_client.post(
        "/api/v1/imports",
        json={
            "data_source_id": seed["source_id"],
            "file_upload_id": csv_file.id,
            "mapping_id": seed["mapping_id"],
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MAPPING_FORMAT_MISMATCH"
    assert error["details"] == {"mapping_format": "jsonl", "file_format": "csv"}


@requires_postgres
async def test_the_same_body_twice_is_409_not_a_second_queued_run(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    """API.md §1 reserves 409 for exactly this, and nothing applied it.

    Sending the same body twice queued two runs — the second of which can only
    report everything as a duplicate.
    """
    seed = await _seed(live_engine)
    body = {
        "data_source_id": seed["source_id"],
        "file_upload_id": seed["file_id"],
        "mapping_id": seed["mapping_id"],
    }

    first = await live_client.post("/api/v1/imports", json=body)
    second = await live_client.post("/api/v1/imports", json=body)

    assert first.status_code == 202
    assert second.status_code == 409
    error = second.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["details"]["import_run_id"] == first.json()["import_run_id"]


@requires_postgres
async def test_a_failed_run_can_be_launched_again(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    """The recovery path, which a blanket 409 would have removed.

    A worker killed mid-import leaves the run `failed`. Refusing to launch it
    again would leave the operator with no way forward, and the import engine
    is idempotent anyway.
    """
    seed = await _seed(live_engine)
    body = {
        "data_source_id": seed["source_id"],
        "file_upload_id": seed["file_id"],
        "mapping_id": seed["mapping_id"],
    }
    first = await live_client.post("/api/v1/imports", json=body)
    async with SqlAlchemyUnitOfWork(live_engine) as uow:
        await uow.import_runs.save_report(
            first.json()["import_run_id"],
            ImportReport(
                records_read=0, records_imported=0, records_duplicate=0, records_rejected=0
            ),
            status="failed",
        )
        await uow.commit()

    again = await live_client.post("/api/v1/imports", json=body)

    assert again.status_code == 202, "un run échoué doit pouvoir être relancé"


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
    # Deux imports *distincts* : poster deux fois le même corps est désormais
    # un 409, et un historique fait de la même paire répétée ne ressemblait de
    # toute façon à rien de réel.
    for _ in range(2):
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
    # Seeded with no raw_record: nothing to point at, and no line invented.
    assert all(i["line_number"] is None for i in everything.json()["items"])
    assert all(i["raw_record_id"] is None for i in everything.json()["items"])


@requires_postgres
async def test_import_issues_point_at_the_rejected_line_and_its_raw_record(
    live_client: AsyncClient, live_engine: AsyncEngine
) -> None:
    """A rejection is only explained if the client can find the line: the route
    returns its number and the raw_record id that `GET /records/{id}` opens.

    Every line is rejected on purpose: this database is shared by the whole e2e
    run without truncation, and an imported session would break the metrics
    tests that expect an empty one.
    """
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
    records = [{"not_sid": "line one"}, {"not_sid": "line two"}]
    reader = InMemoryFileReader({str(seed["storage_path"]): records})
    await RunImport(SqlAlchemyUnitOfWork(live_engine), reader).execute(run_id)

    response = await live_client.get(f"/api/v1/imports/{run_id}/issues?severity=rejected")

    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["line_number"] for i in items] == [1, 2]
    for item in items:
        assert isinstance(item["raw_record_id"], int)
        source = await live_client.get(f"/api/v1/records/{item['raw_record_id']}")
        assert source.status_code == 200
        assert source.json()["line_number"] == item["line_number"]
        assert source.json()["payload"] == records[item["line_number"] - 1]


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
