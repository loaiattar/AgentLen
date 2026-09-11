"""Session tokens — store the SHA-256 of the token, never the token.

Until 0004, `user_session.token` held the bearer token itself: any read of the
table (a backup, a read-only role) gave working sessions for 30 days. The
column becomes `token_hash`, checked to be a SHA-256 hex digest so a plaintext
token cannot be written by mistake, plus an index on `expires_at` for the
purge of expired sessions (issue #151).

The upgrade deletes every existing session instead of hashing it in place.
Those tokens were stored in clear, so they may already be in a backup: logging
everyone out is the point, not a side effect. Users log in again.

The downgrade also deletes every session: a digest cannot be turned back into
the token the client holds.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-11 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM user_session")
    op.drop_constraint("uq_user_session_token", "user_session", type_="unique")
    op.alter_column("user_session", "token", new_column_name="token_hash")
    op.create_unique_constraint(op.f("uq_user_session_token_hash"), "user_session", ["token_hash"])
    op.create_check_constraint(
        op.f("ck_user_session_token_hash_is_sha256"),
        "user_session",
        "token_hash ~ '^[0-9a-f]{64}$'",
    )
    op.create_index("ix_user_session_expires_at", "user_session", ["expires_at"])
    op.create_table_comment(
        "user_session",
        "One active login, identified by the SHA-256 of its bearer token.",
        existing_comment="One active login, identified by its opaque bearer token.",
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_session")
    op.create_table_comment(
        "user_session",
        "One active login, identified by its opaque bearer token.",
        existing_comment="One active login, identified by the SHA-256 of its bearer token.",
    )
    op.drop_index("ix_user_session_expires_at", table_name="user_session")
    # op.f(): the name is final. Without it the `ck` naming convention of
    # tables.py is applied again and the name gets a second prefix.
    op.drop_constraint(op.f("ck_user_session_token_hash_is_sha256"), "user_session", type_="check")
    op.drop_constraint("uq_user_session_token_hash", "user_session", type_="unique")
    op.alter_column("user_session", "token_hash", new_column_name="token")
    op.create_unique_constraint("uq_user_session_token", "user_session", ["token"])
