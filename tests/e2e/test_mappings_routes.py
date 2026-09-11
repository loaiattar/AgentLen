"""Mapping routes (API.md §4, MAPPING_CONTRACT.md §2)."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient

from tests.integration.conftest import requires_postgres

VALID_DOCUMENT = {
    "source_format": "jsonl",
    "entities": [
        {
            "target": "session",
            "natural_key": ["external_id"],
            "fields": [{"target": "external_id", "source": "$.sid", "required": True}],
        }
    ],
}


async def _seed_data_source(live_client: AsyncClient, *, slug: str | None = None) -> int:
    """A fresh data source with a unique slug by default.

    `live_client` shares one Postgres across the whole CI run with no
    truncation between tests, and `POST /data-sources` genuinely 409s on a
    duplicate slug (it isn't idempotent like the repository's own `create()`)
    — a hardcoded default slug would 409 on the second test to call this.
    """
    slug = slug or f"tracelab-{uuid4().hex[:8]}"
    response = await live_client.post("/api/v1/data-sources", json={"slug": slug, "name": slug})
    id_: int = response.json()["id"]
    return id_


# ---------------------------------------------------------------------------
# POST /mappings/validate — no database needed, nothing is ever written
# ---------------------------------------------------------------------------


async def test_validate_accepts_a_correct_document(client: AsyncClient) -> None:
    response = await client.post("/api/v1/mappings/validate", json=VALID_DOCUMENT)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["errors"] == []


async def test_validate_flags_an_operator_outside_the_whitelist(client: AsyncClient) -> None:
    document = {
        "source_format": "jsonl",
        "entities": [
            {
                "target": "session",
                "natural_key": ["external_id"],
                "fields": [
                    {
                        "target": "external_id",
                        "source": "$.sid",
                        "operators": [{"op": "eval_python"}],
                    }
                ],
            }
        ],
    }

    response = await client.post("/api/v1/mappings/validate", json=document)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["code"] == "MAPPING_UNKNOWN_OPERATOR"


async def test_validate_localizes_an_invalid_operator_parameter(client: AsyncClient) -> None:
    document = {
        "source_format": "jsonl",
        "entities": [
            {
                "target": "session",
                "natural_key": ["external_id"],
                "fields": [
                    {
                        "target": "external_id",
                        "source": "$.sid",
                        "operators": [{"op": "cast"}],
                    }
                ],
            }
        ],
    }

    response = await client.post("/api/v1/mappings/validate", json=document)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"] == [
        {
            "code": "INVALID_OPERATOR_PARAM",
            "field_path": "entities[target=session].fields[target=external_id].operators[0].to",
            "message": "Required parameter 'to' is missing for 'cast'.",
        }
    ]


async def test_validate_flags_an_entity_without_a_natural_key(client: AsyncClient) -> None:
    document = {
        "source_format": "jsonl",
        "entities": [{"target": "session", "natural_key": [], "fields": []}],
    }

    response = await client.post("/api/v1/mappings/validate", json=document)

    body = response.json()
    assert body["valid"] is False
    assert any(e["code"] == "MAPPING_MISSING_NATURAL_KEY" for e in body["errors"])


async def test_validate_flags_every_error_at_once(client: AsyncClient) -> None:
    document = {
        "source_format": "jsonl",
        "entities": [
            {
                "target": "session",
                "natural_key": [],
                "fields": [{"target": "not_a_real_field", "source": "$.x"}],
            }
        ],
    }

    response = await client.post("/api/v1/mappings/validate", json=document)

    codes = {e["code"] for e in response.json()["errors"]}
    assert "MAPPING_MISSING_NATURAL_KEY" in codes
    assert "MAPPING_UNKNOWN_TARGET" in codes


# ---------------------------------------------------------------------------
# POST /mappings — validated before write, invalid documents never touch the DB
# ---------------------------------------------------------------------------


async def test_creating_an_invalid_mapping_is_422_before_touching_the_database(
    client: AsyncClient,
) -> None:
    """No reachable database: proves validation runs before the write."""
    response = await client.post(
        "/api/v1/mappings",
        json={
            "data_source_id": 1,
            "name": "broken",
            "source_format": "jsonl",
            "entities": [{"target": "session", "natural_key": [], "fields": []}],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MAPPING_INVALID"


@requires_postgres
async def test_creating_a_mapping_returns_201_with_the_full_document(
    live_client: AsyncClient,
) -> None:
    source_id = await _seed_data_source(live_client)

    response = await live_client.post(
        "/api/v1/mappings",
        json={"data_source_id": source_id, "name": "tracelab-jsonl", **VALID_DOCUMENT},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data_source_id"] == source_id
    assert body["name"] == "tracelab-jsonl"
    assert body["version"] == 1
    assert body["status"] == "active"
    assert body["entities"][0]["target"] == "session"


@requires_postgres
async def test_creating_a_mapping_for_an_unknown_data_source_is_404(
    live_client: AsyncClient,
) -> None:
    response = await live_client.post(
        "/api/v1/mappings",
        json={"data_source_id": 999999, "name": "m", **VALID_DOCUMENT},
    )

    assert response.status_code == 404


@requires_postgres
async def test_creating_the_same_name_twice_for_a_source_is_409(live_client: AsyncClient) -> None:
    source_id = await _seed_data_source(live_client)
    body = {"data_source_id": source_id, "name": "dup", **VALID_DOCUMENT}

    first = await live_client.post("/api/v1/mappings", json=body)
    second = await live_client.post("/api/v1/mappings", json=body)

    assert first.status_code == 201
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# GET /mappings, GET /mappings/{id}
# ---------------------------------------------------------------------------


@requires_postgres
async def test_get_mapping_returns_the_full_document(live_client: AsyncClient) -> None:
    source_id = await _seed_data_source(live_client)
    created = await live_client.post(
        "/api/v1/mappings", json={"data_source_id": source_id, "name": "m", **VALID_DOCUMENT}
    )
    mapping_id = created.json()["id"]

    response = await live_client.get(f"/api/v1/mappings/{mapping_id}")

    assert response.status_code == 200
    assert response.json()["id"] == mapping_id


@requires_postgres
async def test_get_unknown_mapping_is_404(live_client: AsyncClient) -> None:
    response = await live_client.get("/api/v1/mappings/999999")

    assert response.status_code == 404


@requires_postgres
async def test_list_mappings_filters_by_data_source(live_client: AsyncClient) -> None:
    source_id = await _seed_data_source(live_client)
    other_id = await _seed_data_source(live_client)
    await live_client.post(
        "/api/v1/mappings", json={"data_source_id": source_id, "name": "a", **VALID_DOCUMENT}
    )
    await live_client.post(
        "/api/v1/mappings", json={"data_source_id": other_id, "name": "b", **VALID_DOCUMENT}
    )

    response = await live_client.get(f"/api/v1/mappings?data_source_id={source_id}")

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["data_source_id"] == source_id


# ---------------------------------------------------------------------------
# PUT /mappings/{id} — new version, old one superseded
# ---------------------------------------------------------------------------


@requires_postgres
async def test_put_creates_a_new_version_and_supersedes_the_old_one(
    live_client: AsyncClient,
) -> None:
    source_id = await _seed_data_source(live_client)
    created = await live_client.post(
        "/api/v1/mappings", json={"data_source_id": source_id, "name": "m", **VALID_DOCUMENT}
    )
    mapping_id = created.json()["id"]

    response = await live_client.put(f"/api/v1/mappings/{mapping_id}", json=VALID_DOCUMENT)

    assert response.status_code == 200
    new_body = response.json()
    assert new_body["version"] == 2
    assert new_body["id"] != mapping_id

    old = await live_client.get(f"/api/v1/mappings/{mapping_id}")
    assert old.json()["status"] == "superseded"


@requires_postgres
async def test_a_second_put_on_the_same_version_is_409_not_500(live_client: AsyncClient) -> None:
    """The double click. Reproduced against Postgres before the fix.

    `PUT /mappings/{v1}` twice both computed v1 + 1, and the second insert
    raised `UniqueViolationError` on `uq_mapping_name_version`. Nothing catches
    `IntegrityError`, so the caller got a bare 500.
    """
    source_id = await _seed_data_source(live_client, slug="double-put")
    created = await live_client.post(
        "/api/v1/mappings",
        json={"data_source_id": source_id, "name": "double-put", **VALID_DOCUMENT},
    )
    first_id = created.json()["id"]

    second = await live_client.put(f"/api/v1/mappings/{first_id}", json=VALID_DOCUMENT)
    assert second.status_code == 200
    assert second.json()["version"] == 2

    again = await live_client.put(f"/api/v1/mappings/{first_id}", json=VALID_DOCUMENT)

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "CONFLICT"
    assert again.json()["error"]["details"]["latest_version"] == 2


@requires_postgres
async def test_put_refuses_a_data_source_change_instead_of_ignoring_it(
    live_client: AsyncClient,
) -> None:
    """The guard existed but no request could reach it.

    `update_mapping` always passed `data_source_id=None`, so a caller naming
    the wrong source was silently ignored. The field is now accepted on the
    PUT, checked against the previous version, and refused on a mismatch.
    """
    source_id = await _seed_data_source(live_client, slug="put-source")
    other_id = await _seed_data_source(live_client, slug="put-other-source")
    created = await live_client.post(
        "/api/v1/mappings",
        json={"data_source_id": source_id, "name": "put-source-guard", **VALID_DOCUMENT},
    )
    mapping_id = created.json()["id"]

    refused = await live_client.put(
        f"/api/v1/mappings/{mapping_id}",
        json={"data_source_id": other_id, **VALID_DOCUMENT},
    )
    assert refused.status_code == 409

    accepted = await live_client.put(
        f"/api/v1/mappings/{mapping_id}",
        json={"data_source_id": source_id, **VALID_DOCUMENT},
    )
    assert accepted.status_code == 200
    assert accepted.json()["version"] == 2


@requires_postgres
async def test_put_on_an_unknown_mapping_is_404(live_client: AsyncClient) -> None:
    response = await live_client.put("/api/v1/mappings/999999", json=VALID_DOCUMENT)

    assert response.status_code == 404
