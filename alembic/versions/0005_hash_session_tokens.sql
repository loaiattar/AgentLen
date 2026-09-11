BEGIN;

-- Running upgrade 0004 -> 0005

DELETE FROM user_session;

ALTER TABLE user_session DROP CONSTRAINT uq_user_session_token;

ALTER TABLE user_session RENAME token TO token_hash;

ALTER TABLE user_session ADD CONSTRAINT uq_user_session_token_hash UNIQUE (token_hash);

ALTER TABLE user_session ADD CONSTRAINT ck_user_session_token_hash_is_sha256 CHECK (token_hash ~ '^[0-9a-f]{64}$');

CREATE INDEX ix_user_session_expires_at ON user_session (expires_at);

COMMENT ON TABLE user_session IS 'One active login, identified by the SHA-256 of its bearer token.';

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

COMMIT;

