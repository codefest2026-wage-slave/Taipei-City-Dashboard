-- scripts/food_safety/migrations/002_seed_dashboard.up.sql
-- Project: 食安風險追蹤器 (Food Safety Radar)
-- Purpose: Register dashboard 503 — synced to cloud truth (2026-05-03).
--   Components in display order:
--     1012  food_venue_risk                  場所不合格件數
--     1014  food_violation_types             違規食品種類
--     1015  food_testing_rate                年度檢驗違規件數
--     1016  food_risk_matrix                 食安風險矩陣 (RiskQuadrantChart)
--     16    food_safety_repeat_offender_rank 累犯業者排行       (added on cloud)
--     14    food_safety_violation_rate_trend 年度違規率趨勢      (added on cloud)
--     1021  fsm_school_map                   校內食安地圖
--     1022  fsm_restaurant_map               雙北食安地圖
--   1011 (食物中毒趨勢) and 1013 (食安認證餐廳與食品工廠) were dropped from
--   the dashboard on cloud, so they're no longer registered here.
--   Components 14 / 16 use low IDs because they were created directly on
--   cloud; this migration adopts them so fresh-environment applies stay
--   reproducible.
-- down:    migrations/002_seed_dashboard.down.sql
-- Order:   components → component_charts → component_maps → query_charts
--          → dashboards → dashboard_groups
BEGIN;

-- Defensive cleanup: any prior partial seed of food_% rows is wiped
-- before we re-insert. Safe — only food_% indexes touched.
DELETE FROM query_charts   WHERE index LIKE 'food_%';
DELETE FROM component_maps WHERE index LIKE 'food_%';
DELETE FROM component_charts WHERE index LIKE 'food_%';
DELETE FROM components WHERE id BETWEEN 1011 AND 1016;
DELETE FROM components WHERE id IN (14, 16);
-- Also wipe fsm_% rows so re-applying after dashboard 504 (food_safety_monitor)
-- and this 503 migration produces the same end state regardless of order.
DELETE FROM query_charts     WHERE index LIKE 'fsm_%';
DELETE FROM component_maps   WHERE index LIKE 'fsm_%';
DELETE FROM component_charts WHERE index LIKE 'fsm_%';
DELETE FROM components       WHERE id BETWEEN 1021 AND 1025;

-- ── 1. components ───────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1012, 'food_venue_risk',                  '場所不合格件數'),
  (1014, 'food_violation_types',             '違規食品種類'),
  (1015, 'food_testing_rate',                '年度檢驗違規件數'),
  -- Cloud-added platform-low-id components (registered here so apply.sh on a
  -- fresh DB recreates them; cloud upserts existing rows via DO UPDATE).
  (14,   'food_safety_violation_rate_trend', '年度違規率趨勢'),
  (16,   'food_safety_repeat_offender_rank', '累犯業者排行')
ON CONFLICT (id) DO UPDATE
  SET index = EXCLUDED.index,
      name  = EXCLUDED.name;

-- ── 2. component_charts ─────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('food_venue_risk',
   ARRAY['#43A047','#1565C0','#FF9800','#FFC107','#8BC34A','#26C6DA'],
   ARRAY['ColumnChart'], '件'),
  ('food_violation_types',
   ARRAY['#E53935','#8E24AA','#FF6D00','#F57F17','#388E3C','#0288D1','#9E9E9E'],
   ARRAY['DonutChart'], '件'),
  ('food_testing_rate',
   ARRAY['#43A047','#1565C0','#FFCCBC'],
   ARRAY['ColumnChart'], '件'),
  -- Cloud-added (component IDs 14, 16). 12-color palette on the rank chart
  -- to differentiate top-12 repeat offenders.
  ('food_safety_violation_rate_trend',
   ARRAY['#F77F00','#D62828'],
   ARRAY['ColumnLineChart'], '件 / %'),
  ('food_safety_repeat_offender_rank',
   ARRAY['#D62828','#E86A2E','#F77F00','#F5AD4A','#FCBF49','#9AC17C','#4CB495','#2EC4B6','#24B0DD','#6B6B8B','#A855D8','#E170A6'],
   ARRAY['BarChart'], '次')
