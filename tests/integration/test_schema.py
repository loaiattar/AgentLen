"""Schema behaviour: idempotence keys, and absence never becoming zero."""

from __future__ import annotations

import pytest
from sqlalchemy import Connection, insert, select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from agentlen.infrastructure.persistence import tables as t
from tests.integration.conftest import requires_postgres

pytestmark = requires_postgres

#: Both sources contribute one session each in the shared-identifier test.
EXPECTED_SESSIONS = 2


def _provenance(conn: Connection) -> dict[str, int]:
    """Insert the minimum chain a fact row needs: source -> file -> mapping -> run -> record."""
    source_id = conn.execute(
        insert(t.data_source).values(slug="tracelab", name="TraceLab").returning(t.data_source.c.id)
    ).scalar_one()
    file_id = conn.execute(
        insert(t.file_upload)
        .values(
            original_name="sample.jsonl",
            storage_path="/srv/agentlen/uploads/sample.jsonl",
            format="jsonl",
            size_bytes=1024,
            content_hash="a" * 64,
        )
        .returning(t.file_upload.c.id)
    ).scalar_one()
    mapping_id = conn.execute(
        insert(t.mapping)
        .values(
            data_source_id=source_id,
            name="tracelab-jsonl",
            version=1,
            source_format="jsonl",
            document={"mapping_version": "1.0"},
            status="active",
        )
        .returning(t.mapping.c.id)
    ).scalar_one()
    run_id = conn.execute(
        insert(t.import_run)
        .values(
            data_source_id=source_id,
            file_upload_id=file_id,
            mapping_id=mapping_id,
            status="running",
        )
        .returning(t.import_run.c.id)
    ).scalar_one()
    record_id = conn.execute(
        insert(t.raw_record)
        .values(
            import_run_id=run_id,
            line_number=1,
            payload={"session_id": "a3f2"},
            content_hash="b" * 64,
        )
        .returning(t.raw_record.c.id)
    ).scalar_one()
    return {
        "data_source_id": source_id,
        "file_upload_id": file_id,
        "mapping_id": mapping_id,
        "import_run_id": run_id,
        "raw_record_id": record_id,
    }


# ---------------------------------------------------------------------------
# Idempotence: the natural keys must actually be enforced by the database
# ---------------------------------------------------------------------------


def test_same_external_id_twice_in_one_source_is_rejected(clean_db: Connection) -> None:
    """UNIQUE (data_source_id, external_id) is what makes re-import a no-op."""
    p = _provenance(clean_db)
    values = {
        "data_source_id": p["data_source_id"],
        "import_run_id": p["import_run_id"],
        "raw_record_id": p["raw_record_id"],
        "external_id": "session-a3f2",
    }
    clean_db.execute(insert(t.session).values(**values))

    with pytest.raises(IntegrityError) as exc:
        clean_db.execute(insert(t.session).values(**values))
    assert "uq_session_source_external" in str(exc.value)


def test_same_external_id_in_two_sources_is_allowed(clean_db: Connection) -> None:
    """The key is (source, external_id), not external_id alone.

    Two datasets are perfectly entitled to use the same session identifier;
    keying on external_id alone would make the second source unimportable.
    """
    p = _provenance(clean_db)
    other_source = clean_db.execute(
        insert(t.data_source).values(slug="swe-chat", name="SWE-chat").returning(t.data_source.c.id)
    ).scalar_one()

    clean_db.execute(
        insert(t.session).values(
            data_source_id=p["data_source_id"],
            import_run_id=p["import_run_id"],
            raw_record_id=p["raw_record_id"],
            external_id="shared-id",
        )
    )
    clean_db.execute(
        insert(t.session).values(
            data_source_id=other_source,
            import_run_id=p["import_run_id"],
            raw_record_id=p["raw_record_id"],
            external_id="shared-id",
        )
    )
    assert len(clean_db.execute(select(t.session)).all()) == EXPECTED_SESSIONS


def test_duplicate_sequence_index_within_a_session_is_rejected(clean_db: Connection) -> None:
    p = _provenance(clean_db)
    session_id = clean_db.execute(
        insert(t.session)
        .values(
            data_source_id=p["data_source_id"],
            import_run_id=p["import_run_id"],
            raw_record_id=p["raw_record_id"],
            external_id="s1",
        )
        .returning(t.session.c.id)
    ).scalar_one()

    call = {
        "session_id": session_id,
        "raw_record_id": p["raw_record_id"],
        "sequence_index": 0,
        "status": "ok",
    }
    clean_db.execute(insert(t.model_call).values(**call))
    with pytest.raises(IntegrityError) as exc:
        clean_db.execute(insert(t.model_call).values(**call))
    assert "uq_model_call_session_sequence" in str(exc.value)


def test_same_file_content_cannot_be_stored_twice(clean_db: Connection) -> None:
    """file_upload.content_hash is the first idempotence barrier."""
    row = {
        "original_name": "a.jsonl",
        "storage_path": "/srv/agentlen/uploads/a.jsonl",
        "format": "jsonl",
        "size_bytes": 10,
        "content_hash": "c" * 64,
    }
    clean_db.execute(insert(t.file_upload).values(**row))
    with pytest.raises(IntegrityError):
        clean_db.execute(insert(t.file_upload).values(**{**row, "original_name": "b.jsonl"}))


