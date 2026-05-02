-- scripts/food_safety/migrations/001_create_tables.up.sql
-- Project: 食安風險追蹤器 (Food Safety Radar)
-- Purpose: Create the 7 food_* tables in the `dashboard` database.
--          Idempotent (CREATE TABLE IF NOT EXISTS) and transactional.
-- down:    migrations/001_create_tables.down.sql
BEGIN;

-- ── 1. food_inspection_tpe (TPE 20-year inspection statistics) ──
CREATE TABLE IF NOT EXISTS food_inspection_tpe (
    year                 INTEGER PRIMARY KEY,
    total_inspections    INTEGER,
    restaurant_insp      INTEGER,
    drink_shop_insp      INTEGER,
    street_vendor_insp   INTEGER,
    market_insp          INTEGER,
    supermarket_insp     INTEGER,
    manufacturer_insp    INTEGER,
    total_noncompliance  INTEGER,
    restaurant_nc        INTEGER,
    drink_shop_nc        INTEGER,
    street_vendor_nc     INTEGER,
    market_nc            INTEGER,
    supermarket_nc       INTEGER,
    manufacturer_nc      INTEGER,
    food_poisoning_cases INTEGER
);

-- ── 2. food_testing_tpe (TPE 20-year testing statistics) ──
CREATE TABLE IF NOT EXISTS food_testing_tpe (
    year             INTEGER PRIMARY KEY,
    total_tested     INTEGER,
    total_violations INTEGER,
    violation_rate   NUMERIC(5,2),
    viol_labeling    INTEGER,
    viol_ad          INTEGER,
    viol_additive    INTEGER,
    viol_container   INTEGER,
    viol_microbe     INTEGER,
    viol_mycotoxin   INTEGER,
    viol_vetdrug     INTEGER,
    viol_chemical    INTEGER,
    viol_composition INTEGER,
    viol_other       INTEGER
);

-- ── 3. food_restaurant_tpe (TPE certified restaurants, geocoded) ──
CREATE TABLE IF NOT EXISTS food_restaurant_tpe (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(200),
    address   VARCHAR(300),
    district  VARCHAR(50),
    grade     VARCHAR(10),    -- '優' or '良'
    lng       DOUBLE PRECISION,
    lat       DOUBLE PRECISION
);

-- ── 4. food_factory_ntpc (NTPC food factory registry, WGS84 coords) ──
CREATE TABLE IF NOT EXISTS food_factory_ntpc (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(200),
    address   VARCHAR(300),
    tax_id    VARCHAR(50),
    lng       DOUBLE PRECISION,
    lat       DOUBLE PRECISION,
    district  VARCHAR(50)
);

-- ── 5. food_inspection_by_city (MOHW dual-city inspection, 2026 only) ──
CREATE TABLE IF NOT EXISTS food_inspection_by_city (
    id                  SERIAL PRIMARY KEY,
    year                INTEGER NOT NULL,
    city                VARCHAR(20) NOT NULL,            -- '臺北市' or '新北市'
    venue               VARCHAR(40) NOT NULL,            -- 餐飲店/.../合計
    inspections         INTEGER,
    noncompliance       INTEGER,
    poisoning_cases     INTEGER,                         -- only on venue='合計'
    ntpc_violation_rate NUMERIC(5,2),                    -- only on venue='合計'
    UNIQUE (year, city, venue)
);

-- ── 6. food_type_violations (MOHW dual-city violations by food category) ──
CREATE TABLE IF NOT EXISTS food_type_violations (
    id        SERIAL PRIMARY KEY,
    year      INTEGER NOT NULL,
    city      VARCHAR(20) NOT NULL,
    category  VARCHAR(40) NOT NULL,
    count     INTEGER NOT NULL,
    UNIQUE (year, city, category)
);

-- ── 7. food_poisoning_cause (MOHW national food-poisoning by cause) ──
-- Populated by load_mohw_poisoning.py for future use; not yet wired into any
-- query_chart. Reserved as a fallback data source per design §4.
CREATE TABLE IF NOT EXISTS food_poisoning_cause (
    id      SERIAL PRIMARY KEY,
    year    INTEGER NOT NULL,
    cause   VARCHAR(60) NOT NULL,
    cases   INTEGER,
    persons INTEGER,
    UNIQUE (year, cause)
);

COMMIT;