ON CONFLICT (index) DO NOTHING;

-- ── 3. component_maps ──────────────────────────────────────────
-- (food_restaurant_tpe / food_factory_ntpc were tied to the dropped
-- component 1013 食安地圖 — removed.)

-- 1012 場所不合格件數 — taipei (TPE per-venue NC counts, 2020-2025 cumulative)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_venue_risk', 'two_d',
  $$SELECT venue AS x_axis, SUM(nc) AS data FROM (SELECT '餐飲店' AS venue, restaurant_nc AS nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '冷飲店', drink_shop_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '飲食攤販', street_vendor_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '傳統市場', market_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '超級市場', supermarket_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '製造廠商', manufacturer_nc FROM food_inspection_tpe WHERE year >= 2020) t GROUP BY venue ORDER BY data DESC$$,
  'taipei', '臺北市衛生局',
  '臺北市各類場所不合格件數排行（2020-2025累計）。',
  '依場所別累計不合格家次（餐飲店、冷飲店、飲食攤販、傳統市場、超級市場、製造廠商），識別風險最高的場所類型。',
  '市民選擇安全用餐環境；衛生局優先配置稽查資源。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1012 場所不合格件數 — metrotaipei (three_d: year × city stacked)
-- BE three_d returns int data + categories for grouped/stacked BarChart.
-- Data limitation: MOHW xlsx provides only city-level 合計 (no per-venue × by-city),
-- so metrotaipei pivots to year-by-year NC count comparison.
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_venue_risk', 'three_d',
  $$SELECT year::text AS x_axis, city AS y_axis, noncompliance AS data FROM food_inspection_by_city WHERE city IN ('臺北市','新北市') AND year >= 2018 AND noncompliance IS NOT NULL ORDER BY year, city$$,
  'metrotaipei', '衛福部食藥署',
  '雙北年度不合格件數比較（衛福部統計）。',
  '依衛福部 10521-01-03 食品衛生管理工作-按縣市別分，雙北近年合計不合格家次並列同一年度。',
  '市民比較雙城食安水準；衛生局跨城績效評估。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
);

-- 1014 違規食品種類 — taipei (TPE 7 categories cumulative 2022-2025)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_violation_types', 'two_d',
  $$SELECT violation_type AS x_axis, SUM(total) AS data FROM (SELECT '違規標示' AS violation_type, viol_labeling AS total FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '違規廣告', viol_ad FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '食品添加物', viol_additive FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '微生物超標', viol_microbe FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '真菌毒素', viol_mycotoxin FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '化學成分', viol_chemical FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '其他原因', viol_other FROM food_testing_tpe WHERE year >= 2022) t WHERE total > 0 GROUP BY violation_type ORDER BY data DESC$$,
  'taipei', '臺北市衛生局',
  '臺北市食品抽驗違規原因分類（2022-2025累計）。',
  '統計食品抽驗不合格件數依違規原因分析，包含違規標示、食品添加物、微生物超標等七大類，揭示食安違規的主要型態。',
  '食品業者了解重點合規項目，消費者了解食品違規常見原因。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1014 違規食品種類 — metrotaipei (combined dual-city sum per category, single donut)
-- Donut: 12 categories with TPE+NTPC counts summed into one slice per category.
-- 雙北合計，相同類型不分裂。
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_violation_types', 'two_d',
  $$SELECT category AS x_axis, SUM(count) AS data FROM food_type_violations WHERE city IN ('臺北市','新北市') AND year >= 2020 GROUP BY category HAVING SUM(count) > 0 ORDER BY data DESC$$,
  'metrotaipei', '衛福部食藥署',
  '雙北食品違規原因分類（衛福部統計，雙城合計 2020-2025）。',
  '依衛福部 10521-01-03 統計，雙北食品類別（乳品/肉品/蛋品/水產/穀豆烘焙/蔬果/飲料及水/食用油脂/調味品/健康食品/複合調理/其他）違規件數加總顯示，識別整體高風險類別。',
  '食品業者了解雙北重點合規項目；研究者比較整體違規結構。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
);

