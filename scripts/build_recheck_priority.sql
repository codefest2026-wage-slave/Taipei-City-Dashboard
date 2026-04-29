-- ──────────────────────────────────────────────────────────────────
-- L-01-1 複查優先佇列引擎：物化風險特徵表
-- ──────────────────────────────────────────────────────────────────
-- 為每位「雇主」（以 company_name 為 key）聚合：
--   - 違規次數（按法規類型分）
--   - 累計罰款
--   - 最近違規日期、距今天數
--   - 行業別（透過正規化 company_name JOIN GCIS）
--   - 資本額（員工規模代理）
--   - 是否含職災紀錄
--   - 違規嚴重性（職安法權重 > 勞基法 > 性平法）
-- ──────────────────────────────────────────────────────────────────

BEGIN;

-- 共用 normalize function：去除「股份有限公司」「有限公司」「(即...)」等後綴
DROP FUNCTION IF EXISTS norm_company(text);
CREATE FUNCTION norm_company(name text) RETURNS text AS $$
  SELECT regexp_replace(
    regexp_replace(
      regexp_replace(
        COALESCE(name, ''),
        '\s*\([^)]*\)\s*', '', 'g'  -- remove (即...) (代表人...)
      ),
      '股份有限公司|有限公司|商行|合夥事業|工作室|企業社|商號', '', 'g'
    ),
    '\s+', '', 'g'  -- remove all whitespace
  );
$$ LANGUAGE SQL IMMUTABLE;

-- ──────────────────────────────────────────────
-- TPE 物化表
-- ──────────────────────────────────────────────
DROP TABLE IF EXISTS labor_recheck_priority_tpe;
CREATE TABLE labor_recheck_priority_tpe AS
WITH agg AS (
  SELECT
    company_name,
    COUNT(*) FILTER (WHERE law_category = '勞基法')   AS labor_count,
    COUNT(*) FILTER (WHERE law_category = '職安法')   AS safety_count,
    COUNT(*) FILTER (WHERE law_category = '性平法')   AS gender_count,
    COUNT(*)                                          AS total_violations,
    COALESCE(SUM(fine_amount), 0)                     AS total_fine,
    MAX(COALESCE(penalty_date, announcement_date))    AS last_violation_date,
    (CURRENT_DATE - MAX(COALESCE(penalty_date, announcement_date)))::int
                                                      AS days_since_last
  FROM labor_violations_tpe
  GROUP BY company_name
),
disaster_agg AS (
  SELECT company_name, COUNT(*) AS disaster_count,
         SUM(deaths) AS disaster_deaths, SUM(injuries) AS disaster_injuries
  FROM labor_disasters_tpe
  GROUP BY company_name
),
gcis_match AS (
  SELECT DISTINCT ON (norm_company(company_name))
    norm_company(company_name) AS norm_name,
    tax_id, company_name AS gcis_name, address, industry_code, capital
  FROM gcis_companies_tpe
  ORDER BY norm_company(company_name), capital DESC NULLS LAST
)
SELECT
  ROW_NUMBER() OVER () AS id,
  a.company_name,
  g.tax_id,
  g.address,
  g.industry_code,
  ic.name AS industry_name,
  LEFT(g.industry_code, 1) AS industry_major,
  g.capital,
  a.labor_count,
  a.safety_count,
  a.gender_count,
  a.total_violations,
  a.total_fine,
  a.last_violation_date,
  a.days_since_last,
  COALESCE(d.disaster_count, 0)   AS disaster_count,
  COALESCE(d.disaster_deaths, 0)  AS disaster_deaths,
  COALESCE(d.disaster_injuries, 0) AS disaster_injuries,
  -- 風險評分（台北版：服務業權重，工時類加重）
  -- 違規頻率×0.4 + 距上次違規衰減×0.3 + 員工規模(資本)×0.2 + 違規嚴重性×0.1
  ROUND((
    LEAST(a.total_violations::numeric / 10, 1.0) * 40
    + GREATEST(0, 1 - a.days_since_last::numeric / 730) * 30
    + LEAST(COALESCE(g.capital, 0)::numeric / 50000000, 1.0) * 20
    + LEAST((a.safety_count * 3 + a.labor_count * 2 + a.gender_count * 1)::numeric / 30, 1.0) * 10
    + COALESCE(d.disaster_count, 0) * 5
  )::numeric, 1) AS risk_score,
  'taipei' AS city
