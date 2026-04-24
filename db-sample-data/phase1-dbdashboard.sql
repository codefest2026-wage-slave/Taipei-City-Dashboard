-- =============================================================
-- Phase 1: DBDashboard - 照護沙漠指標 View
-- 執行對象: DBDashboard (dashboard database)
-- 說明: 整合 city_age_distribution_newtaipei（行政區人口）
--       與 long_term_nwtpe（長照機構）建立複合指標 View
-- =============================================================

-- 1-1: 確認 long_term_nwtpe 資料表存在
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'long_term_nwtpe'
-- ORDER BY ordinal_position;

-- 1-2: 確認 city_age_distribution_newtaipei 資料表欄位
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'city_age_distribution_newtaipei'
-- ORDER BY ordinal_position;

-- 1-3: 建立照護沙漠指標 View
--   city_age_distribution_newtaipei 欄位對應：
--     "年份"      → 年份
--     "區域別"    → 行政區（如：板橋區、三重區）
--     "統計類型"  → 資料類型（計 = 合計）
--     percent24   → 0-14歲人口數
--     percent26   → 15-64歲人口數
--     percent28   → 65歲以上人口數（elderly）
--   long_term_nwtpe 欄位對應：
--     zone        → 行政區（如：板橋區）
--     city        → 縣市（如：新北市）

CREATE OR REPLACE VIEW ltc_desert_index AS
WITH
-- 各行政區人口數（取最新年份，新北市各區）
pop AS (
    SELECT
        "區域別"                                        AS district,
        '新北市'                                        AS city,
        (percent24 + percent26 + percent28)             AS total_pop,
        percent28                                       AS elderly_pop,
        MAX("年份")                                     AS year
    FROM city_age_distribution_newtaipei
    WHERE "年份" = (
        SELECT MAX("年份") FROM city_age_distribution_newtaipei
    )
      AND "區域別" NOT IN ('總計', '新北市')
      AND "統計類型" = '計'
    GROUP BY "區域別", percent24, percent26, percent28
),
-- 各行政區長照機構數（新北市）
ltc AS (
    SELECT
        zone            AS district,
        COUNT(*)        AS ltc_count
    FROM long_term_nwtpe
    WHERE city = '新北市'
    GROUP BY zone
)
SELECT
    p.district,
    p.city,
    p.total_pop,
    p.elderly_pop,
    ROUND(p.elderly_pop * 100.0 / NULLIF(p.total_pop, 0), 1)                           AS aging_ratio,
    COALESCE(l.ltc_count, 0)                                                            AS ltc_count,
    -- 每萬人長照機構數（密度）
    ROUND(COALESCE(l.ltc_count, 0) * 10000.0 / NULLIF(p.total_pop, 0), 2)             AS ltc_density_per_10k,
    -- 照護沙漠分數：老化比例高但密度低 → 分數高 = 越缺乏照護資源
    ROUND(
        (p.elderly_pop * 100.0 / NULLIF(p.total_pop, 0))
        / (COALESCE(l.ltc_count, 0) * 10000.0 / NULLIF(p.total_pop, 0) + 0.1),
        2
    )                                                                                   AS desert_score
FROM pop p
LEFT JOIN ltc l ON p.district = l.district
ORDER BY desert_score DESC;

-- 驗證 View 是否正確建立
-- SELECT * FROM ltc_desert_index LIMIT 10;

-- 1-4: （可選）確認 accessible_facilities 和 aed_locations 表存在
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
--   AND table_name IN ('accessible_facilities', 'aed_locations', 'elderly_club');

-- =============================================================
-- 1-5: 建立照護沙漠指標 View — 臺北市
--   city_age_distribution_taipei 欄位對應：
--     "年份"      → 年份
--     "區域別"    → 行政區（如：大安區、信義區）
--     "統計類型"  → 資料類型（計 = 合計）
--     percent24   → 0-14歲人口數
--     percent26   → 15-64歲人口數
--     percent28   → 65歲以上人口數（elderly）
--   long_term_tpe 欄位對應：
--     zone        → 行政區（如：大安區）
--     city        → 縣市（如：臺北市）
-- =============================================================

CREATE OR REPLACE VIEW public.ltc_desert_index_tpe AS
WITH
-- 各行政區人口數（取最新年份，臺北市各區）
pop AS (
    SELECT
        "區域別"                                        AS district,
        '臺北市'                                        AS city,
        (percent24 + percent26 + percent28)             AS total_pop,
        percent28                                       AS elderly_pop
    FROM public.city_age_distribution_taipei
    WHERE "年份" = (
        SELECT MAX("年份") FROM public.city_age_distribution_taipei
    )
      AND "區域別" NOT IN ('總計', '臺北市')
      AND "統計類型" = '計'
),
-- 各行政區長照機構數（臺北市）
ltc AS (
    SELECT
        zone            AS district,
        COUNT(*)        AS ltc_count
    FROM public.long_term_tpe
    WHERE city = '臺北市'
    GROUP BY zone
)
SELECT
    p.district,
    p.city,
    p.total_pop,
    p.elderly_pop,
    ROUND(p.elderly_pop * 100.0 / NULLIF(p.total_pop, 0), 1)                           AS aging_ratio,
    COALESCE(l.ltc_count, 0)                                                            AS ltc_count,
    ROUND(COALESCE(l.ltc_count, 0) * 10000.0 / NULLIF(p.total_pop, 0), 2)             AS ltc_density_per_10k,
    ROUND(
        (p.elderly_pop * 100.0 / NULLIF(p.total_pop, 0))
        / (COALESCE(l.ltc_count, 0) * 10000.0 / NULLIF(p.total_pop, 0) + 0.1),
        2
    )                                                                                   AS desert_score
FROM pop p
LEFT JOIN ltc l ON p.district = l.district
ORDER BY desert_score DESC;

-- 驗證 View 是否正確建立
-- SELECT * FROM public.ltc_desert_index_tpe LIMIT 10;
