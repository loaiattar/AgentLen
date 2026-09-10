"""Mapping routes (API.md §4, MAPPING_CONTRACT.md §2)."""

from __future__ import annotations

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


async def _seed_data_source(live_client: AsyncClient, *, slug: str = "tracelab") -> int:
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
    source_id = await _seed_data_source(live_client, slug="tracelab")
    other_id = await _seed_data_source(live_client, slug="swe-chat")
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
async def test_put_on_an_unknown_mapping_is_404(live_client: AsyncClient) -> None:
    response = await live_client.put("/api/v1/mappings/999999", json=VALID_DOCUMENT)

    assert response.status_code == 404
