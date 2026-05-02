-- scripts/labor_safety/migrations/004_register_recheck.down.sql
-- Rollback for 004: remove component 1019 from dashboard 502 + all registrations.
-- up: 004_register_recheck.up.sql
BEGIN;

UPDATE dashboards
SET components = array_remove(components, 1019),
    updated_at = NOW()
WHERE id = 502;

DELETE FROM query_charts     WHERE index = 'labor_recheck_priority';
DELETE FROM component_maps   WHERE index IN ('labor_recheck_priority', 'labor_recheck_priority_ntpc');
DELETE FROM component_charts WHERE index = 'labor_recheck_priority';
DELETE FROM components       WHERE id = 1019;

COMMIT;
