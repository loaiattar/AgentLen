BEGIN;

-- Running upgrade 0001 -> 0002

CREATE VIEW v_session_metrics AS
SELECT
    s.id                        AS session_id,
    s.data_source_id,
    s.agent_id,
    s.import_run_id,
    s.started_at,
    s.duration_ms,
    m.model_call_count,
    m.input_tokens,
    m.output_tokens,
    m.cache_read_tokens,
    m.token_records_present,
    m.token_records_total,
    m.cache_records_present,
    t.tool_call_count,
    t.tool_error_count,
    t.tool_status_known_count
FROM session s
LEFT JOIN LATERAL (
    SELECT
        count(*)                     AS model_call_count,
        sum(mc.input_tokens)         AS input_tokens,
        sum(mc.output_tokens)        AS output_tokens,
        sum(mc.cache_read_tokens)    AS cache_read_tokens,
        -- count(col) counts non-NULLs: this is the coverage numerator.
        count(mc.input_tokens)       AS token_records_present,
        count(*)                     AS token_records_total,
        count(mc.cache_read_tokens)  AS cache_records_present
    FROM model_call mc
    WHERE mc.session_id = s.id
) m ON TRUE
LEFT JOIN LATERAL (
    SELECT
        count(*)                                            AS tool_call_count,
        count(*) FILTER (WHERE tc.status = 'error')         AS tool_error_count,
        -- 'unknown' leaves the denominator entirely: counting it as a success
        -- would deflate the error rate on any source that omits tool status.
        count(*) FILTER (WHERE tc.status IN ('ok','error')) AS tool_status_known_count
    FROM tool_call tc
    WHERE tc.session_id = s.id
) t ON TRUE;

CREATE VIEW v_daily_activity AS
SELECT
    (sm.started_at AT TIME ZONE 'UTC')::date AS day,
    sm.data_source_id,
    count(*)                          AS session_count,
    sum(sm.model_call_count)          AS model_call_count,
    sum(sm.tool_call_count)           AS tool_call_count,
    sum(sm.input_tokens)              AS input_tokens,
    sum(sm.output_tokens)             AS output_tokens,
    sum(sm.token_records_present)     AS token_records_present,
    sum(sm.token_records_total)       AS token_records_total
FROM v_session_metrics sm
WHERE sm.started_at IS NOT NULL
GROUP BY 1, 2;

CREATE VIEW v_tool_usage AS
SELECT
    tc.tool_id,
    t.name              AS tool_name,
    s.data_source_id,
    count(*)                                            AS call_count,
    count(*) FILTER (WHERE tc.status = 'error')         AS error_count,
    count(*) FILTER (WHERE tc.status IN ('ok','error')) AS status_known_count
FROM tool_call tc
JOIN tool t     ON t.id = tc.tool_id
JOIN session s  ON s.id = tc.session_id
GROUP BY tc.tool_id, t.name, s.data_source_id;

CREATE VIEW v_model_usage AS
SELECT
    mc.model_id,
    m.name              AS model_name,
    p.name              AS provider_name,
    s.data_source_id,
    count(*)                        AS call_count,
    sum(mc.input_tokens)            AS input_tokens,
    sum(mc.output_tokens)           AS output_tokens,
    count(mc.input_tokens)          AS token_records_present,
    count(*)                        AS token_records_total,
    sum(mc.cache_read_tokens)       AS cache_read_tokens,
    count(mc.cache_read_tokens)     AS cache_records_present
FROM model_call mc
JOIN session s        ON s.id = mc.session_id
LEFT JOIN model m     ON m.id = mc.model_id
LEFT JOIN provider p  ON p.id = m.provider_id
GROUP BY mc.model_id, m.name, p.name, s.data_source_id;

CREATE VIEW v_import_quality AS
SELECT
    ir.id               AS import_run_id,
    ir.data_source_id,
    ir.status,
    ir.records_read,
    ir.records_imported,
    ir.records_duplicate,
    ir.records_rejected,
    ir.fields_missing,
    ir.created_at,
    iss.issue_count
FROM import_run ir
LEFT JOIN LATERAL (
    SELECT count(*) AS issue_count
    FROM import_issue ii
    WHERE ii.import_run_id = ir.id
) iss ON TRUE;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

COMMIT;

