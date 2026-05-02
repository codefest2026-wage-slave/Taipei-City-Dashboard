-- scripts/food_safety/migrations/001_create_tables.down.sql
-- Rollback for 001: drop all 7 food_safety tables.
-- up:   migrations/001_create_tables.up.sql
BEGIN;

DROP TABLE IF EXISTS food_poisoning_cause     CASCADE;
DROP TABLE IF EXISTS food_type_violations     CASCADE;
DROP TABLE IF EXISTS food_inspection_by_city  CASCADE;
DROP TABLE IF EXISTS food_factory_ntpc        CASCADE;
DROP TABLE IF EXISTS food_restaurant_tpe      CASCADE;
DROP TABLE IF EXISTS food_testing_tpe         CASCADE;
DROP TABLE IF EXISTS food_inspection_tpe      CASCADE;

COMMIT;