-- 1015 年度檢驗違規件數 — taipei (TPE 2015-2025 total_violations count)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_testing_rate', 'two_d',
  $$SELECT year::text AS x_axis, total_violations AS data FROM food_testing_tpe WHERE year >= 2015 ORDER BY year$$,
  'taipei', '臺北市衛生局',
  '臺北市食品抽驗違規件數年度趨勢（2015-2025）。',
  '年度食品抽驗不合格件數年度分布，呈現查驗工作的違規規模與時序變化。',
  '政府評估食安政策成效，消費者了解食品安全違規動態。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1015 年度檢驗違規件數 — metrotaipei (three_d: year × city stacked)
-- BE three_d returns int data + categories so BarChart auto-renders dual-city
-- stacked per year. TPE uses total_violations (檢驗 NC); NTPC uses noncompliance
-- from MOHW by-city xlsx (查驗 NC).
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_testing_rate', 'three_d',
  $$SELECT year::text AS x_axis, '臺北市' AS y_axis, total_violations AS data FROM food_testing_tpe WHERE year >= 2018 UNION ALL SELECT year::text, '新北市', noncompliance FROM food_inspection_by_city WHERE city = '新北市' AND venue = '合計' AND year >= 2018 AND noncompliance IS NOT NULL ORDER BY x_axis, y_axis$$,
  'metrotaipei', '臺北市衛生局 / 衛福部',
  '雙北食品違規件數年度比較（2018-2025）。',
  '雙城同年度違規件數並列：TPE 為食品衛生管理查驗工作不合格件數；NTPC 為衛福部食品衛生管理工作-按縣市別分不合格家次。',
  '政府評估雙城食安政策成效；消費者比較雙北違規規模差異。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
);

-- ── 4a. 食安風險矩陣 component (1016, merged from former 004 seed) ──
-- Scatter散點圖：每筆 = 一家業者；象限色（左上紅 持續違規 / 右上黃 新興風險
-- / 左下藍 改善中 / 右下綠 優良）。原為獨立 dashboard 504，現併入 503。

INSERT INTO components (id, index, name) VALUES
  (1016, 'food_risk_matrix', '食安風險矩陣')
ON CONFLICT (index) DO NOTHING;

INSERT INTO component_charts (index, color, types, unit) VALUES
  ('food_risk_matrix',
   ARRAY['#E53935','#FBC02D','#1E88E5','#43A047'],
   ARRAY['RiskQuadrantChart'], '家')
ON CONFLICT (index) DO NOTHING;

