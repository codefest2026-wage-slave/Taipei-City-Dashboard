-- scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql
-- Project: 校園食材登入平台 raw-record tables
-- Purpose: Land every snapshot CSV into a typed table. Idempotent.
-- down:    migrations/002_create_raw_tables.down.sql
BEGIN;

-- 1. food_chinese_names.csv → food_dictionary (one-shot 食材中文名稱資料集)
CREATE TABLE IF NOT EXISTS school_meal_food_dictionary (
    id              SERIAL PRIMARY KEY,
    food_category   VARCHAR(100),
    formal_name     VARCHAR(200) NOT NULL,
    alias_name      TEXT
);
CREATE INDEX IF NOT EXISTS idx_smfd_formal_name
    ON school_meal_food_dictionary (formal_name);

-- 2. nation_*_學校供餐團膳業者*.csv → caterers
CREATE TABLE IF NOT EXISTS school_meal_caterers (
    id          SERIAL PRIMARY KEY,
    county      VARCHAR(20),
    name        VARCHAR(300) NOT NULL,
    tax_id      VARCHAR(20),
    address     VARCHAR(500)
);
CREATE INDEX IF NOT EXISTS idx_smc_tax_id
    ON school_meal_caterers (tax_id);

-- 3. nation_*_調味料及供應商*.csv → seasoning records (national, date-range entries)
CREATE TABLE IF NOT EXISTS school_meal_seasoning_records_nation (
    id                          SERIAL PRIMARY KEY,
    county                      VARCHAR(20),
    district                    VARCHAR(50),
    school_name                 VARCHAR(300),
    start_date                  DATE,
    end_date                    DATE,
    caterer_name                VARCHAR(300),
    caterer_tax_id              VARCHAR(20),
    seasoning_supplier_name     VARCHAR(300),
    seasoning_name              VARCHAR(200),
    certification_label         VARCHAR(100),
    certification_no            VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_smsrn_seasoning_name
    ON school_meal_seasoning_records_nation (seasoning_name);

-- 4. (tpe|ntpc)_*_*_午餐食材及供應商*.csv → ingredient records
CREATE TABLE IF NOT EXISTS school_meal_ingredient_records (
    id                          SERIAL PRIMARY KEY,
    -- provenance from filename (the API query that produced this row)
    year_queried                SMALLINT NOT NULL,
    month_queried               SMALLINT NOT NULL,
    county_queried              VARCHAR(20) NOT NULL,
    grade_queried               VARCHAR(20) NOT NULL,
    -- row data
    county                      VARCHAR(20),
    district                    VARCHAR(50),
    school_name                 VARCHAR(300),
    meal_date                   DATE,
    caterer_name                VARCHAR(300),
    caterer_tax_id              VARCHAR(20),
    ingredient_supplier_name    VARCHAR(300),
    ingredient_supplier_tax_id  VARCHAR(20),
    ingredient_name             VARCHAR(200),
    seasoning_supplier_name     VARCHAR(300),
    seasoning_supplier_tax_id   VARCHAR(20),
    seasoning_name              VARCHAR(200),
    certification_label         VARCHAR(100),
    certification_no            VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_smir_provenance
    ON school_meal_ingredient_records (year_queried, month_queried, county_queried);
CREATE INDEX IF NOT EXISTS idx_smir_ingredient_name
    ON school_meal_ingredient_records (ingredient_name);

-- 5. (tpe|ntpc)_*_*_午餐菜色資料集.csv → dish records
CREATE TABLE IF NOT EXISTS school_meal_dish_records (
    id                  SERIAL PRIMARY KEY,
    year_queried        SMALLINT NOT NULL,
    month_queried       SMALLINT NOT NULL,
    county_queried      VARCHAR(20) NOT NULL,
    grade_queried       VARCHAR(20) NOT NULL,
    county              VARCHAR(20),
    district            VARCHAR(50),
    school_name         VARCHAR(300),
    meal_date           DATE,
    dish_name           VARCHAR(200)
);
CREATE INDEX IF NOT EXISTS idx_smdr_provenance
    ON school_meal_dish_records (year_queried, month_queried, county_queried);
CREATE INDEX IF NOT EXISTS idx_smdr_dish_name
    ON school_meal_dish_records (dish_name);

-- 6. (tpe|ntpc)_*_*_午餐菜色及食材*.csv → dish-ingredient join records
CREATE TABLE IF NOT EXISTS school_meal_dish_ingredient_records (
    id                          SERIAL PRIMARY KEY,
    year_queried                SMALLINT NOT NULL,
    month_queried               SMALLINT NOT NULL,
    county_queried              VARCHAR(20) NOT NULL,
    grade_queried               VARCHAR(20) NOT NULL,
    county                      VARCHAR(20),
    district                    VARCHAR(50),
    school_name                 VARCHAR(300),
    meal_date                   DATE,
    caterer_name                VARCHAR(300),
    caterer_tax_id              VARCHAR(20),
    ingredient_supplier_name    VARCHAR(300),
    ingredient_supplier_tax_id  VARCHAR(20),
    dish_category               VARCHAR(100),
    dish_name                   VARCHAR(200),
    ingredient_name             VARCHAR(200),
    seasoning_supplier_name     VARCHAR(300),
    seasoning_supplier_tax_id   VARCHAR(20),
    seasoning_name              VARCHAR(200),
    certification_label         VARCHAR(100),
    certification_no            VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_smdir_provenance
    ON school_meal_dish_ingredient_records (year_queried, month_queried, county_queried);
CREATE INDEX IF NOT EXISTS idx_smdir_ingredient_name
    ON school_meal_dish_ingredient_records (ingredient_name);
CREATE INDEX IF NOT EXISTS idx_smdir_dish_name
    ON school_meal_dish_ingredient_records (dish_name);

COMMIT;
