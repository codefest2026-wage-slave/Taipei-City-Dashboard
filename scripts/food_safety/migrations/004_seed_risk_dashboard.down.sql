-- scripts/food_safety/migrations/004_seed_risk_dashboard.down.sql
-- Reverse of 004_seed_risk_dashboard.up.sql
BEGIN;

DELETE FROM dashboard_groups WHERE dashboard_id = 504;
DELETE FROM dashboards       WHERE id = 504;
DELETE FROM query_charts     WHERE index = 'food_risk_matrix';
DELETE FROM component_charts WHERE index = 'food_risk_matrix';
DELETE FROM components       WHERE id = 1016;

COMMIT;
