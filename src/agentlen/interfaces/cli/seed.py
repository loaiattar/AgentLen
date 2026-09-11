"""`python -m agentlen.interfaces.cli seed` — the reproducibility seed (#60).

Prepares exactly what a first import needs and nothing else: the `TraceLab`
data source, a starter mapping for its JSONL shape, and one import of
`data/samples/tracelab_example_session.jsonl`. Every step reuses an existing
mechanism —`UploadFile`'s storage port, `RunImport`, the Postgres job queue,
`ImportWorker` — this module only wires them together and authors the mapping
*document* MAPPING_CONTRACT.md describes (data, not a new pipeline).

Idempotent by construction, the same way the rest of the import pipeline is:
`data_source` and `file_upload` dedupe on their unique columns, the mapping is
looked up before being (re)created, and an import already `succeeded`/
`partial` for this exact file+mapping is left alone rather than re-run.
Re-running `make seed` is safe.

Runs the import itself through the real queue rather than calling `RunImport`
directly, because the `worker` container from `docker compose up` is polling
the same queue concurrently — `FOR UPDATE SKIP LOCKED` means whichever of the
two claims the job first is the one that runs it; this module just waits for
whichever that was to finish.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.application.use_cases.run_import import RunImport
from agentlen.domain.model.mapping import EntityMapping, FieldRule, Mapping
from agentlen.infrastructure.files.local_storage import LocalFileStorage
from agentlen.infrastructure.files.polars_record_reader import PolarsRecordReader
from agentlen.infrastructure.jobs.postgres_queue import PostgresJobQueue
from agentlen.infrastructure.jobs.worker import ImportWorker
from agentlen.infrastructure.persistence import tables as t
from agentlen.infrastructure.persistence.engine import create_engine
from agentlen.infrastructure.persistence.repositories.mapping_codec import mapping_to_document
from agentlen.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

logger = logging.getLogger("agentlen.seed")

DATA_SOURCE_SLUG = "tracelab"
DATA_SOURCE_NAME = "TraceLab"
MAPPING_NAME = "tracelab-jsonl"

#: Repository root, from this file: src/agentlen/interfaces/cli/ -> up 4.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_FILE = _PROJECT_ROOT / "data" / "samples" / "tracelab_example_session.jsonl"
#: Anchored to the repo root (not the cwd): resolves to /app/storage/uploads
#: under the compose WORKDIR, and to <repo_root>/storage/uploads locally — the
#: same convention as the .gitignore'd `storage/` directory.
STORAGE_ROOT = _PROJECT_ROOT / "storage" / "uploads"

_TERMINAL_STATUSES = {"succeeded", "partial", "failed"}


def _tracelab_mapping() -> Mapping:
    """One `session` per line, one `model_call` per line (a "round"), and one
    `tool_call` per entry of its `tools` array — see
    data/samples/tracelab_example_session.jsonl and MAPPING_CONTRACT.md §2.

    `reasoning_output_tokens` is deliberately left unmapped: the domain's
    `TokenUsage`/`RecordNormalizer` do not carry a reasoning-tokens field
    through to `ModelCall` today, so mapping it would be silently dropped
    downstream — a pre-existing gap outside this issue's scope, not something
    to paper over here.
    """
    return Mapping(
        id=uuid4(),
        name=MAPPING_NAME,
        version=1,
        source_format="jsonl",
        entities=(
            EntityMapping(
                target="session",
                natural_key=("external_id",),
                fields=(
                    FieldRule(
                        target="external_id",
                        source="$.session_id",
                        required=True,
                        operators=({"op": "cast", "to": "string"},),
                    ),
                    FieldRule(target="agent_name", source="$.provider"),
                ),
            ),
            EntityMapping(
                target="model_call",
                natural_key=("sequence_index",),
                parent={"entity": "session", "via": "external_id"},
                fields=(
                    FieldRule(
                        target="sequence_index",
                        source="$.round_index",
                        required=True,
                        operators=({"op": "cast", "to": "integer"},),
                    ),
                    FieldRule(target="model_name", source="$.model"),
                    FieldRule(target="provider_name", source="$.provider"),
                    FieldRule(
                        target="input_tokens",
                        source="$.input_tokens_total",
                        operators=({"op": "cast", "to": "integer", "on_error": "null"},),
                    ),
                    FieldRule(
                        target="output_tokens",
                        source="$.output_tokens",
                        operators=({"op": "cast", "to": "integer", "on_error": "null"},),
                    ),
                    FieldRule(
                        target="cache_read_tokens",
                        source="$.claude_cache_read_input_tokens",
                        operators=({"op": "cast", "to": "integer", "on_error": "null"},),
                    ),
                    FieldRule(
                        target="cache_creation_tokens",
                        source="$.claude_cache_creation_input_tokens",
                        operators=({"op": "cast", "to": "integer", "on_error": "null"},),
                    ),
                ),
            ),
            EntityMapping(
                target="tool_call",
                iterate="$.tools",
                parent={"entity": "session", "via": "external_id"},
                natural_key=("sequence_index",),
                # `sequence_index` is deliberately not mapped: `$.tool_index`
                # restarts at 0 on every round, so it is not unique within a
                # session and 14 of the sample's 19 calls overwrote each other
                # (#188). Unmapped, it is derived from the line and the position
                # in `tools` (MAPPING_CONTRACT.md §2.2).
                fields=(
                    FieldRule(target="tool_name", source="$.tool_name", required=True),
                    FieldRule(
                        target="status",
                        source="$.is_error",
                        operators=(
                            {
                                "op": "map_values",
                                "table": {"True": "error", "False": "ok"},
                                "on_unknown": "constant",
                                "constant": "unknown",
                            },
                        ),
                    ),
                    FieldRule(
                        target="duration_ms",
                        source="$.tool_wall_latency_ms",
                        operators=({"op": "cast", "to": "integer", "on_error": "null"},),
                    ),
                ),
            ),
        ),
    )


async def _file_chunks(path: Path) -> AsyncIterator[bytes]:
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            yield chunk


async def _ensure_data_source(engine: AsyncEngine) -> int:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        source_id = await uow.data_sources.create(slug=DATA_SOURCE_SLUG, name=DATA_SOURCE_NAME)
        await uow.commit()
    return source_id


async def _ensure_mapping(engine: AsyncEngine, *, data_source_id: int) -> int:
    """Insert the mapping if it is not already there.

    `MappingRepository` has no "get or create" of its own — `save()` always
    inserts a new version — so idempotency is handled here the same way
    `SqlAlchemyDataSourceRepository.create` handles it for sources: an
    `ON CONFLICT DO NOTHING` against `uq_mapping_name_version`, falling back to
    a plain lookup when it fires.
    """
    mapping = _tracelab_mapping()
    async with engine.begin() as conn:
        statement = (
            insert(t.mapping)
            .values(
                data_source_id=data_source_id,
                name=mapping.name,
                version=mapping.version,
                source_format=mapping.source_format,
                document=mapping_to_document(mapping),
                status="active",
            )
            .on_conflict_do_nothing(constraint="uq_mapping_name_version")
            .returning(t.mapping.c.id)
        )
        created = (await conn.execute(statement)).scalar_one_or_none()
        if created is not None:
            return int(created)

        existing = (
            await conn.execute(
                select(t.mapping.c.id).where(
                    t.mapping.c.data_source_id == data_source_id,
                    t.mapping.c.name == mapping.name,
                    t.mapping.c.version == mapping.version,
                )
            )
        ).scalar_one()
        return int(existing)


async def _ensure_file_upload(engine: AsyncEngine) -> int:
    if not SAMPLE_FILE.exists():
        raise FileNotFoundError(f"Sample file not found: {SAMPLE_FILE}")

    storage = LocalFileStorage(STORAGE_ROOT)
    async with SqlAlchemyUnitOfWork(engine) as uow:
        stored = await storage.store(_file_chunks(SAMPLE_FILE), original_name=SAMPLE_FILE.name)
        existing = await uow.file_uploads.get_by_hash(stored.content_hash)
        if existing is not None:
            await uow.commit()
            return existing.id
        record = await uow.file_uploads.create(
            original_name=SAMPLE_FILE.name,
            storage_path=stored.storage_path,
            format=stored.detected_format,
            size_bytes=stored.size_bytes,
            content_hash=stored.content_hash,
        )
        await uow.commit()
        return record.id


async def _existing_finished_run(
    engine: AsyncEngine, *, file_upload_id: int, mapping_id: int
) -> dict[str, Any] | None:
    async with SqlAlchemyUnitOfWork(engine) as uow:
        for run_id in await uow.file_uploads.import_run_ids(file_upload_id):
            run = await uow.import_runs.get(run_id)
            if (
                run
                and run["mapping_id"] == mapping_id
                and run["status"] in ("succeeded", "partial")
            ):
                return run
    return None


async def _run_and_wait(
    engine: AsyncEngine, run_id: int, *, timeout: float = 60.0, poll_interval: float = 0.5
) -> dict[str, Any]:
    """Let the real queue + worker pipeline process `run_id`.

    Tries to claim and run it in-process (`ImportWorker.run_once`); if the
    `worker` container from `docker compose up` wins the claim instead — the
    expected case once `make up` has been run — this just polls the row until
    it leaves `pending`/`running`.
    """
    queue = PostgresJobQueue(engine)
    worker = ImportWorker(
        queue,
        RunImport(SqlAlchemyUnitOfWork(engine), PolarsRecordReader()),
        worker_id="seed",
    )
    deadline = time.monotonic() + timeout
    while True:
        async with SqlAlchemyUnitOfWork(engine) as uow:
            run = await uow.import_runs.get(run_id)
        if run is None:
            raise RuntimeError(f"import_run {run_id} disappeared while waiting for it.")
        if run["status"] in _TERMINAL_STATUSES:
            return run
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"import_run {run_id} still '{run['status']}' after {timeout:.0f}s — "
                "is the `worker` service running (`make up` / `docker compose up`)?"
            )
        await worker.run_once()  # no-op if another worker already claimed the job
        await asyncio.sleep(poll_interval)


async def run() -> None:
    engine = create_engine()
    try:
        source_id = await _ensure_data_source(engine)
        logger.info("Source '%s' prête (id=%s).", DATA_SOURCE_SLUG, source_id)

        mapping_id = await _ensure_mapping(engine, data_source_id=source_id)
        logger.info("Mapping '%s' v1 prêt (id=%s).", MAPPING_NAME, mapping_id)

        file_upload_id = await _ensure_file_upload(engine)
        logger.info("Fichier échantillon stocké (file_upload_id=%s).", file_upload_id)

        finished = await _existing_finished_run(
            engine, file_upload_id=file_upload_id, mapping_id=mapping_id
        )
        if finished is not None:
            run_row = finished
            logger.info(
                "Import déjà réalisé (import_run_id=%s, status=%s) — rien à refaire.",
                run_row["id"],
                run_row["status"],
            )
        else:
            async with SqlAlchemyUnitOfWork(engine) as uow:
                run_id = await uow.import_runs.create(
                    data_source_id=source_id,
                    file_upload_id=file_upload_id,
                    mapping_id=mapping_id,
                )
                await uow.commit()
            logger.info("Import lancé (import_run_id=%s).", run_id)
            run_row = await _run_and_wait(engine, run_id)

        logger.info(
            "Seed terminé : status=%s, lus=%s, importés=%s, doublons=%s, rejetés=%s.",
            run_row["status"],
            run_row["records_read"],
            run_row["records_imported"],
            run_row["records_duplicate"],
            run_row["records_rejected"],
        )
        if run_row["status"] == "failed":
            raise RuntimeError(f"Import {run_row['id']} a échoué : {run_row.get('error_summary')}")
    finally:
        await engine.dispose()
