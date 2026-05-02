-- scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
BEGIN;
DROP TABLE IF EXISTS school_meal_dish_ingredient_records;
DROP TABLE IF EXISTS school_meal_dish_records;
DROP TABLE IF EXISTS school_meal_ingredient_records;
DROP TABLE IF EXISTS school_meal_seasoning_records_nation;
DROP TABLE IF EXISTS school_meal_caterers;
DROP TABLE IF EXISTS school_meal_food_dictionary;
COMMIT;
