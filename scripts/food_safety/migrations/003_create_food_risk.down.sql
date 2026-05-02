-- scripts/food_safety/migrations/003_create_food_risk.down.sql
-- Reverse of 003_create_food_risk.up.sql
BEGIN;

DROP INDEX IF EXISTS idx_food_risk_result;
DROP INDEX IF EXISTS idx_food_risk_business;
DROP INDEX IF EXISTS idx_food_risk_city_hazard;
DROP TABLE IF EXISTS food_risk_inspection;

COMMIT;
