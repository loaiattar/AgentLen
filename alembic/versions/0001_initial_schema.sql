BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE agent (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    name TEXT NOT NULL, 
    version TEXT, 
    CONSTRAINT pk_agent PRIMARY KEY (id), 
    CONSTRAINT uq_agent_name_version UNIQUE (name, version)
);

COMMENT ON TABLE agent IS 'One observed coding agent: claude-code, codex.';

CREATE TABLE data_source (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    slug TEXT NOT NULL, 
    name TEXT NOT NULL, 
    description TEXT, 
    url TEXT, 
    license TEXT, 
    dataset_version TEXT, 
    retrieved_at DATE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_data_source PRIMARY KEY (id), 
    CONSTRAINT uq_data_source_slug UNIQUE (slug)
);

COMMENT ON TABLE data_source IS 'One identified external dataset, with its version and retrieval date.';

CREATE TABLE file_upload (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    original_name TEXT NOT NULL, 
    storage_path TEXT NOT NULL, 
    format TEXT NOT NULL, 
    size_bytes BIGINT NOT NULL, 
    content_hash CHAR(64) NOT NULL, 
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_file_upload PRIMARY KEY (id), 
    CONSTRAINT ck_file_upload_format CHECK (format IN ('jsonl','csv','parquet')), 
    CONSTRAINT uq_file_upload_content_hash UNIQUE (content_hash)
);

COMMENT ON TABLE file_upload IS 'One physically uploaded file, identified by its SHA-256.';

CREATE TABLE provider (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    name TEXT NOT NULL, 
    CONSTRAINT pk_provider PRIMARY KEY (id), 
    CONSTRAINT uq_provider_name UNIQUE (name)
);

COMMENT ON TABLE provider IS 'One model provider: anthropic, openai, unknown.';

CREATE TABLE repository (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    host TEXT DEFAULT 'github.com' NOT NULL, 
    owner TEXT NOT NULL, 
    name TEXT NOT NULL, 
    CONSTRAINT pk_repository PRIMARY KEY (id), 
    CONSTRAINT uq_repository_host_owner_name UNIQUE (host, owner, name)
);

COMMENT ON TABLE repository IS 'One code repository providing context for a session.';

CREATE TABLE tool (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    name TEXT NOT NULL, 
    category TEXT, 
    CONSTRAINT pk_tool PRIMARY KEY (id), 
    CONSTRAINT uq_tool_name UNIQUE (name)
);

COMMENT ON TABLE tool IS 'One invocable tool, by canonical name: Read, Bash, Edit.';

CREATE TABLE mapping (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    data_source_id BIGINT NOT NULL, 
    name TEXT NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    source_format TEXT NOT NULL, 
    document JSONB NOT NULL, 
    status TEXT DEFAULT 'draft' NOT NULL, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_mapping PRIMARY KEY (id), 
    CONSTRAINT ck_mapping_source_format CHECK (source_format IN ('jsonl','csv','parquet')), 
    CONSTRAINT ck_mapping_status CHECK (status IN ('draft','validated','active','superseded','rejected','archived')), 
    CONSTRAINT ck_mapping_version_positive CHECK (version >= 1), 
    CONSTRAINT fk_mapping_data_source_id_data_source FOREIGN KEY(data_source_id) REFERENCES data_source (id), 
    CONSTRAINT uq_mapping_name_version UNIQUE (data_source_id, name, version)
);

COMMENT ON TABLE mapping IS 'One version of a reusable import configuration.';

CREATE TABLE model (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    provider_id BIGINT NOT NULL, 
    name TEXT NOT NULL, 
    family TEXT, 
    CONSTRAINT pk_model PRIMARY KEY (id), 
    CONSTRAINT fk_model_provider_id_provider FOREIGN KEY(provider_id) REFERENCES provider (id), 
    CONSTRAINT uq_model_provider_name UNIQUE (provider_id, name)
);

COMMENT ON TABLE model IS 'One model identified at one provider.';

CREATE TABLE import_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    data_source_id BIGINT NOT NULL, 
    file_upload_id BIGINT NOT NULL, 
    mapping_id BIGINT NOT NULL, 
    status TEXT NOT NULL, 
    records_read INTEGER DEFAULT '0' NOT NULL, 
    records_imported INTEGER DEFAULT '0' NOT NULL, 
    records_duplicate INTEGER DEFAULT '0' NOT NULL, 
    records_rejected INTEGER DEFAULT '0' NOT NULL, 
    fields_missing JSONB, 
    error_summary TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    locked_at TIMESTAMP WITH TIME ZONE, 
    locked_by TEXT, 
    attempts SMALLINT DEFAULT '0' NOT NULL, 
    CONSTRAINT pk_import_run PRIMARY KEY (id), 
    CONSTRAINT ck_import_run_status CHECK (status IN ('pending','running','succeeded','partial','failed','cancelled')), 
    CONSTRAINT fk_import_run_data_source_id_data_source FOREIGN KEY(data_source_id) REFERENCES data_source (id), 
    CONSTRAINT fk_import_run_file_upload_id_file_upload FOREIGN KEY(file_upload_id) REFERENCES file_upload (id), 
    CONSTRAINT fk_import_run_mapping_id_mapping FOREIGN KEY(mapping_id) REFERENCES mapping (id)
);

