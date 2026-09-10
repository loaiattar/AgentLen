BEGIN;

-- Running upgrade 0002 -> 0003

CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    email TEXT NOT NULL, 
    password_hash TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT uq_users_email UNIQUE (email)
);

COMMENT ON TABLE users IS 'One person able to authenticate against the API.';

CREATE TABLE user_session (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    token TEXT NOT NULL, 
    user_id BIGINT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_user_session PRIMARY KEY (id), 
    CONSTRAINT fk_user_session_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_session_token UNIQUE (token)
);

COMMENT ON TABLE user_session IS 'One active login, identified by its opaque bearer token.';

CREATE INDEX ix_user_session_user_id ON user_session (user_id);

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

COMMIT;

