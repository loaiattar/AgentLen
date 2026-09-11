"""Dashboard read views — the light-CQRS read side.

Five views feeding the dashboard, each keeping `data_source_id` so a metric
declared `per_source_only` is never aggregated across sources without warning,
and each exposing `*_present` / `*_total` counters next to any aggregate over a
nullable column.

Those counters are the point. `SUM` and `AVG` skip NULLs silently, so a figure
computed over 12% of the rows looks exactly like one computed over all of them.
The counters are what let the API return a `coverage` object and the front say
"partial" instead of showing a confident wrong number (ADR-009).

**Deviation from DATA_MODEL.md §7, deliberate.** The documented
`v_session_metrics` LEFT JOINs `model_call` and `tool_call` in the same query
and groups by session. That fans out: one session with 3 model calls and 5 tool
calls yields 15 rows, so `sum(input_tokens)` counts every model call 5 times.
Measured on that exact shape: 3000 instead of 600, and 15 token records present
instead of 3. `count(DISTINCT mc.id)` survives because of the DISTINCT, which is
why the error is easy to miss. The children are aggregated in separate LATERAL
subqueries here instead. DATA_MODEL.md needs the same correction.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# One session per row, with its children aggregated independently.
V_SESSION_METRICS = """
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
) t ON TRUE
"""

# Sessions with no started_at cannot be placed on a day and are excluded here.
# They still count in the overview; the difference between the two totals is
# itself a coverage signal rather than something to paper over.
V_DAILY_ACTIVITY = """
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
GROUP BY 1, 2
"""

V_TOOL_USAGE = """
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
GROUP BY tc.tool_id, t.name, s.data_source_id
"""

# model_id is nullable: a trace can name a model we could not resolve. Those
# calls are kept under a NULL model rather than dropped, so the volumetry adds
# up to the real number of calls.
V_MODEL_USAGE = """
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
GROUP BY mc.model_id, m.name, p.name, s.data_source_id
"""

V_IMPORT_QUALITY = """
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
) iss ON TRUE
"""

_VIEWS = (
    ("v_session_metrics", V_SESSION_METRICS),
    ("v_daily_activity", V_DAILY_ACTIVITY),
    ("v_tool_usage", V_TOOL_USAGE),
    ("v_model_usage", V_MODEL_USAGE),
    ("v_import_quality", V_IMPORT_QUALITY),
)


def upgrade() -> None:
    for _, statement in _VIEWS:
        op.execute(statement)


def downgrade() -> None:
    # Reverse order: v_daily_activity is built on v_session_metrics.
    for name, _ in reversed(_VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {name}")