-- 1016 食安風險矩陣 — taipei
-- X 軸 = 「歷史違規」(cutoff 2025-05-03 之前) / Y 軸 = 「近期違規」(cutoff 之後)
-- x_axis 字串編碼 "{x_value}|{biz_name}|h={n}|r={n}|gt={n}" 給 FE tooltip
-- jitter 用 hashtext(biz_key) 衍生 → 同業者每次位置一致
-- 優良象限業者抽樣 350 家避免散點過密；hash seed 含 'YYYY-MM-DD-HH'，每整點換一批
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_risk_matrix', 'two_d',
  $$WITH per_biz AS (
    SELECT
      business_name || '@' || COALESCE(address,'') AS biz_key,
      MAX(business_name) AS biz_name,
      BOOL_OR(inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_bool,
      BOOL_OR(inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_bool,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_n,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_n
    FROM food_risk_inspection
    WHERE city = '臺北市'
    GROUP BY biz_key
  ),
  violators AS (
    SELECT * FROM per_biz WHERE (h_bool OR r_bool)
  ),
  combined AS (
    SELECT * FROM violators
    UNION ALL
    SELECT * FROM (
      SELECT * FROM per_biz
      WHERE NOT h_bool AND NOT r_bool
      ORDER BY hashtext(biz_key || to_char(NOW(), 'YYYY-MM-DD-HH24'))
      LIMIT 350
    ) goods_sample
  )
  SELECT
    ROUND((
      (CASE WHEN h_bool THEN -1.2 ELSE 1.2 END)
      + ((((hashtext(biz_key) % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 2.3
    )::numeric, 3)::text
      || '|' || COALESCE(NULLIF(biz_name,''), '匿名業者')
      || '|h=' || h_n::text || '|r=' || r_n::text
      || '|gt=' || (SELECT COUNT(*) FROM per_biz WHERE NOT h_bool AND NOT r_bool)::text  AS x_axis,
    CASE
      WHEN r_bool THEN
         1.225 + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.45
      ELSE
        -1.35  + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.7
    END  AS data
  FROM combined$$,
  'taipei', '臺北市衛生局 / 食藥署食品查核及檢驗資訊平台',
  '臺北市食安風險矩陣（歷史違規 × 近期違規）。',
  '以業者為單位、依違規時間切兩段（cutoff 2025-05-03）：橫軸 = 歷史違規（左多→右少）、縱軸 = 近期違規（下少→上多）。四象限：左上紅 = 持續違規；左下藍 = 改善中；右上黃 = 新興風險；右下綠 = 優良（含合格業者抽樣 350 家）。資料來源：食藥署食品查核及檢驗資訊平台稽查紀錄。',
  '主管機關優先稽查業者識別；研究者觀察食安行為趨勢；市民了解所在區域食安狀況。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1016 食安風險矩陣 — metrotaipei (雙北合計)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_risk_matrix', 'two_d',
  $$WITH per_biz AS (
    SELECT
      business_name || '@' || COALESCE(address,'') AS biz_key,
      MAX(business_name) AS biz_name,
      BOOL_OR(inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_bool,
      BOOL_OR(inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_bool,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_n,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_n
    FROM food_risk_inspection
    WHERE city IN ('臺北市','新北市')
    GROUP BY biz_key
  ),
  violators AS (
    SELECT * FROM per_biz WHERE (h_bool OR r_bool)
  ),
  combined AS (
    SELECT * FROM violators
    UNION ALL
    SELECT * FROM (
      SELECT * FROM per_biz
      WHERE NOT h_bool AND NOT r_bool
      ORDER BY hashtext(biz_key || to_char(NOW(), 'YYYY-MM-DD-HH24'))
      LIMIT 350
    ) goods_sample
  )
  SELECT
    ROUND((
      (CASE WHEN h_bool THEN -1.2 ELSE 1.2 END)
      + ((((hashtext(biz_key) % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 2.3
    )::numeric, 3)::text
      || '|' || COALESCE(NULLIF(biz_name,''), '匿名業者')
      || '|h=' || h_n::text || '|r=' || r_n::text
      || '|gt=' || (SELECT COUNT(*) FROM per_biz WHERE NOT h_bool AND NOT r_bool)::text  AS x_axis,
    CASE
      WHEN r_bool THEN
         1.225 + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.45
      ELSE
        -1.35  + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.7
    END  AS data
  FROM combined$$,
  'metrotaipei', '雙北衛生局 / 食藥署',
  '雙北食安風險矩陣（雙城合計，歷史違規 × 近期違規）。',
  '雙城業者違規記錄合併聚合，每點 = 一家業者，cutoff 2025-05-03 切歷史/近期。象限定義同臺北版，資料範圍擴大為臺北市 + 新北市。',
  '雙城聯合稽查資源配置；跨域食安政策評估；新北市民比較雙北食安風險落差。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- ── 4ab. 14 / 16 query_charts (3 cities each: taipei, newtaipei, metrotaipei) ──
-- Note the city naming: these were authored on cloud against a different
-- naming convention (`newtaipei` instead of the `ntpc` we use for food_*).
-- Time-window is dynamic — `time_from='fiveyear_ago'` causes the BE to
-- substitute `%s` placeholders with computed inspection_date bounds.

-- 14 食品稽查年度抽檢量與違規率 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_safety_violation_rate_trend', 'time',
  $$WITH base AS (
  SELECT inspection_date, inspection_result
  FROM food_safety_inspection_metrotaipei
  WHERE city = '臺北市'
    AND inspection_date IS NOT NULL
    AND inspection_date BETWEEN '%s' AND '%s'
)
SELECT DATE_TRUNC('year', inspection_date::timestamp) AS x_axis,
  '抽檢件數' AS y_axis,
  COUNT(*)::float AS data
FROM base GROUP BY 1
UNION ALL
SELECT DATE_TRUNC('year', inspection_date::timestamp) AS x_axis,
  '違規率(%%)',
  ROUND(COUNT(*) FILTER (WHERE inspection_result != '合格')
    * 100.0 / NULLIF(COUNT(*), 0), 1)::float AS data
FROM base GROUP BY 1
ORDER BY 1, 2$$,
  'taipei', '衛生福利部食品藥物管理署 / 臺北市衛生局 [2026]',
  '臺北市食品稽查年度抽檢量與違規率',
  '以年度為單位統計臺北市食品稽查總抽檢件數與違規率。',
  '觀察臺北市食安稽查成效年度變化。',
  'fiveyear_ago', 'now', 1, 'year', '{}', '{}',
  ARRAY['https://food.fda.gov.tw/'], '{codefest2026-wage-slave}', NOW(), NOW()
);

-- 14 食品稽查年度抽檢量與違規率 — newtaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_safety_violation_rate_trend', 'time',
  $$WITH base AS (
  SELECT inspection_date, inspection_result
  FROM food_safety_inspection_metrotaipei
  WHERE city = '新北市'
    AND inspection_date IS NOT NULL
    AND inspection_date BETWEEN '%s' AND '%s'
)
SELECT DATE_TRUNC('year', inspection_date::timestamp) AS x_axis,
  '抽檢件數' AS y_axis,
  COUNT(*)::float AS data
FROM base GROUP BY 1
UNION ALL
SELECT DATE_TRUNC('year', inspection_date::timestamp) AS x_axis,
  '違規率(%%)',
  ROUND(COUNT(*) FILTER (WHERE inspection_result != '合格')
    * 100.0 / NULLIF(COUNT(*), 0), 1)::float AS data
FROM base GROUP BY 1
ORDER BY 1, 2$$,
  'newtaipei', '衛生福利部食品藥物管理署 / 新北市衛生局 [2026]',
  '新北市食品稽查年度抽檢量與違規率',
  '以年度為單位統計新北市食品稽查總抽檢件數與違規率。',
  '觀察新北市食安稽查成效年度變化。',
  'fiveyear_ago', 'now', 1, 'year', '{}', '{}',
  ARRAY['https://food.fda.gov.tw/'], '{codefest2026-wage-slave}', NOW(), NOW()
);

-- 14 食品稽查年度抽檢量與違規率 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_safety_violation_rate_trend', 'time',
  $$WITH base AS (
  SELECT inspection_date, inspection_result
  FROM food_safety_inspection_metrotaipei
  WHERE inspection_date IS NOT NULL
    AND inspection_date BETWEEN '%s' AND '%s'
)
SELECT DATE_TRUNC('year', inspection_date::timestamp) AS x_axis,
  '抽檢件數' AS y_axis,
  COUNT(*)::float AS data
FROM base GROUP BY 1
UNION ALL
SELECT DATE_TRUNC('year', inspection_date::timestamp) AS x_axis,
  '違規率(%%)',
  ROUND(COUNT(*) FILTER (WHERE inspection_result != '合格')
    * 100.0 / NULLIF(COUNT(*), 0), 1)::float AS data
FROM base GROUP BY 1
ORDER BY 1, 2$$,
  'metrotaipei', '衛生福利部食品藥物管理署 / 臺北市衛生局 / 新北市衛生局 [2026]',
  '雙北食品稽查年度抽檢量與違規率',
  '以年度為單位統計雙北食品稽查總抽檢件數（柱狀）與違規率百分比（折線）。',
  '觀察雙北食安稽查資源投入及違規率的年度變化。',
  'fiveyear_ago', 'now', 1, 'year', '{}', '{}',
  ARRAY['https://food.fda.gov.tw/'], '{codefest2026-wage-slave}', NOW(), NOW()
);

-- 16 累犯業者排行 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_safety_repeat_offender_rank', 'two_d',
  $$SELECT business_name AS x_axis, COUNT(*) AS data, MAX(fine_amount) AS tooltip
FROM food_safety_inspection_metrotaipei
WHERE city = '臺北市'
  AND inspection_result IS NOT NULL
  AND inspection_result != '合格'
  AND business_name IS NOT NULL
  AND TRIM(business_name) != ''
  AND inspection_date BETWEEN '%s' AND '%s'
GROUP BY business_name
ORDER BY data DESC
LIMIT 12$$,
  'taipei', '衛生福利部食品藥物管理署 / 臺北市衛生局 [2026]',
  '臺北市食品稽查累犯業者違規次數排行',
  '統計臺北市各業者在稽查期間累計違規次數，由高至低排序。',
  '鎖定臺北市高頻違規業者，輔助重點稽查。',
  'fiveyear_ago', 'now', 1, 'month', '{}', '{}',
  ARRAY['https://food.fda.gov.tw/'], '{codefest2026-wage-slave}', NOW(), NOW()
);

-- 16 累犯業者排行 — newtaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_safety_repeat_offender_rank', 'two_d',
  $$SELECT business_name AS x_axis, COUNT(*) AS data, MAX(fine_amount) AS tooltip
FROM food_safety_inspection_metrotaipei
WHERE city = '新北市'
  AND inspection_result IS NOT NULL
  AND inspection_result != '合格'
  AND business_name IS NOT NULL
  AND TRIM(business_name) != ''
  AND inspection_date BETWEEN '%s' AND '%s'
GROUP BY business_name
ORDER BY data DESC
LIMIT 12$$,
  'newtaipei', '衛生福利部食品藥物管理署 / 新北市衛生局 [2026]',
  '新北市食品稽查累犯業者違規次數排行',
  '統計新北市各業者在稽查期間累計違規次數，由高至低排序。',
  '鎖定新北市高頻違規業者，輔助重點稽查。',
  'fiveyear_ago', 'now', 1, 'month', '{}', '{}',
  ARRAY['https://food.fda.gov.tw/'], '{codefest2026-wage-slave}', NOW(), NOW()
);

-- 16 累犯業者排行 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_safety_repeat_offender_rank', 'two_d',
  $$SELECT business_name AS x_axis, COUNT(*) AS data, MAX(fine_amount) AS tooltip
FROM food_safety_inspection_metrotaipei
WHERE inspection_result IS NOT NULL
  AND inspection_result != '合格'
  AND business_name IS NOT NULL
  AND TRIM(business_name) != ''
  AND inspection_date BETWEEN '%s' AND '%s'
GROUP BY business_name
ORDER BY data DESC
LIMIT 12$$,
  'metrotaipei', '衛生福利部食品藥物管理署 / 臺北市衛生局 / 新北市衛生局 [2026]',
  '雙北食品稽查累犯業者違規次數排行',
  '統計雙北地區各業者在稽查期間累計違規（不合格）次數，由高至低排序，協助識別需重點關注的慣犯業者，作為稽查資源優先配置依據。',
  '用於鎖定雙北地區高頻違規業者，輔助衛生主管機關針對累犯實施重點稽查與輔導。',
  'fiveyear_ago', 'now', 1, 'month', '{}', '{}',
  ARRAY['https://food.fda.gov.tw/'], '{codefest2026-wage-slave}', NOW(), NOW()
);

-- ── 4b. food_safety_monitor 校內+校外 components (1021/1022) ──────
-- Mirror of scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql
-- so dashboard 503 also exposes the school + restaurant maps. Both
-- migrations write IDENTICAL fsm_* rows; the defensive DELETE above means
-- the order of apply.sh runs doesn't matter — last writer wins identically.

INSERT INTO components (id, index, name) VALUES
  (1021, 'fsm_school_map',         '校內食安地圖'),
  (1022, 'fsm_restaurant_map',     '雙北食安地圖')
ON CONFLICT (index) DO UPDATE
  SET name = EXCLUDED.name;

INSERT INTO component_charts (index, color, types, unit) VALUES
  ('fsm_school_map',       ARRAY['#00E5FF','#FF1744','#FFC107'], ARRAY['FoodSafetyControls'], '校'),
  ('fsm_restaurant_map',   ARRAY['#FF1744','#FF6D00','#FFC107','#00E676','#00E5FF'], ARRAY['FoodSafetyExternalLegend'], '家')
ON CONFLICT (index) DO NOTHING;

-- Re-sync component_maps.id sequence with MAX(id) before INSERT.
-- Sequences don't roll back on DELETE; if a prior platform-demo seed left
-- rows at high ids while the sequence was lower (common after pg_dump
-- restore that skipped sequence values), nextval() walks forward and
-- collides on those ids. Reset before our 6-row insert below.
SELECT setval(
  pg_get_serial_sequence('component_maps', 'id'),
  COALESCE((SELECT MAX(id) FROM component_maps), 0) + 1,
  false
);

INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('fsm_schools',       '學校節點',       'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","recent_alert"],"red","#FF1744","#0288D1"],"circle-radius":["match",["get","recent_alert"],"red",6,4],"circle-opacity":1,"circle-stroke-width":["match",["get","recent_alert"],"red",4,2.5],"circle-stroke-color":["match",["get","recent_alert"],"red","#FF1744","#4FC3F7"],"circle-stroke-opacity":["match",["get","recent_alert"],"red",0.25,0.5],"circle-blur":0.2}'::json),
  ('fsm_supply_chain',  '供應鏈連線',     'arc',    'geojson', 'big',
    '{"arc-color":["#00E5FF","#FF1744"],"arc-width":2,"arc-opacity":0.8,"arc-animate":true}'::json),
  ('fsm_suppliers',     '供應商節點',     'circle', 'geojson', 'big',
    '{"circle-color":"rgba(0,0,0,0)","circle-radius":10,"circle-opacity":1,"circle-stroke-width":3,"circle-stroke-color":["case",["any",["==",["get","hazard_level"],"Critical"],["==",["get","hazard_level"],"High"]],"#FF1744","#00E5FF"],"circle-stroke-opacity":0.95}'::json),
  ('fsm_supplier_dots', '供應商中心點',   'circle', 'geojson', 'big',
    '{"circle-color":["case",["any",["==",["get","hazard_level"],"Critical"],["==",["get","hazard_level"],"High"]],"#FF1744","#00E5FF"],"circle-radius":3.5,"circle-opacity":1,"circle-stroke-width":1,"circle-stroke-color":"#0A1228","circle-stroke-opacity":0.6}'::json),
  ('fsm_restaurants',   '校外稽查業者',   'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","hazard_level"],"critical","#FF1744","high","#FF6D00","medium","#FFC107","low","#00E676","#00E5FF"],"circle-radius":["match",["get","hazard_level"],"critical",5,"high",5,"medium",4,"low",4,3],"circle-opacity":1,"circle-stroke-width":["match",["get","hazard_level"],"critical",4,"high",4,"medium",3,"low",3,2],"circle-stroke-color":["match",["get","hazard_level"],"critical","#FF1744","high","#FF6D00","medium","#FFC107","low","#00E676","#00E5FF"],"circle-stroke-opacity":0.25,"circle-blur":0.18}'::json),
  ('fsm_district_heat', '行政區違規密度', 'fill',   'geojson', 'big',
    '{"fill-color":["interpolate",["linear"],["get","density"],0,"#003344",50,"#0088AA",100,"#00E5FF"],"fill-opacity":0.35,"fill-outline-color":"#00E5FF"}'::json);

-- 1021 校內食安地圖 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_school_map', 'map_legend',
  $$SELECT unnest(array['一般學校','曾發生事件','供應商有疑慮']) as name, unnest(array['circle','circle','circle']) as type$$,
  'taipei', '臺北市政府教育局',
  '臺北市國中小食安地圖 — 學校節點與供應鏈網絡。',
  '以學校節點呈現臺北市國中小，紅色標示連接供應商有近期不合格紀錄之學校；點擊學校展開供應鏈連線。',
  '家長挑學校；衛生局追蹤校園食安；研究者分析供應鏈風險。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index = 'fsm_schools'),
  '{}', '{}', '{doit,k12ea}', NOW(), NOW()
);

-- 1021 校內食安地圖 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_school_map', 'map_legend',
  $$SELECT unnest(array['一般學校','曾發生事件','供應商有疑慮']) as name, unnest(array['circle','circle','circle']) as type$$,
  'metrotaipei', '雙北教育局',
  '雙北國中小食安地圖 — 學校節點與供應鏈網絡。',
  '雙城國中小節點疊加，紅色標示連接供應商有近期不合格紀錄之學校；點擊節點展開供應鏈連線（deck.gl ArcLayer）。',
  '家長跨城挑學校；衛生局聯合追蹤；研究者分析雙北供應鏈交織。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index = 'fsm_schools'),
  '{}', '{}', '{doit,k12ea}', NOW(), NOW()
);

-- 1022 校外食安地圖 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_restaurant_map', 'map_legend',
  $$SELECT unnest(array['行政區違規密度','重大危害','高危害','中等危害','低危害','一般稽查']) as name, unnest(array['fill','circle','circle','circle','circle','circle']) as type$$,
  'taipei', '臺北市衛生局',
  '臺北市校外食安地圖 — 區域熱點與業者稽查歷史。',
  '臺北市 12 區違規密度 choropleth + 校外業者節點（hazard_level 5 級配色），點擊業者展開稽查歷史。',
  '家長外食前查詢；衛生局調配稽查資源；店家了解所在區域風險評級。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_district_heat','fsm_restaurants') ORDER BY id),
  '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1022 校外食安地圖 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_restaurant_map', 'map_legend',
  $$SELECT unnest(array['行政區違規密度','重大危害','高危害','中等危害','低危害','一般稽查']) as name, unnest(array['fill','circle','circle','circle','circle','circle']) as type$$,
  'metrotaipei', '雙北衛生局',
  '雙北校外食安地圖 — 區域熱點與業者稽查歷史。',
  '雙北 41 區違規密度疊合 + 雙城業者節點，依 hazard_level 5 級配色，支援違規程度 / 時間區間 篩選。',
  '家長跨城外食；衛生局比較雙城稽查強度；研究者分析地理風險分布。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_district_heat','fsm_restaurants') ORDER BY id),
  '{}', '{}', '{doit}', NOW(), NOW()
);

-- ── 5. dashboards ────────────────────────────────────────────────
-- Display order matches cloud truth (2026-05-03):
--   1012, 1014, 1015, 1016, 16, 14, 1021, 1022
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (503, 'food_safety_radar', '食安風險追蹤器',
   ARRAY[1012,1014,1015,1016,16,14,1021,1022], 'restaurant', NOW(), NOW())
ON CONFLICT (index) DO UPDATE
  SET components = EXCLUDED.components,
      updated_at = NOW();

-- ── 6. dashboard_groups ──────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (503, 2),
  (503, 3)
ON CONFLICT DO NOTHING;

COMMIT;
