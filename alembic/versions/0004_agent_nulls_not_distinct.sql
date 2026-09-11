BEGIN;

-- Running upgrade 0003 -> 0004

UPDATE session AS s
SET agent_id = grouped.survivor_id
FROM (
    SELECT id, min(id) OVER (PARTITION BY name, version) AS survivor_id
    FROM agent
) AS grouped
WHERE s.agent_id = grouped.id
  AND grouped.id <> grouped.survivor_id;

DELETE FROM agent AS duplicate
USING agent AS survivor
WHERE duplicate.name = survivor.name
  AND duplicate.version IS NOT DISTINCT FROM survivor.version
  AND duplicate.id > survivor.id;

ALTER TABLE agent DROP CONSTRAINT uq_agent_name_version;

ALTER TABLE agent ADD CONSTRAINT uq_agent_name_version UNIQUE NULLS NOT DISTINCT (name, version);

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

COMMIT;

