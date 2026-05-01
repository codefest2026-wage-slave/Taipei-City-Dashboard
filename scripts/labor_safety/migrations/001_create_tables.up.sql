-- scripts/labor_safety/migrations/001_create_tables.up.sql
-- Project: 工作安全燈號 (Labor Safety Radar)
-- Purpose: Create the 6 labor_* tables in the `dashboard` database.
--          Idempotent (CREATE TABLE IF NOT EXISTS) and transactional.
-- down:    migrations/001_create_tables.down.sql
BEGIN;

-- ──────────────────────────────────────────────
-- 1. labor_violations_tpe
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS labor_violations_tpe (
    id                SERIAL PRIMARY KEY,
    announcement_date DATE,
    penalty_date      DATE,
    doc_no            VARCHAR(200),
    company_name      VARCHAR(300) NOT NULL,
    principal         VARCHAR(100),
    law_category      VARCHAR(20)  NOT NULL,  -- '勞基法' '性平法' '職安法'
    law_article       VARCHAR(500),
    violation_content TEXT,
    fine_amount       INTEGER               -- NULL for 職安法 (no fine field)
);

-- ──────────────────────────────────────────────
-- 2. labor_violations_ntpc
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS labor_violations_ntpc (
    id                SERIAL PRIMARY KEY,
    penalty_date      DATE,
    law_category      VARCHAR(20)  NOT NULL,
    law_article       VARCHAR(500),
    company_name      VARCHAR(300) NOT NULL,
    principal         VARCHAR(100),
    tax_id            VARCHAR(50),
    violation_content TEXT,
    doc_no            VARCHAR(200),
    fine_amount       INTEGER
);

-- ──────────────────────────────────────────────
-- 3. labor_disasters_tpe
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS labor_disasters_tpe (
    id              SERIAL PRIMARY KEY,
    incident_date   DATE,
    company_name    VARCHAR(300),
    address         VARCHAR(300),
    disaster_type   VARCHAR(100),
    deaths          INTEGER DEFAULT 0,
    injuries        INTEGER DEFAULT 0,
    lng             DOUBLE PRECISION,
    lat             DOUBLE PRECISION
);

-- ──────────────────────────────────────────────
-- 4. labor_disasters_ntpc
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS labor_disasters_ntpc (
    id              SERIAL PRIMARY KEY,
    incident_date   DATE,
    disaster_type   VARCHAR(100),
    deaths          INTEGER DEFAULT 0,
    injuries        INTEGER DEFAULT 0,
    district        VARCHAR(20),
    industry        VARCHAR(100)
);

-- ──────────────────────────────────────────────
-- 5. labor_disputes_industry_tpe
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS labor_disputes_industry_tpe (
    id          SERIAL PRIMARY KEY,
    year        INTEGER NOT NULL,
    period      VARCHAR(20),
    industry    VARCHAR(100) NOT NULL,
    case_count  INTEGER NOT NULL
);

-- ──────────────────────────────────────────────
-- 6. labor_insurance_monthly_tpe
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS labor_insurance_monthly_tpe (
    id               SERIAL PRIMARY KEY,
    period_label     VARCHAR(20)    NOT NULL,
    period_date      DATE           NOT NULL,
    insured_units    INTEGER,
    insured_persons  INTEGER,
    benefit_cases    INTEGER,
    benefit_amount   BIGINT,
    new_seekers      INTEGER,
    new_openings     INTEGER,
    placed_seekers   INTEGER,
    placed_openings  INTEGER,
    placement_rate   NUMERIC(5,2),
    utilization_rate NUMERIC(5,2),
    accident_cases   INTEGER,
    accident_deaths  INTEGER
);

COMMIT;
