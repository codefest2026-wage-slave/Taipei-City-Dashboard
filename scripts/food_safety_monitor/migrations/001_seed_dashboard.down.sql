-- scripts/food_safety_monitor/migrations/001_seed_dashboard.down.sql
-- Reverse 001_seed_dashboard.up.sql. Removes ALL dashboard 504 / fsm_* rows.
BEGIN;
DELETE FROM dashboard_groups WHERE dashboard_id = 504;
DELETE FROM dashboards WHERE id = 504;
DELETE FROM query_charts WHERE index LIKE 'fsm_%';
DELETE FROM component_maps WHERE index LIKE 'fsm_%';
DELETE FROM component_charts WHERE index LIKE 'fsm_%';
DELETE FROM components WHERE id BETWEEN 1020 AND 1026;
COMMIT;
