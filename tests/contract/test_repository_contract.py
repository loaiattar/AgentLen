"""One suite, both implementations.

A test double is only useful if a use case cannot tell it apart from the real
thing. The way to know that is not to hope — it is to run the same assertions
against both and require identical answers.

Every test below is parametrised over the in-memory unit of work and the
SQLAlchemy one. The Postgres half skips when Docker is unavailable, so
`pytest tests/unit` stays green on any machine while the contract is still
enforced wherever a database exists.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from agentlen.application.dto.persistence import ModelCallRow, SessionRow
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping, MappingProposal
from agentlen.domain.model.model_call import ModelCall, TokenUsage
from agentlen.domain.model.session import Session
from agentlen.infrastructure.persistence.engine import to_async_url
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes.repositories import InMemoryUnitOfWork
from tests.integration.conftest import requires_postgres

STARTED = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
async def in_memory() -> AsyncIterator[InMemoryUnitOfWork]:
    yield InMemoryUnitOfWork()


@pytest.fixture
async def sql(database_url: str, clean_db: Any) -> AsyncIterator[SqlAlchemyUnitOfWork]:
    engine = create_async_engine(to_async_url(database_url))
    yield SqlAlchemyUnitOfWork(engine)
    await engine.dispose()


@pytest.fixture(params=["in_memory", pytest.param("sql", marks=requires_postgres)])
def uow(request: pytest.FixtureRequest) -> Any:
    """Each test runs twice: once per implementation."""
    return request.getfixturevalue(request.param)


async def _provenance(uow: Any) -> dict[str, int]:
    """The chain a fact row needs, created through the repositories themselves."""
    source_id = await uow.data_sources.create(slug="tracelab", name="TraceLab")
    if hasattr(uow, "_engine"):  # SQL: file_upload and mapping have no repository yet
        from sqlalchemy import insert

        from agentlen.infrastructure.persistence import tables as t

        file_id = (
            await uow._conn.execute(
                insert(t.file_upload)
                .values(
                    original_name="s.jsonl",
                    storage_path="/srv/s.jsonl",
                    format="jsonl",
                    size_bytes=1,
                    content_hash="a" * 64,
                )
                .returning(t.file_upload.c.id)
            )
        ).scalar_one()
        mapping_id = (
            await uow._conn.execute(
                insert(t.mapping)
                .values(
                    data_source_id=source_id,
                    name="m",
                    version=1,
                    source_format="jsonl",
                    document={},
                    status="active",
                )
                .returning(t.mapping.c.id)
            )
        ).scalar_one()
    else:
        file_id, mapping_id = 1, 1

    run_id = await uow.import_runs.create(
        data_source_id=source_id, file_upload_id=file_id, mapping_id=mapping_id
    )
    raw = await uow.raw_records.add_many(import_run_id=run_id, records=[(1, {"sid": "a"})])
    return {"source": source_id, "run": run_id, "raw": raw[1]}


def _session(source_id: int, external_id: str) -> Session:
    return Session(
        id=uuid4(),
        data_source_id=source_id,
        external_id=external_id,
        started_at=STARTED,
        duration_ms=1000,
    )


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


async def test_inserting_the_same_session_twice_reports_a_duplicate(uow: Any) -> None:
    """Re-importing is expected. The second insert must be a no-op that says so,
    not an error and not a second row."""
    async with uow:
        p = await _provenance(uow)
        entity = _session(p["source"], "s1")
        row = SessionRow(entity=entity, import_run_id=p["run"], raw_record_id=p["raw"])

        first = await uow.sessions.add_many([row])
        # A re-import is a new run. The same session again within one run is
        # not a duplicate but the same session (#123).
        second = await uow.sessions.add_many(
            [
                SessionRow(
                    entity=_session(p["source"], "s1"),
                    import_run_id=await _second_run(uow, p),
                    raw_record_id=p["raw"],
                )
            ]
        )

        assert first.inserted_count == 1
        assert first.duplicate_count == 0
        assert second.inserted_count == 0
        assert second.duplicate_count == 1
        assert await uow.sessions.count() == 1
        await uow.commit()


async def test_same_external_id_in_two_sources_is_not_a_duplicate(uow: Any) -> None:
    """The key is (source, external_id). Two datasets may reuse an identifier."""
    async with uow:
        p = await _provenance(uow)
        other = await uow.data_sources.create(slug="swe-chat", name="SWE-chat")

        outcome = await uow.sessions.add_many(
            [
                SessionRow(
                    entity=_session(p["source"], "shared"),
                    import_run_id=p["run"],
                    raw_record_id=p["raw"],
                ),
                SessionRow(
                    entity=_session(other, "shared"), import_run_id=p["run"], raw_record_id=p["raw"]
                ),
            ]
        )

        assert outcome.inserted_count == 2
        assert outcome.duplicate_count == 0
        await uow.commit()


async def test_duplicate_sequence_index_within_a_session_is_reported(uow: Any) -> None:
    async with uow:
        p = await _provenance(uow)
        entity = _session(p["source"], "s1")
        inserted = await uow.sessions.add_many(
            [SessionRow(entity=entity, import_run_id=p["run"], raw_record_id=p["raw"])]
        )

        def call() -> ModelCallRow:
            return ModelCallRow(
                entity=ModelCall(
                    id=uuid4(),
                    session_id=entity.id,
                    sequence_index=0,
                    token_usage=TokenUsage(input_tokens=10, output_tokens=2),
                    status="ok",
                ),
                raw_record_id=p["raw"],
            )

        first = await uow.model_calls.add_many([call()], session_ids=inserted.assigned)
        second = await uow.model_calls.add_many([call()], session_ids=inserted.assigned)

        assert first.inserted_count == 1
        assert second.duplicate_count == 1
        await uow.commit()


async def _second_run(uow: Any, p: dict[str, int]) -> int:
    """Another import run on the same file — what a re-import creates."""
    run = await uow.import_runs.get(p["run"])
    return int(
        await uow.import_runs.create(
            data_source_id=run["data_source_id"],
            file_upload_id=run["file_upload_id"],
            mapping_id=run["mapping_id"],
        )
    )


def _model_call(session: Session, sequence_index: int, raw: int) -> ModelCallRow:
    return ModelCallRow(
        entity=ModelCall(
            id=uuid4(),
            session_id=session.id,
            sequence_index=sequence_index,
            token_usage=TokenUsage(input_tokens=10, output_tokens=2),
            status="ok",
        ),
        raw_record_id=raw,
    )


async def test_a_session_already_imported_gives_its_id_to_new_calls(uow: Any) -> None:
    """#123. A session stored by an earlier import is a duplicate, and the calls
    a new file brings for it must still attach to it instead of vanishing."""
    async with uow:
        p = await _provenance(uow)
        first = await uow.sessions.add_many(
            [
                SessionRow(
                    entity=_session(p["source"], "s1"),
                    import_run_id=p["run"],
                    raw_record_id=p["raw"],
                )
            ]
        )
        later = _session(p["source"], "s1")
        second = await uow.sessions.add_many(
            [
                SessionRow(
                    entity=later, import_run_id=await _second_run(uow, p), raw_record_id=p["raw"]
                )
            ]
        )
        calls = await uow.model_calls.add_many(
            [_model_call(later, 1, p["raw"])], session_ids=second.ids
        )

        assert second.inserted_count == 0
        assert second.duplicate_count == 1
        assert second.ids[later.id] == next(iter(first.assigned.values()))
        assert calls.inserted_count == 1
        assert calls.duplicate_count == 0
        await uow.commit()


async def test_a_session_repeated_within_one_run_is_one_insert_and_no_duplicate(
    uow: Any,
) -> None:
    """#123. TraceLab repeats the session on every line. Those lines, in one batch
    or across batches of the same run, describe one session: one row, no duplicate."""
    async with uow:
        p = await _provenance(uow)
        a, b, c = (_session(p["source"], "s1") for _ in range(3))
        same_batch = await uow.sessions.add_many(
            [
                SessionRow(entity=a, import_run_id=p["run"], raw_record_id=p["raw"]),
                SessionRow(entity=b, import_run_id=p["run"], raw_record_id=p["raw"]),
            ]
        )
        next_batch = await uow.sessions.add_many(
            [SessionRow(entity=c, import_run_id=p["run"], raw_record_id=p["raw"])]
        )

        assert same_batch.inserted_count == 1
        assert same_batch.duplicate_count == 0
        assert same_batch.ids[a.id] == same_batch.ids[b.id]
        assert next_batch.inserted_count == 0
        assert next_batch.duplicate_count == 0
        assert next_batch.ids[c.id] == same_batch.ids[a.id]
        assert await uow.sessions.count() == 1
        await uow.commit()


async def test_the_same_call_twice_in_one_batch_is_one_insert_and_one_duplicate(uow: Any) -> None:
    """A call is an event: the same key twice is the same call recorded twice."""
    async with uow:
        p = await _provenance(uow)
        session = _session(p["source"], "s1")
        sessions = await uow.sessions.add_many(
            [SessionRow(entity=session, import_run_id=p["run"], raw_record_id=p["raw"])]
        )
        outcome = await uow.model_calls.add_many(
            [_model_call(session, 0, p["raw"]), _model_call(session, 0, p["raw"])],
            session_ids=sessions.ids,
        )

        assert outcome.inserted_count == 1
        assert outcome.duplicate_count == 1
        await uow.commit()


async def test_a_call_whose_session_is_unknown_is_unlinked_not_a_duplicate(uow: Any) -> None:
    """#123. Counting such a call as "already imported" is how calls used to vanish."""
    async with uow:
        p = await _provenance(uow)
        orphan = _model_call(_session(p["source"], "never-stored"), 0, p["raw"])

        outcome = await uow.model_calls.add_many([orphan], session_ids={})

        assert outcome.inserted_count == 0
        assert outcome.duplicate_count == 0
        assert outcome.unlinked == (orphan.entity.id,)
        await uow.commit()


