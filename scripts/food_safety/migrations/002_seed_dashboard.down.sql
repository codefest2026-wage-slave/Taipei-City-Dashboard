-- scripts/food_safety/migrations/002_seed_dashboard.down.sql
-- Rollback for 002: remove all food_% registrations from dashboardmanager DB.
-- up:   migrations/002_seed_dashboard.up.sql
BEGIN;

DELETE FROM dashboard_groups WHERE dashboard_id = 503;
DELETE FROM dashboards       WHERE id = 503;
DELETE FROM query_charts     WHERE index LIKE 'food_%';
DELETE FROM component_maps   WHERE index LIKE 'food_%';
DELETE FROM component_charts WHERE index LIKE 'food_%';
DELETE FROM components       WHERE id BETWEEN 1011 AND 1016;
DELETE FROM components       WHERE id IN (14, 16);

COMMIT;
