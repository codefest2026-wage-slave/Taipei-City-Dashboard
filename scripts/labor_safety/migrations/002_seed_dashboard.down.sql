-- scripts/labor_safety/migrations/002_seed_dashboard.down.sql
-- Rollback for 002: remove dashboard 502 and all labor_% registrations.
-- up:   migrations/002_seed_dashboard.up.sql
-- Order: junction (dashboard_groups) → parent (dashboards) → leaf
--        registration tables → components last (FK target).
BEGIN;

DELETE FROM dashboard_groups WHERE dashboard_id = 502;
DELETE FROM dashboards       WHERE id           = 502;
DELETE FROM query_charts     WHERE index LIKE 'labor_%';
DELETE FROM component_maps   WHERE index LIKE 'labor_disaster%';
DELETE FROM component_charts WHERE index LIKE 'labor_%';
DELETE FROM components       WHERE id BETWEEN 1005 AND 1010;

COMMIT;