COMMENT ON TABLE import_run IS 'One import execution: one file x one mapping x one instant.';

CREATE INDEX ix_import_run_pending ON import_run (status, created_at) WHERE status = 'pending';

CREATE TABLE mapping_proposal (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    data_source_id BIGINT, 
    file_upload_id BIGINT NOT NULL, 
    mapping_id BIGINT, 
    document JSONB NOT NULL, 
    validation JSONB, 
    rationale JSONB, 
    ambiguities JSONB, 
    unmapped_fields JSONB, 
    analyzer_provider TEXT NOT NULL, 
    analyzer_model TEXT NOT NULL, 
    prompt_version TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_mapping_proposal PRIMARY KEY (id), 
    CONSTRAINT fk_mapping_proposal_data_source_id_data_source FOREIGN KEY(data_source_id) REFERENCES data_source (id), 
    CONSTRAINT fk_mapping_proposal_file_upload_id_file_upload FOREIGN KEY(file_upload_id) REFERENCES file_upload (id), 
    CONSTRAINT fk_mapping_proposal_mapping_id_mapping FOREIGN KEY(mapping_id) REFERENCES mapping (id)
);

COMMENT ON TABLE mapping_proposal IS 'One mapping proposed by an AI model for one file.';

CREATE INDEX ix_mapping_proposal_file_upload_id ON mapping_proposal (file_upload_id);

CREATE TABLE mapping_proposal_message (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    mapping_proposal_id BIGINT NOT NULL, 
    turn_index INTEGER NOT NULL, 
    role TEXT NOT NULL, 
    content TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_mapping_proposal_message PRIMARY KEY (id), 
    CONSTRAINT ck_mapping_proposal_message_role CHECK (role IN ('user','assistant')), 
    CONSTRAINT fk_mapping_proposal_message_mapping_proposal_id_mapping_c886 FOREIGN KEY(mapping_proposal_id) REFERENCES mapping_proposal (id) ON DELETE CASCADE, 
    CONSTRAINT uq_proposal_message_proposal_turn UNIQUE (mapping_proposal_id, turn_index)
);

COMMENT ON TABLE mapping_proposal_message IS 'One conversation turn between the user and the import agent.';

CREATE TABLE raw_record (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    import_run_id BIGINT NOT NULL, 
    line_number INTEGER NOT NULL, 
    payload JSONB NOT NULL, 
    content_hash CHAR(64) NOT NULL, 
    CONSTRAINT pk_raw_record PRIMARY KEY (id), 
    CONSTRAINT fk_raw_record_import_run_id_import_run FOREIGN KEY(import_run_id) REFERENCES import_run (id) ON DELETE CASCADE, 
    CONSTRAINT uq_raw_record_run_line UNIQUE (import_run_id, line_number)
);

COMMENT ON TABLE raw_record IS 'One source record exactly as it was read, before any transformation.';

CREATE INDEX ix_raw_record_content_hash ON raw_record (content_hash);

CREATE TABLE import_issue (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    import_run_id BIGINT NOT NULL, 
    raw_record_id BIGINT, 
    severity TEXT NOT NULL, 
    code TEXT NOT NULL, 
    field_path TEXT, 
    message TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_import_issue PRIMARY KEY (id), 
    CONSTRAINT ck_import_issue_severity CHECK (severity IN ('rejected','duplicate','warning')), 
    CONSTRAINT fk_import_issue_import_run_id_import_run FOREIGN KEY(import_run_id) REFERENCES import_run (id) ON DELETE CASCADE, 
    CONSTRAINT fk_import_issue_raw_record_id_raw_record FOREIGN KEY(raw_record_id) REFERENCES raw_record (id) ON DELETE CASCADE
);

COMMENT ON TABLE import_issue IS 'One problem on one raw_record: rejection, duplicate or warning.';

CREATE INDEX ix_import_issue_run_severity ON import_issue (import_run_id, severity);

