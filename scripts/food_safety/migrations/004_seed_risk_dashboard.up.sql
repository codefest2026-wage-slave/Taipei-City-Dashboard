-- scripts/food_safety/migrations/004_seed_risk_dashboard.up.sql
-- DEPRECATED: 食安風險矩陣 (component 1016) is now seeded by 002 alongside
-- the other 食安風險追蹤器 components. The standalone dashboard 504
-- 'food_risk_matrix' is no longer created — dashboard id 504 belongs to
-- food_safety_monitor (校內/校外食安地圖).
--
-- This migration is kept as a forward-compatible cleanup hook so existing
-- environments where dashboard 504='food_risk_matrix' was installed get the
-- standalone dashboard removed on next apply. The 1016 component itself is
-- now owned by 002 and will be re-registered there.
-- down: migrations/004_seed_risk_dashboard.down.sql
BEGIN;

-- Drop the standalone 食安風險矩陣 dashboard if a previous apply created it.
-- Only deletes when the 504 row is the food_risk_matrix one — leaves the
-- food_safety_monitor 504 (created by scripts/food_safety_monitor/) intact.
DELETE FROM dashboard_groups
  WHERE dashboard_id = 504
    AND EXISTS (SELECT 1 FROM dashboards
                WHERE id = 504 AND index = 'food_risk_matrix');
DELETE FROM dashboards WHERE id = 504 AND index = 'food_risk_matrix';

COMMIT;
