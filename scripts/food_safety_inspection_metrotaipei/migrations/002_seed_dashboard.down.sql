-- scripts/food_safety_inspection_metrotaipei/migrations/002_seed_dashboard.down.sql
-- Rollback for 002: remove food_inspection_rate registration from dashboardmanager DB.
-- up: migrations/002_seed_dashboard.up.sql
BEGIN;

DELETE FROM dashboard_groups WHERE dashboard_id = 1200;
DELETE FROM dashboards       WHERE id = 1200;
DELETE FROM query_charts     WHERE index = 'food_inspection_rate';
DELETE FROM component_charts WHERE index = 'food_inspection_rate';
DELETE FROM components       WHERE id = 1200;

COMMIT;
