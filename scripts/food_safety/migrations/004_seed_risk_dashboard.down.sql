-- scripts/food_safety/migrations/004_seed_risk_dashboard.down.sql
-- Reverse of 004_seed_risk_dashboard.up.sql.
--
-- 004 no longer creates anything (component 1016 is owned by 002), so the
-- only thing to undo is the cleanup hook — and that's a delete that nothing
-- here can resurrect. No-op for symmetry; the canonical down for the 1016
-- component is 002_seed_dashboard.down.sql.
BEGIN;
SELECT 1;  -- no-op
COMMIT;