# ---------------------------------------------------------------------------
# Absence is not zero (ADR-009) — the rule this project is built around
# ---------------------------------------------------------------------------


def test_omitted_token_counts_are_stored_as_null(clean_db: Connection) -> None:
    """A model_call inserted without token data must read back NULL, not 0.

    If a default ever creeps onto these columns, a source that reports no
    cache metrics becomes indistinguishable from one that read zero cached
    tokens, and every cache metric silently becomes wrong.
    """
    p = _provenance(clean_db)
    session_id = clean_db.execute(
        insert(t.session)
        .values(
            data_source_id=p["data_source_id"],
            import_run_id=p["import_run_id"],
            raw_record_id=p["raw_record_id"],
            external_id="s1",
        )
        .returning(t.session.c.id)
    ).scalar_one()

    clean_db.execute(
        insert(t.model_call).values(
            session_id=session_id,
            raw_record_id=p["raw_record_id"],
            sequence_index=0,
            status="unknown",
        )
    )
    row = clean_db.execute(select(t.model_call)).mappings().one()

    for column in (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
        "reasoning_tokens",
        "duration_ms",
        "started_at",
    ):
        assert row[column] is None, f"{column} came back as {row[column]!r}, expected None"


def test_sum_over_missing_values_is_null_not_zero(clean_db: Connection) -> None:
    """SUM of no rows is NULL in SQL — the read models depend on this.

    Postgres returning NULL here (rather than 0) is what lets the dashboard
    report "unavailable" instead of inventing a zero.
    """
    total = clean_db.execute(select(text("SUM(input_tokens)")).select_from(t.model_call)).scalar()
    assert total is None


def test_no_measure_column_has_a_default_or_not_null(clean_db: Connection) -> None:
    """Structural guard over every measure column in the schema.

    Cheaper than trusting review to catch a `server_default="0"` slipped into
    a future migration.
    """
    rows = clean_db.execute(
        text(
            "SELECT table_name, column_name, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_schema = 'public'"
        )
    ).mappings()
    by_table: dict[tuple[str, str], dict[str, object]] = {
        (r["table_name"], r["column_name"]): dict(r) for r in rows
    }

    for table_name, columns in t.MEASURE_COLUMNS.items():
        for column in columns:
            info = by_table[(table_name, column)]
            assert info["is_nullable"] == "YES", f"{table_name}.{column} is NOT NULL"
            assert info["column_default"] is None, (
                f"{table_name}.{column} has default {info['column_default']!r} — "
                "a missing measure must stay NULL"
            )


# ---------------------------------------------------------------------------
# Constraints that encode business rules
# ---------------------------------------------------------------------------


def test_invalid_status_is_rejected_by_check_constraint(clean_db: Connection) -> None:
    p = _provenance(clean_db)
    with pytest.raises(IntegrityError) as exc:
        clean_db.execute(
            insert(t.import_run).values(
                data_source_id=p["data_source_id"],
                file_upload_id=p["file_upload_id"],
                mapping_id=p["mapping_id"],
                status="almost_done",
            )
        )
    assert "ck_import_run_status" in str(exc.value)


def test_deleting_an_import_run_cascades_to_its_raw_records(clean_db: Connection) -> None:
    """Provenance rows follow their run; fact rows do not silently vanish."""
    p = _provenance(clean_db)
    clean_db.execute(t.import_run.delete().where(t.import_run.c.id == p["import_run_id"]))
    assert clean_db.execute(select(t.raw_record)).first() is None


def test_mapping_versions_coexist(clean_db: Connection) -> None:
    """Editing a mapping creates version N+1; the old version stays queryable
    so a past import_run remains explainable."""
    p = _provenance(clean_db)
    clean_db.execute(
        insert(t.mapping).values(
            data_source_id=p["data_source_id"],
            name="tracelab-jsonl",
            version=2,
            source_format="jsonl",
            document={"mapping_version": "1.0"},
            status="active",
        )
    )
    clean_db.execute(
        t.mapping.update().where(t.mapping.c.id == p["mapping_id"]).values(status="superseded")
    )
    versions = clean_db.execute(
        select(t.mapping.c.version, t.mapping.c.status).order_by(t.mapping.c.version)
    ).all()
    assert versions == [(1, "superseded"), (2, "active")]


def test_identity_column_cannot_be_overridden(clean_db: Connection) -> None:
    """GENERATED ALWAYS means the application never picks an id.

    ALWAYS rather than BY DEFAULT so an import cannot smuggle in its own
    primary keys; Postgres reports this as GeneratedAlways, not a constraint
    violation.
    """
    with pytest.raises(ProgrammingError) as exc:
        clean_db.execute(insert(t.data_source).values(id=42, slug="forced", name="Forced"))
    assert "GENERATED ALWAYS" in str(exc.value).upper()
