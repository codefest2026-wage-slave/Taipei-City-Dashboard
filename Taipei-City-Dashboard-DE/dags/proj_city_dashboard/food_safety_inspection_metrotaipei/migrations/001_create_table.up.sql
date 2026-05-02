-- scripts/food_safety_inspection_metrotaipei/migrations/001_create_table.up.sql
-- Project: 雙北食品查核及檢驗資訊平台稽查紀錄
-- Purpose: Create food_safety_inspection_metrotaipei in the dashboard DB.
--          Idempotent (CREATE TABLE IF NOT EXISTS) and transactional.
-- down:    migrations/001_create_table.down.sql
BEGIN;

CREATE TABLE IF NOT EXISTS food_safety_inspection_metrotaipei (
    data_time                 TIMESTAMP WITH TIME ZONE,
    business_type             VARCHAR(20),     -- 個人農場 | 商業業者
    source_id                 INTEGER,         -- 原 CSV 內的項次（在來源檔內唯一）
    business_name             TEXT,            -- 業者名稱（市招）
    address                   TEXT,            -- 業者地址
    city                      VARCHAR(10),     -- 臺北市 / 新北市
    district                  VARCHAR(10),     -- 行政區
    product_name              TEXT,            -- 產品名稱
    inspection_date           DATE,            -- 稽查/檢驗日期 (民國 → 西元)
    inspection_item           TEXT,            -- 稽查/檢驗項目
    inspection_result         VARCHAR(20),     -- 合格 / 不合格 / 不符合規定 …
    violated_law_raw          TEXT,            -- 違反之食安法條及相關法 (原文)
    fine_amount               NUMERIC,         -- 裁罰金額
    note                      TEXT,            -- 備註
    violated_law_standardized TEXT,            -- 違反法條 (標準化)
    hazard_level              VARCHAR(10),     -- info / low / medium / high / critical
    hazard_basis              TEXT             -- 危害判斷依據
);

CREATE INDEX IF NOT EXISTS idx_fsim_city_district
    ON food_safety_inspection_metrotaipei (city, district);
CREATE INDEX IF NOT EXISTS idx_fsim_inspection_date
    ON food_safety_inspection_metrotaipei (inspection_date);
CREATE INDEX IF NOT EXISTS idx_fsim_hazard_level
    ON food_safety_inspection_metrotaipei (hazard_level);

COMMIT;
