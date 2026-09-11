"""SQLAlchemy Core table definitions.

Single source of truth for the physical schema, transcribed from
``docs/architecture/DATA_MODEL.md``. Nothing here is imported by ``domain/``
or ``application/`` — ``import-linter`` enforces that.

Two rules govern this module:

1. **A measure column is never NOT NULL and never carries a server default.**
   ``input_tokens``, ``duration_ms``, ``started_at`` and their kin are nullable
   with no default, because ``NULL`` means "the source did not provide it" and
   ``0`` means "the source provided zero". Collapsing the two is the single
   failure this project is most concerned with (ADR-009).

2. **The natural keys are the idempotence contract.** ``UNIQUE (data_source_id,
   external_id)`` on ``session`` and ``UNIQUE (session_id, sequence_index)`` on
   the call tables are what make re-importing a file a no-op instead of a
   duplication. They are load-bearing, not hygiene.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

# Naming convention so Alembic can autogenerate stable, diffable names for
# constraints instead of relying on whatever Postgres happens to invent.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _pk() -> Column[int]:
    """BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY."""
    return Column("id", BigInteger, Identity(always=True), primary_key=True)


def _tz(name: str) -> Column[datetime]:
    """A nullable timestamptz column, with no server default.

    Used for every temporal measure: absence of a timestamp is information,
    so these must never be filled in with now() or the epoch.
    """
    return Column(name, DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Provenance — where every row came from and what happened on the way in
# ---------------------------------------------------------------------------

data_source = Table(
    "data_source",
    metadata,
    _pk(),
    Column("slug", Text, nullable=False, unique=True),
    Column("name", Text, nullable=False),
    Column("description", Text),
    Column("url", Text),
    Column("license", Text),
    Column("dataset_version", Text),
    Column("retrieved_at", Date),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    comment="One identified external dataset, with its version and retrieval date.",
)

file_upload = Table(
    "file_upload",
    metadata,
    _pk(),
    Column("original_name", Text, nullable=False),
    Column("storage_path", Text, nullable=False),
    Column("format", Text, nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    # SHA-256 of the content: the first of the three idempotence barriers.
    Column("content_hash", CHAR(64), nullable=False, unique=True),
    Column("uploaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("format IN ('jsonl','csv','parquet')", name="format"),
    comment="One physically uploaded file, identified by its SHA-256.",
)

mapping = Table(
    "mapping",
    metadata,
    _pk(),
    Column("data_source_id", BigInteger, ForeignKey("data_source.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("source_format", Text, nullable=False),
    # The mapping document itself (MAPPING_CONTRACT.md §2).
    Column("document", JSONB, nullable=False),
    Column("status", Text, nullable=False, server_default="draft"),
    Column("description", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    _tz("updated_at"),
    CheckConstraint("source_format IN ('jsonl','csv','parquet')", name="source_format"),
    CheckConstraint(
        "status IN ('draft','validated','active','superseded','rejected','archived')",
        name="status",
    ),
    CheckConstraint("version >= 1", name="version_positive"),
    # Versioning: editing an active mapping creates version N+1 rather than
    # mutating it, so a past import stays explainable (MAPPING_CONTRACT.md §6).
    UniqueConstraint("data_source_id", "name", "version", name="uq_mapping_name_version"),
    comment="One version of a reusable import configuration.",
)

import_run = Table(
    "import_run",
    metadata,
    _pk(),
    Column("data_source_id", BigInteger, ForeignKey("data_source.id"), nullable=False),
    Column("file_upload_id", BigInteger, ForeignKey("file_upload.id"), nullable=False),
    Column("mapping_id", BigInteger, ForeignKey("mapping.id"), nullable=False),
    Column("status", Text, nullable=False),
    # Frozen historical summary. Recomputing it after a raw_record purge would
    # give a wrong answer, which is why it is stored (DATA_MODEL.md §5).
    Column("records_read", Integer, nullable=False, server_default="0"),
    Column("records_imported", Integer, nullable=False, server_default="0"),
    Column("records_duplicate", Integer, nullable=False, server_default="0"),
    Column("records_rejected", Integer, nullable=False, server_default="0"),
    Column("fields_missing", JSONB),
    Column("error_summary", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    _tz("started_at"),
    _tz("finished_at"),
    # Job-queue columns, consumed by FOR UPDATE SKIP LOCKED (issue #55).
    _tz("locked_at"),
    Column("locked_by", Text),
    Column("attempts", SmallInteger, nullable=False, server_default="0"),
    CheckConstraint(
        "status IN ('pending','running','succeeded','partial','failed','cancelled')",
        name="status",
    ),
    comment="One import execution: one file x one mapping x one instant.",
)

# Partial index: the queue only ever scans pending rows, so the index only
# needs to cover them.
Index(
    "ix_import_run_pending",
    import_run.c.status,
    import_run.c.created_at,
    postgresql_where=import_run.c.status == "pending",
)

raw_record = Table(
    "raw_record",
    metadata,
    _pk(),
    Column(
        "import_run_id",
        BigInteger,
        ForeignKey("import_run.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("line_number", Integer, nullable=False),
    # The source record, byte-for-byte as it arrived. Deliberately
    # un-normalised: keeping the raw payload is a requirement (ADR-008).
    Column("payload", JSONB, nullable=False),
    Column("content_hash", CHAR(64), nullable=False),
    UniqueConstraint("import_run_id", "line_number", name="uq_raw_record_run_line"),
    comment="One source record exactly as it was read, before any transformation.",
)

Index("ix_raw_record_content_hash", raw_record.c.content_hash)

import_issue = Table(
    "import_issue",
    metadata,
    _pk(),
    Column(
        "import_run_id",
        BigInteger,
        ForeignKey("import_run.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("raw_record_id", BigInteger, ForeignKey("raw_record.id", ondelete="CASCADE")),
    Column("severity", Text, nullable=False),
    Column("code", Text, nullable=False),
    Column("field_path", Text),
    Column("message", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("severity IN ('rejected','duplicate','warning')", name="severity"),
    comment="One problem on one raw_record: rejection, duplicate or warning.",
)

Index("ix_import_issue_run_severity", import_issue.c.import_run_id, import_issue.c.severity)


# ---------------------------------------------------------------------------
# Reference tables — the 3NF justification
#
# Without these, the fact tables would carry transitive dependencies:
# model_call.model_name -> provider_name, session.agent_name -> agent_version,
# tool_call.tool_name -> tool_category. Each one is extracted here.
# ---------------------------------------------------------------------------

provider = Table(
    "provider",
    metadata,
    _pk(),
    Column("name", Text, nullable=False, unique=True),
    comment="One model provider: anthropic, openai, unknown.",
)

model = Table(
    "model",
    metadata,
    _pk(),
    Column("provider_id", BigInteger, ForeignKey("provider.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("family", Text),
    UniqueConstraint("provider_id", "name", name="uq_model_provider_name"),
    comment="One model identified at one provider.",
)

agent = Table(
    "agent",
    metadata,
    _pk(),
    Column("name", Text, nullable=False),
    # NULL = the source gave no version. No mapping provides one today.
    Column("version", Text),
    # NULLS NOT DISTINCT: with the default, ('claude-code', NULL) never
    # conflicts with itself, the referential upsert never matches, and every
    # import creates the same agent again (issue #137, migration 0004).
    UniqueConstraint(
        "name",
        "version",
        name="uq_agent_name_version",
        postgresql_nulls_not_distinct=True,
    ),
    comment="One observed coding agent: claude-code, codex.",
)

tool = Table(
    "tool",
    metadata,
    _pk(),
    Column("name", Text, nullable=False, unique=True),
    Column("category", Text),
    comment="One invocable tool, by canonical name: Read, Bash, Edit.",
)

repository = Table(
    "repository",
    metadata,
    _pk(),
    Column("host", Text, nullable=False, server_default="github.com"),
    Column("owner", Text, nullable=False),
    Column("name", Text, nullable=False),
    UniqueConstraint("host", "owner", "name", name="uq_repository_host_owner_name"),
    comment="One code repository providing context for a session.",
)


# ---------------------------------------------------------------------------
# Facts — the three levels required by the brief
# ---------------------------------------------------------------------------

session = Table(
    "session",
    metadata,
    _pk(),
    Column("data_source_id", BigInteger, ForeignKey("data_source.id"), nullable=False),
    Column("import_run_id", BigInteger, ForeignKey("import_run.id"), nullable=False),
    Column("raw_record_id", BigInteger, ForeignKey("raw_record.id"), nullable=False),
    Column("external_id", Text, nullable=False),
    Column("agent_id", BigInteger, ForeignKey("agent.id")),
    Column("repository_id", BigInteger, ForeignKey("repository.id")),
    # NULL = the source gave no timestamp. Not "the epoch", not "zero".
    _tz("started_at"),
    _tz("ended_at"),
    # Kept even though it looks derivable: some sources report a duration
    # without reporting bounds, so it carries information (DATA_MODEL.md §5).
    Column("duration_ms", BigInteger),
    Column("outcome", Text),
    CheckConstraint(
        "outcome IN ('completed','error','aborted','unknown')",
        name="outcome",
    ),
    # NATURAL KEY: this is what makes re-import idempotent.
    UniqueConstraint("data_source_id", "external_id", name="uq_session_source_external"),
    comment="One agent working session, from start to finish.",
)

Index("ix_session_started_at", session.c.started_at)
Index("ix_session_data_source_agent", session.c.data_source_id, session.c.agent_id)

model_call = Table(
    "model_call",
    metadata,
    _pk(),
    Column("session_id", BigInteger, ForeignKey("session.id", ondelete="CASCADE"), nullable=False),
    Column("raw_record_id", BigInteger, ForeignKey("raw_record.id"), nullable=False),
    Column("model_id", BigInteger, ForeignKey("model.id")),
    Column("sequence_index", Integer, nullable=False),
    Column("external_id", Text),
    _tz("started_at"),
    Column("duration_ms", BigInteger),
    # Every token column is nullable with no default: NULL = not supplied.
    # A source without cache metrics must stay distinguishable from a source
    # that genuinely read zero cached tokens.
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("cache_read_tokens", Integer),
    Column("cache_creation_tokens", Integer),
    Column("reasoning_tokens", Integer),
    Column("stop_reason", Text),
    Column("status", Text, nullable=False, server_default="unknown"),
    Column("error_code", Text),
    CheckConstraint("status IN ('ok','error','unknown')", name="status"),
    UniqueConstraint("session_id", "sequence_index", name="uq_model_call_session_sequence"),
    comment="One model inference call within a session.",
)

Index("ix_model_call_session_id", model_call.c.session_id)
Index("ix_model_call_model_id", model_call.c.model_id)

tool_call = Table(
    "tool_call",
    metadata,
    _pk(),
    Column("session_id", BigInteger, ForeignKey("session.id", ondelete="CASCADE"), nullable=False),
    Column("model_call_id", BigInteger, ForeignKey("model_call.id", ondelete="SET NULL")),
    Column("raw_record_id", BigInteger, ForeignKey("raw_record.id"), nullable=False),
    Column("tool_id", BigInteger, ForeignKey("tool.id"), nullable=False),
    Column("sequence_index", Integer, nullable=False),
    Column("external_id", Text),
    _tz("started_at"),
    Column("duration_ms", BigInteger),
    Column("status", Text, nullable=False, server_default="unknown"),
    Column("error_message", Text),
    # Polymorphic by nature: modelling tool arguments relationally would mean
    # one table per tool. Display only, never aggregated (DATA_MODEL.md §5).
    Column("arguments", JSONB),
    Column("result_size", Integer),
    CheckConstraint("status IN ('ok','error','unknown')", name="status"),
    UniqueConstraint("session_id", "sequence_index", name="uq_tool_call_session_sequence"),
    comment="One tool invocation within a session.",
)

Index("ix_tool_call_session_id", tool_call.c.session_id)
Index("ix_tool_call_tool_id", tool_call.c.tool_id)
Index("ix_tool_call_model_call_id", tool_call.c.model_call_id)


# ---------------------------------------------------------------------------
# AI mapping proposals — traceability of what the model suggested
# ---------------------------------------------------------------------------

mapping_proposal = Table(
    "mapping_proposal",
    metadata,
    _pk(),
    Column("data_source_id", BigInteger, ForeignKey("data_source.id")),
    Column("file_upload_id", BigInteger, ForeignKey("file_upload.id"), nullable=False),
    # Set once the proposal has been saved as a real mapping.
    Column("mapping_id", BigInteger, ForeignKey("mapping.id")),
    Column("document", JSONB, nullable=False),
    Column("validation", JSONB),
    Column("rationale", JSONB),
    # Both are mandatory in the contract: an adapter that returns neither is
    # considered incomplete (MAPPING_CONTRACT.md §5).
    Column("ambiguities", JSONB),
    Column("unmapped_fields", JSONB),
    # The descriptor is kept here, and deliberately NOT in `mapping`, so a
    # saved mapping stays portable across providers.
    Column("analyzer_provider", Text, nullable=False),
    Column("analyzer_model", Text, nullable=False),
    Column("prompt_version", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    comment="One mapping proposed by an AI model for one file.",
)

Index("ix_mapping_proposal_file_upload_id", mapping_proposal.c.file_upload_id)

mapping_proposal_message = Table(
    "mapping_proposal_message",
    metadata,
    _pk(),
    Column(
        "mapping_proposal_id",
        BigInteger,
        ForeignKey("mapping_proposal.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("turn_index", Integer, nullable=False),
    Column("role", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("role IN ('user','assistant')", name="role"),
    UniqueConstraint("mapping_proposal_id", "turn_index", name="uq_proposal_message_proposal_turn"),
    comment="One conversation turn between the user and the import agent.",
)


# ---------------------------------------------------------------------------
# User auth — orthogonal to the rest of the schema: no other table references
# `users` or `user_session`. This is per-person login, distinct from the
# app-wide `X-API-Key` the front presents on every request.
#
# Table named "users" (plural), unlike every other table in this schema — the
# singular "user" is a reserved word in the SQL standard (a synonym for
# CURRENT_USER), so a bare, unquoted `user` breaks the moment anything issues
# raw SQL against it (as tests/integration/conftest.py's TRUNCATE did during
# development). Not worth carrying that landmine for naming-convention purity.
# ---------------------------------------------------------------------------

user = Table(
    "users",
    metadata,
    _pk(),
    Column("email", Text, nullable=False, unique=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    comment="One person able to authenticate against the API.",
)

user_session = Table(
    "user_session",
    metadata,
    _pk(),
    Column("token", Text, nullable=False, unique=True),
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # NULL would mean "never expires" — every session created by LoginUser
    # sets this, but the column stays nullable rather than NOT NULL so a
    # future non-expiring token type isn't a schema change.
    _tz("expires_at"),
    comment="One active login, identified by its opaque bearer token.",
)

Index("ix_user_session_user_id", user_session.c.user_id)


ALL_TABLES = (
    data_source,
    file_upload,
    mapping,
    import_run,
    raw_record,
    import_issue,
    provider,
    model,
    agent,
    tool,
    repository,
    session,
    model_call,
    tool_call,
    mapping_proposal,
    mapping_proposal_message,
    user,
    user_session,
)

#: Measure columns that must never become NOT NULL or gain a default.
#: Asserted by ``tests/integration/test_schema.py`` so the rule survives
#: future migrations rather than living only in review discipline.
MEASURE_COLUMNS: dict[str, tuple[str, ...]] = {
    "session": ("started_at", "ended_at", "duration_ms"),
    "model_call": (
        "started_at",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
        "reasoning_tokens",
    ),
    "tool_call": ("started_at", "duration_ms", "result_size"),
}
