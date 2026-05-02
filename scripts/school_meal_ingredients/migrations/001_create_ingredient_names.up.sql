-- scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql
-- Project: 校園食材登入平台 食材名稱去重表
-- Purpose: Create school_meal_ingredient_names dictionary table in `dashboard`.
--          Idempotent (CREATE TABLE IF NOT EXISTS) and transactional.
-- down:    migrations/001_create_ingredient_names.down.sql
BEGIN;

CREATE TABLE IF NOT EXISTS school_meal_ingredient_names (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) UNIQUE NOT NULL,
    occurrence      INTEGER       NOT NULL DEFAULT 0,
    first_seen_ym   VARCHAR(7),                       -- 'YYYY-MM'
    last_seen_ym    VARCHAR(7),                       -- 'YYYY-MM'
    source_counties TEXT[]                            -- e.g. {'臺北市','新北市'}
);

CREATE INDEX IF NOT EXISTS idx_school_meal_ingredient_names_name
    ON school_meal_ingredient_names (name);

COMMIT;
