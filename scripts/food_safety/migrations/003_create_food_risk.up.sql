-- scripts/food_safety/migrations/003_create_food_risk.up.sql
-- Project: 食安風險矩陣 (Food Risk Matrix) — 業者頻率 × 危害等級
-- Purpose: Create the food_risk_inspection table in the `dashboard` database.
--          Source: 食藥署食品查核及檢驗資訊平台2026-05-02 (台北新北)
--          Pre-processed by scripts/food_safety/main.py — 帶 hazard_level 五階分級
--          (critical/high/medium/low/info) 與 violated_law_standardized 欄位
-- down:    migrations/003_create_food_risk.down.sql
BEGIN;

CREATE TABLE IF NOT EXISTS food_risk_inspection (
    id                        SERIAL PRIMARY KEY,
    source_id                 INTEGER,
    business_type             VARCHAR(20),    -- '個人農場' | '商業業者'
    business_name             VARCHAR(300),
    address                   VARCHAR(500),
    city                      VARCHAR(20),    -- '臺北市' | '新北市'
    district                  VARCHAR(20),
    product_name              VARCHAR(300),
    inspection_date           DATE,
    inspection_item           VARCHAR(200),
    inspection_result         VARCHAR(20),    -- '合格' | '不合格'
    violated_law_raw          TEXT,
    fine_amount               NUMERIC(12,2),
    note                      TEXT,
    violated_law_standardized TEXT,
    hazard_level              VARCHAR(20),    -- critical | high | medium | low | info
    hazard_basis              TEXT
);

CREATE INDEX IF NOT EXISTS idx_food_risk_city_hazard
  ON food_risk_inspection (city, hazard_level);
CREATE INDEX IF NOT EXISTS idx_food_risk_business
  ON food_risk_inspection (business_name, address);
CREATE INDEX IF NOT EXISTS idx_food_risk_result
  ON food_risk_inspection (inspection_result);

COMMIT;