FROM agg a
LEFT JOIN gcis_match g ON norm_company(a.company_name) = g.norm_name
LEFT JOIN industry_codes ic ON g.industry_code = ic.code AND ic.level = 4
LEFT JOIN disaster_agg d ON a.company_name = d.company_name;

CREATE INDEX idx_recheck_tpe_score ON labor_recheck_priority_tpe(risk_score DESC);
CREATE INDEX idx_recheck_tpe_name ON labor_recheck_priority_tpe(company_name);

-- ──────────────────────────────────────────────
-- NTPC 物化表（評分公式調整：職安類加重）
-- ──────────────────────────────────────────────
DROP TABLE IF EXISTS labor_recheck_priority_ntpc;
CREATE TABLE labor_recheck_priority_ntpc AS
WITH agg AS (
  SELECT
    company_name,
    COUNT(*) FILTER (WHERE law_category = '勞基法') AS labor_count,
    COUNT(*) FILTER (WHERE law_category = '職安法') AS safety_count,
    COUNT(*) FILTER (WHERE law_category = '性平法') AS gender_count,
    COUNT(*)                                        AS total_violations,
    COALESCE(SUM(fine_amount), 0)                   AS total_fine,
    MAX(penalty_date)                               AS last_violation_date,
    (CURRENT_DATE - MAX(penalty_date))::int         AS days_since_last,
    -- NTPC 違規本身有 tax_id，可直接保留
    MAX(tax_id) AS ntpc_tax_id
  FROM labor_violations_ntpc
  GROUP BY company_name
),
disaster_agg AS (
  SELECT industry, district, COUNT(*) AS n
  FROM labor_disasters_ntpc GROUP BY industry, district
),
gcis_match AS (
  SELECT DISTINCT ON (norm_company(company_name))
    norm_company(company_name) AS norm_name,
    tax_id, company_name AS gcis_name, address, industry_code, capital
  FROM gcis_companies_ntpc
  ORDER BY norm_company(company_name), capital DESC NULLS LAST
)
SELECT
  ROW_NUMBER() OVER () AS id,
  a.company_name,
  COALESCE(g.tax_id, a.ntpc_tax_id) AS tax_id,
  g.address,
  g.industry_code,
  ic.name AS industry_name,
  LEFT(g.industry_code, 1) AS industry_major,
  g.capital,
  a.labor_count,
  a.safety_count,
  a.gender_count,
  a.total_violations,
  a.total_fine,
  a.last_violation_date,
  a.days_since_last,
  0::int AS disaster_count,    -- NTPC disasters 無 company-level 資訊
  0::int AS disaster_deaths,
  0::int AS disaster_injuries,
  -- 風險評分（新北版：製造業權重，職安類加重）
  ROUND((
    LEAST(a.total_violations::numeric / 10, 1.0) * 40
    + GREATEST(0, 1 - a.days_since_last::numeric / 730) * 30
    + LEAST(COALESCE(g.capital, 0)::numeric / 50000000, 1.0) * 20
    + LEAST((a.safety_count * 4 + a.labor_count * 1.5 + a.gender_count * 1)::numeric / 30, 1.0) * 10
  )::numeric, 1) AS risk_score,
  'newtaipei' AS city
FROM agg a
LEFT JOIN gcis_match g ON norm_company(a.company_name) = g.norm_name
LEFT JOIN industry_codes ic ON g.industry_code = ic.code AND ic.level = 4;

CREATE INDEX idx_recheck_ntpc_score ON labor_recheck_priority_ntpc(risk_score DESC);
CREATE INDEX idx_recheck_ntpc_name ON labor_recheck_priority_ntpc(company_name);

COMMIT;

-- ──────────────────────────────────────────────
-- 驗證
-- ──────────────────────────────────────────────
SELECT 'tpe_total' AS m, COUNT(*) FROM labor_recheck_priority_tpe
UNION ALL SELECT 'tpe_with_industry', COUNT(*) FROM labor_recheck_priority_tpe WHERE industry_name IS NOT NULL
UNION ALL SELECT 'tpe_with_capital', COUNT(*) FROM labor_recheck_priority_tpe WHERE capital IS NOT NULL
UNION ALL SELECT 'ntpc_total', COUNT(*) FROM labor_recheck_priority_ntpc
UNION ALL SELECT 'ntpc_with_industry', COUNT(*) FROM labor_recheck_priority_ntpc WHERE industry_name IS NOT NULL
UNION ALL SELECT 'ntpc_with_capital', COUNT(*) FROM labor_recheck_priority_ntpc WHERE capital IS NOT NULL;
