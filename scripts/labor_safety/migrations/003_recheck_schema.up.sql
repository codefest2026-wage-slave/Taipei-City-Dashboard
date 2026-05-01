-- scripts/labor_safety/migrations/003_recheck_schema.up.sql
-- Project: 工作安全燈號 — 雙北複查優先佇列引擎 (component 1019)
-- Purpose: GCIS company registration tables (joined by build_recheck_priority).
--          The labor_recheck_priority_{tpe,ntpc} tables themselves are
--          CREATE-TABLE-AS in build_recheck_priority.sql, not pre-created here.
-- down:    003_recheck_schema.down.sql
BEGIN;

CREATE TABLE IF NOT EXISTS gcis_companies_tpe (
  tax_id           VARCHAR(20)  NOT NULL,
  company_name     VARCHAR(300) NOT NULL,
  address          VARCHAR(400),
  industry_code    VARCHAR(10),
  capital          BIGINT,
  established_date DATE,
  PRIMARY KEY (tax_id)
);
CREATE INDEX IF NOT EXISTS idx_gcis_companies_tpe_industry ON gcis_companies_tpe (industry_code);
CREATE INDEX IF NOT EXISTS idx_gcis_companies_tpe_name     ON gcis_companies_tpe (company_name);

CREATE TABLE IF NOT EXISTS gcis_companies_ntpc (
  tax_id           VARCHAR(20)  NOT NULL,
  company_name     VARCHAR(300) NOT NULL,
  address          VARCHAR(400),
  industry_code    VARCHAR(10),
  capital          BIGINT,
  established_date DATE,
  PRIMARY KEY (tax_id)
);
CREATE INDEX IF NOT EXISTS idx_gcis_companies_ntpc_industry ON gcis_companies_ntpc (industry_code);
CREATE INDEX IF NOT EXISTS idx_gcis_companies_ntpc_name     ON gcis_companies_ntpc (company_name);

-- industry_codes is joined by build_recheck_priority.sql to enrich industry_name.
-- Sourced from 主計總處 行業分類 (industrial.xml).
CREATE TABLE IF NOT EXISTS industry_codes (
  code  VARCHAR(10) PRIMARY KEY,
  name  VARCHAR(200) NOT NULL,
  level INTEGER  -- 1=大類(A-Z), 2=中類, 3=小類, 4=細類
);

COMMIT;
