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
from uuid import UUID

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

    `assigned` maps each entity's in-batch UUID to the id the database gave it,
    so children can be linked to the parent that was just written.

    `duplicates` lists entities the database already had, recognised by their
    natural key. They are not an error: re-importing a file is a normal act, and
    the import report counts them separately from rejections (DATA_MODEL.md §6).
    """

    assigned: dict[UUID, int] = field(default_factory=dict)
    duplicates: tuple[UUID, ...] = ()

    @property
    def inserted_count(self) -> int:
        return len(self.assigned)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)


@dataclass(frozen=True)
class FileUploadRecord:
    """A file already known to the system, recognised by its content hash."""

    id: int
    original_name: str
    storage_path: str
    format: str
    size_bytes: int
    content_hash: str