@pytest.mark.parametrize("bind_limit", [32_767, 40], ids=["one-statement", "split"])
async def test_outcomes_do_not_depend_on_how_many_statements_a_batch_takes(
    uow: Any, bind_limit: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#136. asyncpg binds at most 32 767 parameters per statement, so the SQL
    side splits large batches. Forty parameters is a few rows per INSERT and
    twenty keys per lookup: RETURNING, stored keys, in-batch repeats and orphans
    all cross a slice boundary, and must still be counted as in one statement."""
    from agentlen.domain.model.import_run import ImportIssue
    from agentlen.infrastructure.persistence.repositories import sql as sql_repositories

    monkeypatch.setattr(sql_repositories, "MAX_BIND_PARAMETERS", bind_limit)
    async with uow:
        p = await _provenance(uow)
        earlier = [_session(p["source"], f"s{i}") for i in range(25)]
        stored = await uow.sessions.add_many(
            [SessionRow(entity=s, import_run_id=p["run"], raw_record_id=p["raw"]) for s in earlier]
        )
        first_calls = [_model_call(earlier[0], i, p["raw"]) for i in range(25)]
        earlier_calls = await uow.model_calls.add_many(first_calls, session_ids=stored.ids)

        rerun = await _second_run(uow, p)
        batch = [_session(p["source"], f"s{i}") for i in range(30)]
        repeat = _session(p["source"], "s27")
        sessions = await uow.sessions.add_many(
            [
                SessionRow(entity=s, import_run_id=rerun, raw_record_id=p["raw"])
                for s in [*batch, repeat]
            ]
        )
        calls = [_model_call(batch[0], i, p["raw"]) for i in range(30)]
        repeated_call = _model_call(batch[0], 27, p["raw"])
        orphan = _model_call(_session(p["source"], "never-stored"), 0, p["raw"])
        outcome = await uow.model_calls.add_many(
            [*calls, repeated_call, orphan], session_ids=sessions.ids
        )

        raw = await uow.raw_records.add_many(
            import_run_id=rerun, records=[(line, {"line": line}) for line in range(1, 31)]
        )
        await uow.import_issues.add_many(
            import_run_id=rerun,
            issues=[
                (
                    ImportIssue(severity="rejected", code="CAST_FAILED", message=f"m{line}"),
                    raw[line],
                )
                for line in range(1, 31)
            ],
        )
        await uow.commit()

    assert (sessions.inserted_count, sessions.duplicate_count, len(sessions.ids)) == (5, 25, 31)
    assert sessions.ids[repeat.id] == sessions.assigned[batch[27].id]
    assert sessions.ids[batch[3].id] == stored.assigned[earlier[3].id]
    assert (outcome.inserted_count, outcome.duplicate_count) == (5, 26)
    assert outcome.unlinked == (orphan.entity.id,)
    assert outcome.ids[repeated_call.entity.id] == outcome.assigned[calls[27].entity.id]
    assert outcome.ids[calls[3].entity.id] == earlier_calls.assigned[first_calls[3].entity.id]
    assert sorted(raw) == list(range(1, 31))
    async with uow:
        listed = await uow.import_issues.list(import_run_id=rerun, limit=50)
    assert [(r.issue.message, r.issue.line_number) for r in listed] == [
        (f"m{line}", line) for line in range(1, 31)
    ]


# ---------------------------------------------------------------------------
# Absent is not zero, all the way down to storage
# ---------------------------------------------------------------------------


async def test_unknown_token_counts_round_trip_as_none(uow: Any) -> None:
    async with uow:
        p = await _provenance(uow)
        entity = _session(p["source"], "s1")
        inserted = await uow.sessions.add_many(
            [SessionRow(entity=entity, import_run_id=p["run"], raw_record_id=p["raw"])]
        )
        await uow.model_calls.add_many(
            [
                ModelCallRow(
                    entity=ModelCall(
                        id=uuid4(),
                        session_id=entity.id,
                        sequence_index=0,
                        token_usage=TokenUsage(),
                        status="unknown",
                    ),
                    raw_record_id=p["raw"],
                )
            ],
            session_ids=inserted.assigned,
        )
        await uow.commit()

    async with uow:
        stored = await uow.sessions.get(list(inserted.assigned.values())[0])
        assert stored is not None
        assert stored.external_id == "s1"


async def test_a_session_without_duration_stays_none(uow: Any) -> None:
    async with uow:
        p = await _provenance(uow)
        entity = Session(
            id=uuid4(),
            data_source_id=p["source"],
            external_id="s1",
            started_at=None,
            duration_ms=None,
        )
        outcome = await uow.sessions.add_many(
            [SessionRow(entity=entity, import_run_id=p["run"], raw_record_id=p["raw"])]
        )
        await uow.commit()

    async with uow:
        stored = await uow.sessions.get(outcome.assigned[entity.id])
        assert stored is not None
        assert stored.duration_ms is None
        assert stored.started_at is None


async def test_a_session_without_start_takes_its_earliest_dated_call(uow: Any) -> None:
    """#200. A source that dates only its calls still dates its sessions, by the
    earliest call, model or tool. A stored start is kept, and a session with no
    dated call stays undated: nothing is invented."""
    from agentlen.application.dto.persistence import ToolCallRow
    from agentlen.domain.model.tool_call import ToolCall

    tool_at = datetime(2026, 6, 1, 5, 40, tzinfo=UTC)
    model_at = datetime(2026, 6, 1, 5, 41, tzinfo=UTC)
    async with uow:
        p = await _provenance(uow)
        undated = Session(id=uuid4(), data_source_id=p["source"], external_id="undated")
        mapped = _session(p["source"], "mapped")
        callless = Session(id=uuid4(), data_source_id=p["source"], external_id="callless")
        sessions = await uow.sessions.add_many(
            [
                SessionRow(entity=s, import_run_id=p["run"], raw_record_id=p["raw"])
                for s in (undated, mapped, callless)
            ]
        )
        await uow.model_calls.add_many(
            [
                ModelCallRow(
                    entity=ModelCall(
                        id=uuid4(),
                        session_id=session.id,
                        sequence_index=index,
                        token_usage=TokenUsage(),
                        status="ok",
                        started_at=at,
                    ),
                    raw_record_id=p["raw"],
                )
                for session, index, at in (
                    (undated, 0, model_at),
                    (undated, 1, None),
                    (mapped, 0, tool_at),
                    (callless, 0, None),
                )
            ],
            session_ids=sessions.ids,
        )
        await uow.tool_calls.add_many(
            [
                ToolCallRow(
                    entity=ToolCall(
                        id=uuid4(),
                        session_id=undated.id,
                        sequence_index=0,
                        tool_name="Bash",
                        status="ok",
                        started_at=tool_at,
                    ),
                    raw_record_id=p["raw"],
                    tool_id=await uow.referentials.resolve("tool", "Bash"),
                )
            ],
            session_ids=sessions.ids,
        )
        ids = list(sessions.ids.values())
        assert await uow.sessions.fill_missing_started_at(ids) == 1
        assert await uow.sessions.fill_missing_started_at(ids) == 0, "a derived start is kept"
        await uow.commit()

    async with uow:
        stored = {
            s.external_id: await uow.sessions.get(sessions.ids[s.id])
            for s in (undated, mapped, callless)
        }
        assert stored["undated"] is not None and stored["undated"].started_at == tool_at
        assert stored["mapped"] is not None and stored["mapped"].started_at == STARTED
        assert stored["callless"] is not None and stored["callless"].started_at is None


# ---------------------------------------------------------------------------
# Transaction boundary
# ---------------------------------------------------------------------------


async def test_leaving_without_commit_writes_nothing(uow: Any) -> None:
    """The default is rollback: an early return must not half-commit."""
    async with uow:
        p = await _provenance(uow)
        await uow.sessions.add_many(
            [
                SessionRow(
                    entity=_session(p["source"], "s1"),
                    import_run_id=p["run"],
                    raw_record_id=p["raw"],
                )
            ]
        )
        # deliberately no commit

    async with uow:
        assert await uow.sessions.count() == 0


async def test_an_exception_mid_import_leaves_the_database_untouched(uow: Any) -> None:
    """A half-imported file is worse than a failed one — nothing tells you
    which half you got."""
    boom = RuntimeError("disk on fire")
    with pytest.raises(RuntimeError):
        async with uow:
            p = await _provenance(uow)
            await uow.sessions.add_many(
                [
                    SessionRow(
                        entity=_session(p["source"], "s1"),
                        import_run_id=p["run"],
                        raw_record_id=p["raw"],
                    )
                ]
            )
            raise boom

    async with uow:
        assert await uow.sessions.count() == 0


# ---------------------------------------------------------------------------
# Referentials
# ---------------------------------------------------------------------------


async def test_the_same_name_resolves_to_the_same_row(uow: Any) -> None:
    async with uow:
        first = await uow.referentials.resolve("tool", "Bash")
        second = await uow.referentials.resolve("tool", "Bash")
        assert first == second
        await uow.commit()


async def test_a_model_name_is_keyed_by_its_provider(uow: Any) -> None:
    """DATA_MODEL.md §4: model is unique on (provider_id, name). Two providers
    publishing a same-named model must not collapse into one row."""
    async with uow:
        anthropic = await uow.referentials.resolve(
            "model", "shared-name", context={"provider_name": "anthropic"}
        )
        openai = await uow.referentials.resolve(
            "model", "shared-name", context={"provider_name": "openai"}
        )
        assert anthropic != openai
        await uow.commit()


async def test_an_agent_without_version_resolves_to_one_row_across_transactions(
    uow: Any,
) -> None:
    """No mapping provides an agent version, so the key is (name, NULL).

    Each import run resolves it in its own transaction with a fresh cache: the
    second run must find the first run's row, not create another (issue #137).
    A known version is still a different agent.
    """
    async with uow:
        first = await uow.referentials.resolve("agent", "claude-code")
        await uow.commit()
    async with uow:
        second = await uow.referentials.resolve("agent", "claude-code")
        versioned = await uow.referentials.resolve(
            "agent", "claude-code", context={"version": "1.0"}
        )
        await uow.commit()

    assert second == first
    assert versioned != first


# ---------------------------------------------------------------------------
# Import report and issues
# ---------------------------------------------------------------------------


async def test_the_import_report_round_trips(uow: Any) -> None:
    from agentlen.domain.model.import_run import ImportReport

    async with uow:
        p = await _provenance(uow)
        report = ImportReport(
            records_read=100, records_imported=90, records_duplicate=7, records_rejected=3
        )
        await uow.import_runs.save_report(p["run"], report, status="partial")
        await uow.commit()

    async with uow:
        stored = await uow.import_runs.get_report(p["run"])
        assert stored is not None
        assert stored.records_read == 100
        assert stored.records_rejected == 3


async def test_issues_are_listed_and_filterable_by_severity(uow: Any) -> None:
    from agentlen.domain.model.import_run import ImportIssue

    async with uow:
        p = await _provenance(uow)
        await uow.import_issues.add_many(
            import_run_id=p["run"],
            issues=[
                (ImportIssue(severity="rejected", code="CAST_FAILED", message="nope"), p["raw"]),
                (ImportIssue(severity="duplicate", code="DUPLICATE", message="seen"), p["raw"]),
            ],
        )
        await uow.commit()

    async with uow:
        assert len(await uow.import_issues.list(import_run_id=p["run"])) == 2
        rejected = await uow.import_issues.list(import_run_id=p["run"], severity="rejected")
        assert len(rejected) == 1
        assert rejected[0].issue.code == "CAST_FAILED"


async def test_issues_read_their_line_number_from_the_linked_raw_record(uow: Any) -> None:
    """`import_issue` stores no line: it comes back from the raw_record the
    issue points at. An issue with no raw_record keeps a null line, never 0."""
    from agentlen.domain.model.import_run import ImportIssue

    async with uow:
        p = await _provenance(uow)
        raw = await uow.raw_records.add_many(import_run_id=p["run"], records=[(7, {"sid": "b"})])
        await uow.import_issues.add_many(
            import_run_id=p["run"],
            issues=[
                (ImportIssue(severity="rejected", code="CAST_FAILED", message="nope"), raw[7]),
                (ImportIssue(severity="duplicate", code="ALREADY_IMPORTED", message="seen"), None),
            ],
        )
        await uow.commit()

    async with uow:
        listed = await uow.import_issues.list(import_run_id=p["run"])

    assert [(r.issue.line_number, r.raw_record_id) for r in listed] == [
        (7, raw[7]),
        (None, None),
    ]


async def test_import_run_list_returns_most_recent_first_and_count_matches(uow: Any) -> None:
    async with uow:
        p = await _provenance(uow)
        second_run = await uow.import_runs.create(
            data_source_id=p["source"], file_upload_id=1, mapping_id=1
        )
        await uow.commit()

    async with uow:
        history = await uow.import_runs.list(limit=50, offset=0)
        total = await uow.import_runs.count()

    ids = [row["id"] for row in history]
    assert ids.index(second_run) < ids.index(p["run"])
    assert total == len(history)


async def test_import_run_list_is_paginated(uow: Any) -> None:
    async with uow:
        p = await _provenance(uow)
        for _ in range(2):
            await uow.import_runs.create(data_source_id=p["source"], file_upload_id=1, mapping_id=1)
        await uow.commit()

    async with uow:
        total = await uow.import_runs.count()
        page = await uow.import_runs.list(limit=1, offset=0)

    assert total >= 3
    assert len(page) == 1


# ---------------------------------------------------------------------------
# Data sources (issue #50)
# ---------------------------------------------------------------------------


async def test_created_data_source_is_retrievable_by_id_with_its_full_record(uow: Any) -> None:
    async with uow:
        source_id = await uow.data_sources.create(
            slug="tracelab",
            name="TraceLab",
            description="Traces d'agents de developpement IA",
            url="https://github.com/uw-syfi/TraceLab",
            license="MIT",
            dataset_version="v0.0.1",
            retrieved_at=date(2026, 9, 7),
        )
        await uow.commit()

    async with uow:
        record = await uow.data_sources.get_by_id(source_id)

    assert record is not None
    assert record.slug == "tracelab"
    assert record.name == "TraceLab"
    assert record.dataset_version == "v0.0.1"
    assert record.retrieved_at == date(2026, 9, 7)


async def test_get_by_id_returns_none_for_an_unknown_id(uow: Any) -> None:
    async with uow:
        assert await uow.data_sources.get_by_id(999_999) is None


async def test_list_returns_every_declared_source(uow: Any) -> None:
    async with uow:
        await uow.data_sources.create(slug="tracelab", name="TraceLab")
        await uow.data_sources.create(slug="swe-chat", name="SWE-chat")
        await uow.commit()

    async with uow:
        records = await uow.data_sources.list()

    slugs = {r.slug for r in records}
    assert {"tracelab", "swe-chat"} <= slugs


async def test_creating_the_same_slug_twice_returns_the_existing_row_not_a_second_one(
    uow: Any,
) -> None:
    async with uow:
        first_id = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        second_id = await uow.data_sources.create(slug="tracelab", name="TraceLab (retry)")
        await uow.commit()

    assert first_id == second_id
    async with uow:
        records = await uow.data_sources.list()
    assert sum(1 for r in records if r.slug == "tracelab") == 1


# ---------------------------------------------------------------------------
# Mappings (issue #52)
# ---------------------------------------------------------------------------


def _mapping(*, name: str = "tracelab-jsonl") -> Mapping:
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


async def test_saved_mapping_is_retrievable_by_id_with_its_full_record(uow: Any) -> None:
    async with uow:
        source_id = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        mapping_id = await uow.mappings.save(_mapping(), data_source_id=source_id)
        await uow.commit()

    async with uow:
        record = await uow.mappings.get_by_id(mapping_id)

    assert record is not None
    assert record["data_source_id"] == source_id
    assert record["name"] == "tracelab-jsonl"
    assert record["version"] == 1
    assert record["status"] == "active"
    assert record["document"]["entities"][0]["target"] == "session"


async def test_get_by_id_returns_none_for_an_unknown_mapping(uow: Any) -> None:
    async with uow:
        record = await uow.mappings.get_by_id(999999)

    assert record is None


async def test_list_records_is_filterable_by_data_source_and_paginated(uow: Any) -> None:
    async with uow:
        source_id = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        other_source_id = await uow.data_sources.create(slug="swe-chat", name="SWE-chat")
        await uow.mappings.save(_mapping(name="a"), data_source_id=source_id)
        await uow.mappings.save(_mapping(name="b"), data_source_id=source_id)
        await uow.mappings.save(_mapping(name="c"), data_source_id=other_source_id)
        await uow.commit()

    async with uow:
        for_source = await uow.mappings.list_records(data_source_id=source_id, limit=50, offset=0)
        total_for_source = await uow.mappings.count(data_source_id=source_id)
        one_page = await uow.mappings.list_records(data_source_id=source_id, limit=1, offset=0)

    assert total_for_source == 2
    assert len(for_source) == 2
    assert len(one_page) == 1


async def test_supersede_changes_the_status_and_leaves_the_document_untouched(uow: Any) -> None:
    async with uow:
        source_id = await uow.data_sources.create(slug="tracelab", name="TraceLab")
        mapping_id = await uow.mappings.save(_mapping(), data_source_id=source_id)
        await uow.commit()

    async with uow:
        await uow.mappings.supersede(mapping_id)
        await uow.commit()

    async with uow:
        record = await uow.mappings.get_by_id(mapping_id)

    assert record is not None
    assert record["status"] == "superseded"
    assert record["document"]["entities"][0]["target"] == "session"


# ---------------------------------------------------------------------------
# Mapping proposals — the conversation the AI and the operator have
# ---------------------------------------------------------------------------


def _proposal(mapping: Mapping | None = None) -> MappingProposal:
    return MappingProposal(
        mapping=mapping or _mapping(name="proposed"),
        rationale=("sid ressemble à un identifiant de session",),
        ambiguities=("duration_ms vient peut-être de latency",),
        unmapped_fields=("$.debug",),
        analyzer_descriptor={"provider": "fake", "model": "test", "prompt_version": "test"},
    )


async def _file_upload_id(uow: Any) -> int:
    """A file row to hang a proposal on. SQL enforces the foreign key."""
    if not hasattr(uow, "_engine"):
        return 1
    from sqlalchemy import insert

    from agentlen.infrastructure.persistence import tables as t

    return int(
        (
            await uow._conn.execute(
                insert(t.file_upload)
                .values(
                    original_name="p.jsonl",
                    storage_path="/srv/p.jsonl",
                    format="jsonl",
                    size_bytes=1,
                    content_hash=uuid4().hex * 2,
                )
                .returning(t.file_upload.c.id)
            )
        ).scalar_one()
    )


async def test_a_proposal_round_trips_with_its_rationale_and_ambiguities(uow: Any) -> None:
    async with uow:
        file_id = await _file_upload_id(uow)
        proposal_id = await uow.mapping_proposals.save(_proposal(), file_upload_id=file_id)
        await uow.commit()

    async with uow:
        stored = await uow.mapping_proposals.get(proposal_id)

    assert stored is not None
    assert stored.mapping.entities[0].fields[0].source == "$.sid"
    assert stored.rationale == ("sid ressemble à un identifiant de session",)
    assert stored.ambiguities == ("duration_ms vient peut-être de latency",)
    assert stored.unmapped_fields == ("$.debug",)


async def test_an_unknown_proposal_is_none_not_an_error(uow: Any) -> None:
    async with uow:
        assert await uow.mapping_proposals.get(999999) is None


async def test_update_replaces_the_document_and_keeps_the_id(uow: Any) -> None:
    async with uow:
        file_id = await _file_upload_id(uow)
        proposal_id = await uow.mapping_proposals.save(_proposal(), file_upload_id=file_id)
        await uow.commit()

    refined = _proposal(_mapping(name="refined"))
    async with uow:
        await uow.mapping_proposals.update(proposal_id, refined)
        await uow.commit()

    async with uow:
        stored = await uow.mapping_proposals.get(proposal_id)

    assert stored is not None
    assert stored.mapping.name == "refined"


async def test_the_message_window_returns_the_last_turns_in_reading_order(uow: Any) -> None:
    """`RefineMapping` replays the tail of the conversation into the next prompt.

    Two things have to hold whatever the implementation: the window is the
    *last* N turns, and they come back oldest-first — a transcript read
    backwards would tell the model the opposite of what happened.
    """
    async with uow:
        file_id = await _file_upload_id(uow)
        proposal_id = await uow.mapping_proposals.save(_proposal(), file_upload_id=file_id)
        for index in range(7):
            await uow.mapping_proposals.add_message(
                proposal_id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"turn-{index}",
            )
        await uow.commit()

    async with uow:
        window = await uow.mapping_proposals.list_messages(proposal_id, limit=3)
        everything = await uow.mapping_proposals.list_messages(proposal_id, limit=50)

    assert [m["content"] for m in window] == ["turn-4", "turn-5", "turn-6"]
    assert [m["turn_index"] for m in window] == [4, 5, 6]
    assert [m["role"] for m in window] == ["user", "assistant", "user"]
    assert len(everything) == 7


async def test_a_non_positive_message_limit_returns_nothing(uow: Any) -> None:
    """The two implementations used to disagree here.

    The fake returned `[]`; the SQL one passed the value straight to `.limit()`,
    so `limit=0` and `limit=-1` reached Postgres as written. `RefineMapping`
    refuses a limit below 1, so nothing triggered it — which is exactly how a
    contract gap waits for its next caller.
    """
    async with uow:
        file_id = await _file_upload_id(uow)
        proposal_id = await uow.mapping_proposals.save(_proposal(), file_upload_id=file_id)
        for index in range(3):
            await uow.mapping_proposals.add_message(
                proposal_id, role="user", content=f"turn-{index}"
            )
        await uow.commit()

    async with uow:
        zero = await uow.mapping_proposals.list_messages(proposal_id, limit=0)
        negative = await uow.mapping_proposals.list_messages(proposal_id, limit=-1)

    assert zero == []
    assert negative == []


async def test_messages_of_one_proposal_do_not_leak_into_another(uow: Any) -> None:
    async with uow:
        file_id = await _file_upload_id(uow)
        first = await uow.mapping_proposals.save(_proposal(), file_upload_id=file_id)
        second = await uow.mapping_proposals.save(_proposal(), file_upload_id=file_id)
        await uow.mapping_proposals.add_message(first, role="user", content="pour la première")
        await uow.mapping_proposals.add_message(second, role="user", content="pour la seconde")
        await uow.commit()

    async with uow:
        for_first = await uow.mapping_proposals.list_messages(first, limit=10)
        for_second = await uow.mapping_proposals.list_messages(second, limit=10)

    assert [m["content"] for m in for_first] == ["pour la première"]
    assert [m["content"] for m in for_second] == ["pour la seconde"]
    assert [m["turn_index"] for m in for_second] == [0], "turn_index is per proposal"
