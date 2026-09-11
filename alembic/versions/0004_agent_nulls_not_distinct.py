"""Agent key — treat an unknown version as one value, not as many.

`agent` is unique on `(name, version)`, and `version` is nullable because no
source mapping provides it today. PostgreSQL's default is `NULLS DISTINCT`:
two `('claude-code', NULL)` rows do not conflict, so the referential upsert's
`ON CONFLICT (name, version)` never fired and every import run created a new
agent row for the same agent. The dashboard then split one agent into as many
agents as there were imports (issue #137).

`UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15+) makes the key mean what the
upsert assumes. The other referential keys are not affected: every column of
`provider`, `model`, `tool` and `repository` keys is `NOT NULL`.

The upgrade first merges the duplicates already stored, or adding the
constraint would fail: every `session.agent_id` is re-pointed at the oldest
row of its `(name, version)` group, then the other rows are deleted. `session`
is the only table referencing `agent` at this revision.

The downgrade restores the looser constraint. It cannot un-merge the rows, and
does not need to: the merged rows satisfy both constraints.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-11 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PARTITION BY groups NULLs together, which is exactly the equality the new
# constraint enforces.
REPOINT_SESSIONS = """
UPDATE session AS s
SET agent_id = grouped.survivor_id
FROM (
    SELECT id, min(id) OVER (PARTITION BY name, version) AS survivor_id
    FROM agent
) AS grouped
WHERE s.agent_id = grouped.id
  AND grouped.id <> grouped.survivor_id
"""

DELETE_DUPLICATES = """
DELETE FROM agent AS duplicate
USING agent AS survivor
WHERE duplicate.name = survivor.name
  AND duplicate.version IS NOT DISTINCT FROM survivor.version
  AND duplicate.id > survivor.id
"""


def upgrade() -> None:
    op.execute(REPOINT_SESSIONS)
    op.execute(DELETE_DUPLICATES)
    op.drop_constraint("uq_agent_name_version", "agent", type_="unique")
    op.create_unique_constraint(
        "uq_agent_name_version",
        "agent",
        ["name", "version"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_name_version", "agent", type_="unique")
    op.create_unique_constraint("uq_agent_name_version", "agent", ["name", "version"])
