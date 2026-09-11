"""Rows on their way into the database.

A domain entity does not carry everything its table needs. `Session` knows its
`external_id` and an agent *name*; the table needs an `import_run_id`, a
`raw_record_id` and an `agent_id`. That gap is deliberate — the domain models
the business fact, not the storage layout (3NF referentials, provenance).

These DTOs are the bridge: entity plus the context the import run resolved for
it. Keeping them here rather than widening the entities is what stops the
storage layout from leaking into the domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID

from agentlen.domain.model.import_run import ImportIssue
from agentlen.domain.model.model_call import ModelCall
from agentlen.domain.model.session import Session
from agentlen.domain.model.tool_call import ToolCall


@dataclass(frozen=True)
class SessionRow:
    entity: Session
    import_run_id: int
    raw_record_id: int
    agent_id: int | None = None
    repository_id: int | None = None


@dataclass(frozen=True)
class ModelCallRow:
    entity: ModelCall
    raw_record_id: int
    model_id: int | None = None


@dataclass(frozen=True)
class ToolCallRow:
    entity: ToolCall
    raw_record_id: int
    tool_id: int


@dataclass(frozen=True)
class InsertOutcome:
    """What an insertion actually did.

    `assigned` maps each entity this call wrote to the id the database gave it —
    one row per natural key, however many times the batch repeats that key.

    `existing` maps every other entity to the id of the row that already holds
    its natural key: written earlier in the same batch, earlier in the same
    import run, or by a previous import. Children need that id to attach to a
    parent they did not create, which is why `ids` merges the two.

    `duplicates` lists the entities the report counts as already imported. It is
    a subset of `existing` and not an error: re-importing a file is a normal act,
    counted apart from rejections (DATA_MODEL.md §6). A session that several
    lines of one import describe is the same session, not a duplicate.

    `unlinked` lists children that could not be written because their parent is
    unknown. They are neither imported nor duplicates: the caller must say so
    rather than let them disappear.
    """

    assigned: dict[UUID, int] = field(default_factory=dict)
    duplicates: tuple[UUID, ...] = ()
    existing: dict[UUID, int] = field(default_factory=dict)
    unlinked: tuple[UUID, ...] = ()

    @property
    def ids(self) -> dict[UUID, int]:
        """Every entity's database id, whether written by this call or already stored."""
        return {**self.existing, **self.assigned}

    @property
    def inserted_count(self) -> int:
        return len(self.assigned)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)


@dataclass(frozen=True)
class ImportIssueRecord:
    """A stored import issue and the source record it points at.

    `import_issue` has no line number of its own: `issue.line_number` is read
    back from the linked `raw_record`, and stays `None` when there is none (a
    run-level issue such as `ALREADY_IMPORTED`). `raw_record_id` is storage
    provenance, so it lives here rather than on the domain `ImportIssue`; it
    is what lets a client open `GET /records/{raw_record_id}`.
    """

    issue: ImportIssue
    raw_record_id: int | None = None


@dataclass(frozen=True)
class DataSourceRecord:
    """One external dataset (API.md §2: `GET /data-sources`)."""

    id: int
    slug: str
    name: str
    description: str | None = None
    url: str | None = None
    license: str | None = None
    dataset_version: str | None = None
    retrieved_at: date | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class FileUploadRecord:
    """A file already known to the system, recognised by its content hash."""

    id: int
    original_name: str
    storage_path: str
    format: str
    size_bytes: int
    content_hash: str


@dataclass(frozen=True)
class UserRecord:
    """One person able to authenticate.

    `password_hash` never leaves the application layer: the HTTP schemas
    (`interfaces/http/schemas/auth.py`) map this to `UserOut`, which does not
    carry the field at all — there is no serializer bug possible, only a
    missing attribute.
    """

    id: int
    email: str
    password_hash: str
    created_at: datetime | None = None


@dataclass(frozen=True)
class UserSessionRecord:
    """One active login, keyed by the SHA-256 of the bearer token a client
    presents after `/auth/login`. The token itself is never stored."""

    token_hash: str
    user_id: int
    created_at: datetime | None = None
    expires_at: datetime | None = None