CREATE TABLE session (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    data_source_id BIGINT NOT NULL, 
    import_run_id BIGINT NOT NULL, 
    raw_record_id BIGINT NOT NULL, 
    external_id TEXT NOT NULL, 
    agent_id BIGINT, 
    repository_id BIGINT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    ended_at TIMESTAMP WITH TIME ZONE, 
    duration_ms BIGINT, 
    outcome TEXT, 
    CONSTRAINT pk_session PRIMARY KEY (id), 
    CONSTRAINT ck_session_outcome CHECK (outcome IN ('completed','error','aborted','unknown')), 
    CONSTRAINT fk_session_agent_id_agent FOREIGN KEY(agent_id) REFERENCES agent (id), 
    CONSTRAINT fk_session_data_source_id_data_source FOREIGN KEY(data_source_id) REFERENCES data_source (id), 
    CONSTRAINT fk_session_import_run_id_import_run FOREIGN KEY(import_run_id) REFERENCES import_run (id), 
    CONSTRAINT fk_session_raw_record_id_raw_record FOREIGN KEY(raw_record_id) REFERENCES raw_record (id), 
    CONSTRAINT fk_session_repository_id_repository FOREIGN KEY(repository_id) REFERENCES repository (id), 
    CONSTRAINT uq_session_source_external UNIQUE (data_source_id, external_id)
);

COMMENT ON TABLE session IS 'One agent working session, from start to finish.';

CREATE INDEX ix_session_data_source_agent ON session (data_source_id, agent_id);

CREATE INDEX ix_session_started_at ON session (started_at);

CREATE TABLE model_call (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    session_id BIGINT NOT NULL, 
    raw_record_id BIGINT NOT NULL, 
    model_id BIGINT, 
    sequence_index INTEGER NOT NULL, 
    external_id TEXT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    duration_ms BIGINT, 
    input_tokens INTEGER, 
    output_tokens INTEGER, 
    cache_read_tokens INTEGER, 
    cache_creation_tokens INTEGER, 
    reasoning_tokens INTEGER, 
    stop_reason TEXT, 
    status TEXT DEFAULT 'unknown' NOT NULL, 
    error_code TEXT, 
    CONSTRAINT pk_model_call PRIMARY KEY (id), 
    CONSTRAINT ck_model_call_status CHECK (status IN ('ok','error','unknown')), 
    CONSTRAINT fk_model_call_model_id_model FOREIGN KEY(model_id) REFERENCES model (id), 
    CONSTRAINT fk_model_call_raw_record_id_raw_record FOREIGN KEY(raw_record_id) REFERENCES raw_record (id), 
    CONSTRAINT fk_model_call_session_id_session FOREIGN KEY(session_id) REFERENCES session (id) ON DELETE CASCADE, 
    CONSTRAINT uq_model_call_session_sequence UNIQUE (session_id, sequence_index)
);

COMMENT ON TABLE model_call IS 'One model inference call within a session.';

CREATE INDEX ix_model_call_model_id ON model_call (model_id);

CREATE INDEX ix_model_call_session_id ON model_call (session_id);

CREATE TABLE tool_call (
    id BIGINT GENERATED ALWAYS AS IDENTITY, 
    session_id BIGINT NOT NULL, 
    model_call_id BIGINT, 
    raw_record_id BIGINT NOT NULL, 
    tool_id BIGINT NOT NULL, 
    sequence_index INTEGER NOT NULL, 
    external_id TEXT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    duration_ms BIGINT, 
    status TEXT DEFAULT 'unknown' NOT NULL, 
    error_message TEXT, 
    arguments JSONB, 
    result_size INTEGER, 
    CONSTRAINT pk_tool_call PRIMARY KEY (id), 
    CONSTRAINT ck_tool_call_status CHECK (status IN ('ok','error','unknown')), 
    CONSTRAINT fk_tool_call_model_call_id_model_call FOREIGN KEY(model_call_id) REFERENCES model_call (id) ON DELETE SET NULL, 
    CONSTRAINT fk_tool_call_raw_record_id_raw_record FOREIGN KEY(raw_record_id) REFERENCES raw_record (id), 
    CONSTRAINT fk_tool_call_session_id_session FOREIGN KEY(session_id) REFERENCES session (id) ON DELETE CASCADE, 
    CONSTRAINT fk_tool_call_tool_id_tool FOREIGN KEY(tool_id) REFERENCES tool (id), 
    CONSTRAINT uq_tool_call_session_sequence UNIQUE (session_id, sequence_index)
);

COMMENT ON TABLE tool_call IS 'One tool invocation within a session.';

CREATE INDEX ix_tool_call_model_call_id ON tool_call (model_call_id);

CREATE INDEX ix_tool_call_session_id ON tool_call (session_id);

CREATE INDEX ix_tool_call_tool_id ON tool_call (tool_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

