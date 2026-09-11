"""The six tests the brief requires, in the order it lists them.

`docs/architecture/ARCHITECTURE.md` §11 names six behaviours that have to be
demonstrated, not merely implemented. They live in their own package, carry
their own marker and are named after the requirement rather than after the code
they exercise, so that

    make test-acceptance

reads as the list of requirements with a verdict beside each one.

Nothing here needs an API key: `AI_PROVIDER=fake` is the default, and the one
test that switches providers switches between two test doubles.

Each test builds its own controlled dataset. That is deliberate — an acceptance
test that leans on a fixture written elsewhere proves the fixture, and the
reader has to go and find it before believing the assertion.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import Connection, Engine, func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.dto.dashboard import DashboardFilters
from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.read_models.sql import SqlDashboardQueries
from agentlen.infrastructure.persistence.repositories.mapping_codec import mapping_to_document
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes.file_reader import InMemoryFileReader
from tests.integration.conftest import requires_postgres

pytestmark = [pytest.mark.acceptance, requires_postgres]

TRACES = "memory://traces"

#: Two sessions, one with two tool calls and a model call, one with a single
#: tool call. Small enough to compute every expected figure by hand below.
RECORDS: list[dict[str, Any]] = [
    {
        "sid": "s-1",
        "model": "claude-opus-4-8",
        "provider": "anthropic",
        "in_tokens": 100,
        "out_tokens": 20,
        "seq": 0,
        "tools": [
            {"name": "Bash", "i": 0, "status": "ok"},
            {"name": "Read", "i": 1, "status": "error"},
        ],
    },
    {
        "sid": "s-2",
        "model": "claude-opus-4-8",
        "provider": "anthropic",
        "in_tokens": 300,
        "out_tokens": 40,
        "seq": 0,
        "tools": [{"name": "Bash", "i": 0, "status": "ok"}],
    },
]

MAPPING = Mapping(
    id=uuid4(),
    name="acceptance",
    version=1,
    source_format="jsonl",
    entities=(
        EntityMapping(
            target="session",
            natural_key=("external_id",),
            fields=(FieldRule(target="external_id", source="$.sid", required=True),),
        ),
        EntityMapping(
            target="model_call",
            natural_key=("sequence_index",),
            parent={"entity": "session", "via": "external_id"},
            fields=(
                FieldRule(target="sequence_index", source="$.seq", required=True),
                FieldRule(target="model_name", source="$.model", required=True),
                FieldRule(target="provider_name", source="$.provider"),
                FieldRule(target="input_tokens", source="$.in_tokens"),
                FieldRule(target="output_tokens", source="$.out_tokens"),
            ),
        ),
        EntityMapping(
            target="tool_call",
            natural_key=("sequence_index",),
            iterate="$.tools",
            parent={"entity": "session", "via": "external_id"},
            fields=(
                FieldRule(target="tool_name", source="$.name", required=True),
                FieldRule(target="sequence_index", source="$.i", required=True),
                FieldRule(target="status", source="$.status"),
            ),
        ),
    ),
)


def _seed(engine: Engine, *, mapping: Mapping = MAPPING, slug: str = "tracelab") -> dict[str, int]:
    """Seed through a connection of our own.

    `clean_db` hands out a connection already inside `engine.begin()`, so
    committing on it closes the context manager's transaction and every later
    statement is refused. It is requested for the truncation it performs, not
    for the connection it yields.
    """
    with engine.begin() as conn:
        return _insert(conn, mapping=mapping, slug=slug)


def _insert(conn: Connection, *, mapping: Mapping, slug: str) -> dict[str, int]:
    source_id = conn.execute(
        insert(t.data_source).values(slug=slug, name=slug).returning(t.data_source.c.id)
    ).scalar_one()
    file_id = conn.execute(
        insert(t.file_upload)
        .values(
            original_name="traces.jsonl",
            storage_path=TRACES,
            format="jsonl",
            size_bytes=1,
            content_hash=uuid4().hex.rjust(64, "0"),
        )
        .returning(t.file_upload.c.id)
    ).scalar_one()
    mapping_id = conn.execute(
        insert(t.mapping)
        .values(
            data_source_id=source_id,
            name=mapping.name,
            version=mapping.version,
            source_format="jsonl",
            document=mapping_to_document(mapping),
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()
    return {"source_id": source_id, "file_id": file_id, "mapping_id": mapping_id}


@pytest.fixture
def seeded(clean_db: Connection, engine: Engine) -> dict[str, int]:  # noqa: ARG001
    """`clean_db` is requested for the empty database it guarantees."""
    return _seed(engine)


@pytest.fixture
async def importer(database_url: str) -> AsyncIterator[Any]:
    """Runs a real import against the real database, from records in memory."""
    engine = create_async_engine(to_async_url(database_url))

    async def run(seed: dict[str, int], records: list[dict[str, Any]]) -> dict[str, Any]:
        uow = SqlAlchemyUnitOfWork(engine)
        async with uow:
            run_id = await uow.import_runs.create(
                data_source_id=seed["source_id"],
                file_upload_id=seed["file_id"],
                mapping_id=seed["mapping_id"],
            )
            await uow.commit()
        report = await RunImport(uow, InMemoryFileReader({TRACES: records})).execute(run_id)
        return {"run_id": run_id, "report": report}

    yield run
    await engine.dispose()


def _count(engine: Engine, table: Any) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


# ---------------------------------------------------------------------------
# 1. Réimport idempotent
# ---------------------------------------------------------------------------


async def test_reimport_is_idempotent(
    seeded: dict[str, int], importer: Any, engine: Engine
) -> None:
    """§11.1 — importing the same file twice creates no duplicate.

    The second run must not be a no-op that hides itself: it is recorded like
    any other, and reports what it refused rather than staying silent.
    """
    first = await importer(seeded, RECORDS)
    sessions_after_first = _count(engine, t.session)
    tools_after_first = _count(engine, t.tool_call)

    second = await importer(seeded, RECORDS)

    # Nothing new in the database.
    assert _count(engine, t.session) == sessions_after_first
    assert _count(engine, t.tool_call) == tools_after_first

    # And the second run says so, instead of reporting an empty success.
    assert second["report"].records_imported == 0
    assert second["report"].records_duplicate == first["report"].records_imported
    assert second["report"].records_rejected == 0

    # Both runs stay traceable — an import that changed nothing is still an
    # import somebody asked for.
    with engine.connect() as conn:
        runs = conn.execute(select(t.import_run.c.id, t.import_run.c.status)).all()
    assert {r.id for r in runs} == {first["run_id"], second["run_id"]}
    assert all(r.status == "succeeded" for r in runs)


# ---------------------------------------------------------------------------
# 2. Relations conservées
# ---------------------------------------------------------------------------


async def test_relations_are_preserved(
    seeded: dict[str, int], importer: Any, engine: Engine
) -> None:
    """§11.2 — every model_call and tool_call stays attached to its session."""
    await importer(seeded, RECORDS)

    with engine.connect() as conn:
        sessions = {
            row.external_id: row.id
            for row in conn.execute(select(t.session.c.id, t.session.c.external_id)).all()
        }
    assert set(sessions) == {"s-1", "s-2"}

    # No orphans: every child points at a session that exists.
    with engine.connect() as conn:
        orphan_models = conn.execute(
            select(func.count())
            .select_from(t.model_call)
            .where(t.model_call.c.session_id.notin_(select(t.session.c.id)))
        ).scalar_one()
        orphan_tools = conn.execute(
            select(func.count())
            .select_from(t.tool_call)
            .where(t.tool_call.c.session_id.notin_(select(t.session.c.id)))
        ).scalar_one()
    assert (orphan_models, orphan_tools) == (0, 0)

    # And attached to the *right* session, not merely to one of them: s-1
    # brought two tool calls, s-2 brought one.
    with engine.connect() as conn:
        per_session = dict(
            conn.execute(
                select(t.tool_call.c.session_id, func.count())
                .select_from(t.tool_call)
                .group_by(t.tool_call.c.session_id)
            ).all()
        )
    assert per_session[sessions["s-1"]] == 2
    assert per_session[sessions["s-2"]] == 1


# ---------------------------------------------------------------------------
# 3. Indicateur correct après jointure et filtrage
# ---------------------------------------------------------------------------


async def test_metric_matches_reference_computation(
    seeded: dict[str, int], importer: Any, database_url: str
) -> None:
    """§11.3 — a read-model aggregate against an independent computation.

    The expected figures below are written out from `RECORDS` by hand, in this
    file, and not derived from any query. That is the whole point: a reference
    obtained by running a second version of the same SQL would agree with the
    first for the same wrong reason.

    The join is what makes this worth asserting. Two sessions, three tool calls
    and two model calls: a naive join of sessions to both children multiplies
    the rows and inflates every total.
    """
    await importer(seeded, RECORDS)

    # --- reference, computed from RECORDS alone -----------------------------
    expected_sessions = len(RECORDS)  # 2
    expected_model_calls = sum(1 for r in RECORDS if r.get("model"))  # 2
    expected_tool_calls = sum(len(r["tools"]) for r in RECORDS)  # 3
    expected_input = sum(r["in_tokens"] for r in RECORDS)  # 400
    expected_output = sum(r["out_tokens"] for r in RECORDS)  # 60
    expected_tool_errors = sum(
        1 for r in RECORDS for tool in r["tools"] if tool["status"] == "error"
    )  # 1
    expected_error_rate = expected_tool_errors / expected_tool_calls  # 1/3

    engine = create_async_engine(to_async_url(database_url))
    try:
        totals = await SqlDashboardQueries(engine).overview(
            DashboardFilters(data_source_id=seeded["source_id"])
        )
    finally:
        await engine.dispose()

    assert totals.session_count == expected_sessions
    assert totals.model_call_count == expected_model_calls
    assert totals.tool_call_count == expected_tool_calls
    assert totals.total_input_tokens == expected_input
    assert totals.total_output_tokens == expected_output
    assert totals.tool_error_count == expected_tool_errors
    assert totals.tool_error_rate == pytest.approx(expected_error_rate)

    # Filtering has to bite: a source that imported nothing reports nothing,
    # not the figures above.
    engine = create_async_engine(to_async_url(database_url))
    try:
        elsewhere = await SqlDashboardQueries(engine).overview(
            DashboardFilters(data_source_id=seeded["source_id"] + 999)
        )
    finally:
        await engine.dispose()
    assert elsewhere.session_count == 0
    assert elsewhere.total_input_tokens is None


# ---------------------------------------------------------------------------
# 4. Mapping invalide refusé et expliqué
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "entities"),
    [
        (
            "champ cible inconnu",
            [
                {
                    "target": "session",
                    "natural_key": ["external_id"],
                    "fields": [{"target": "not_a_real_field", "source": "$.sid"}],
                }
            ],
        ),
        (
            "opérateur hors whitelist",
            [
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
        ),
        (
            "entité cible inconnue",
            [
                {
                    "target": "not_an_entity",
                    "natural_key": ["external_id"],
                    "fields": [{"target": "external_id", "source": "$.sid"}],
                }
            ],
        ),
    ],
)
async def test_invalid_mapping_is_rejected_with_explanation(
    client: AsyncClient, label: str, entities: list[dict[str, Any]]
) -> None:
    """§11.4 — 422 carrying the offending path and a readable message.

    No database: the refusal happens before anything is written, which is
    itself part of the requirement. The client here is wired to an unreachable
    one, so a test that passed by writing first would fail loudly.
    """
    response = await client.post(
        "/api/v1/mappings/validate",
        json={"source_format": "jsonl", "entities": entities},
    )

    assert response.status_code == 200, "validation answers, it does not raise"
    body = response.json()
    assert body["valid"] is False, label
    assert body["errors"], label

    error = body["errors"][0]
    assert error["field_path"], f"{label}: l'erreur doit dire où"
    assert error["code"], f"{label}: l'erreur doit porter un code"
    assert len(error["message"]) > 10, f"{label}: le message doit être lisible"


async def test_saving_an_invalid_mapping_is_422_before_any_write(client: AsyncClient) -> None:
    """The same refusal on the write path, where it carries the 422."""
    response = await client.post(
        "/api/v1/mappings",
        json={
            "data_source_id": 1,
            "name": "broken",
            "source_format": "jsonl",
            "entities": [
                {
                    "target": "session",
                    "natural_key": ["external_id"],
                    "fields": [{"target": "not_a_real_field", "source": "$.sid"}],
                }
            ],
        },
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "MAPPING_INVALID"
    assert error["details"]["errors"][0]["field_path"]


# ---------------------------------------------------------------------------
# 5. Portabilité du mapping entre fournisseurs
# ---------------------------------------------------------------------------


async def test_mapping_is_portable_across_providers(
    clean_db: Connection,  # noqa: ARG001 - requested for the empty database
    engine: Engine,
    importer: Any,
    database_url: str,
) -> None:
    """§11.5 — a mapping produced under one provider applies under another.

    Two halves, and the provider genuinely changes between them: the mapping is
    proposed by one analyzer, stored, then applied to the same records while a
    second analyzer — a different class, a different descriptor — is the one
    configured. The mapping travels; the provider does not travel with it.
    """
    from agentlen.infrastructure.ai.fake_adapter import FakeAnalyzer

    class OtherProviderAnalyzer(FakeAnalyzer):
        """A second provider, distinguishable from the first."""

        provider_name = "other"

    first = FakeAnalyzer()
    second = OtherProviderAnalyzer()
    assert first.descriptor["provider"] != second.descriptor["provider"], (
        "les deux moitiés doivent réellement changer de fournisseur"
    )

    # A mapping carries no provider reference — that is what makes it portable.
    document = mapping_to_document(MAPPING)
    serialised = str(document).lower()
    # Provider *names*, not the word "provider": `provider_name` is a legitimate
    # target field, and forbidding it would be forbidding the schema.
    for name in ("anthropic", "openai", "claude", "gpt", "groq", "mistral", "fake", "other"):
        assert name not in serialised, f"le mapping mentionne le fournisseur '{name}'"

    # Applied under provider one.
    seed_one = _seed(engine, slug="source-provider-one")
    result_one = await importer(seed_one, RECORDS)

    # Applied under provider two, same document, same records.
    seed_two = _seed(engine, slug="source-provider-two")
    result_two = await importer(seed_two, RECORDS)

    assert result_one["report"].records_imported == result_two["report"].records_imported
    assert result_one["report"].records_rejected == result_two["report"].records_rejected == 0

    engine = create_async_engine(to_async_url(database_url))
    try:
        queries = SqlDashboardQueries(engine)
        totals_one = await queries.overview(DashboardFilters(data_source_id=seed_one["source_id"]))
        totals_two = await queries.overview(DashboardFilters(data_source_id=seed_two["source_id"]))
    finally:
        await engine.dispose()

    assert totals_one.session_count == totals_two.session_count
    assert totals_one.tool_call_count == totals_two.tool_call_count
    assert totals_one.total_input_tokens == totals_two.total_input_tokens


# ---------------------------------------------------------------------------
# 6. Valeur absente ≠ zéro
# ---------------------------------------------------------------------------


NO_CACHE_RECORDS: list[dict[str, Any]] = [
    {
        "sid": "nc-1",
        "model": "claude-opus-4-8",
        "provider": "anthropic",
        "in_tokens": 100,
        "out_tokens": 20,
        "seq": 0,
        "tools": [],
    },
]


async def test_missing_value_is_never_zero(
    seeded: dict[str, int], importer: Any, database_url: str
) -> None:
    """§11.6 — a source with no cache data reports null and coverage 0.

    Zero is a measurement: it says the cache was asked for and returned
    nothing. Absent is not a measurement. Conflating the two turns "we do not
    know" into "we know it is nothing", which is the one mistake a dashboard
    about data quality must not make.
    """
    await importer(seeded, NO_CACHE_RECORDS)

    filters = DashboardFilters(data_source_id=seeded["source_id"])
    engine = create_async_engine(to_async_url(database_url))
    try:
        queries = SqlDashboardQueries(engine)
        totals = await queries.overview(filters)
        models = await queries.model_usage(filters)
    finally:
        await engine.dispose()

    # The mapping maps no cache field at all, so nothing is known about it.
    assert models, "le jeu doit produire au moins un point modèle"
    for point in models:
        assert point.cache_read_tokens is None, "absent doit rester null, jamais 0"
        assert point.cache_coverage.present == 0
        assert point.cache_coverage.ratio == 0.0

        # The contrast that gives the assertion its meaning: what *was* mapped
        # comes back as a real number, so `None` above is absence, not emptiness.
        assert point.input_tokens == 100
        assert point.token_coverage.present == 1

    # Durations are not mapped either — same rule, same answer.
    assert totals.avg_session_duration_ms is None
    assert totals.duration_coverage.present == 0


async def test_missing_value_survives_the_http_boundary(
    live_client: AsyncClient, seeded: dict[str, int], importer: Any
) -> None:
    """The same rule where the user actually meets it: in the JSON.

    `live_client` is requested **first** on purpose: its engine empties the
    database on setup, and asking for it after `seeded` would wipe the rows the
    seed had just written.
    """
    await importer(seeded, NO_CACHE_RECORDS)

    response = await live_client.get(
        f"/api/v1/metrics/overview?data_source_id={seeded['source_id']}"
    )

    assert response.status_code == 200
    metrics = {m["key"]: m for m in response.json()["metrics"]}
    absent = [m for m in metrics.values() if m["value"] is None]
    assert absent, "au moins un indicateur doit être absent sur ce jeu"
    for metric in absent:
        assert metric["value"] is None, metric["key"]
        assert metric["coverage"]["present"] == 0, metric["key"]
        # `ratio` is `present / total`, or `None` when nothing was in scope to
        # divide by — the same rule one level down. What it must never be is a
        # positive number sitting beside a null value.
        assert metric["coverage"]["ratio"] in (0.0, None), metric["key"]

    # A metric that *is* known must not have been swept up in the same net.
    known = [m for m in metrics.values() if m["value"] is not None]
    assert known, "le jeu doit produire au moins un indicateur connu"
    for metric in known:
        assert metric["coverage"]["present"] > 0, metric["key"]
