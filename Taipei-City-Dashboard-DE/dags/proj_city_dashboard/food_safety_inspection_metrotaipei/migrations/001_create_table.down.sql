-- scripts/food_safety_inspection_metrotaipei/migrations/001_create_table.down.sql
-- Rollback for 001: drop the food_safety_inspection_metrotaipei table.
-- up:   migrations/001_create_table.up.sql
BEGIN;

DROP TABLE IF EXISTS food_safety_inspection_metrotaipei CASCADE;

COMMIT;
