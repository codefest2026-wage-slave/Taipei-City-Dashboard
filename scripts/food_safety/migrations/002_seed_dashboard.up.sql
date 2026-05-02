-- scripts/food_safety/migrations/002_seed_dashboard.up.sql
-- Project: 食安風險追蹤器 (Food Safety Radar)
-- Purpose: Register dashboard 503 with 5 food_* components (1011-1015), the
--          食安風險矩陣 component (1016, RiskQuadrantChart) merged in from
--          earlier 004 seed, PLUS the 校內食安地圖 + 校外食安地圖 components
--          (1021/1022) mirrored from scripts/food_safety_monitor/. dashboard
--          503 is the single home for all of these — there is no standalone
--          食安風險矩陣 dashboard 504 (food_safety_monitor owns 504). fsm_*
--          INSERTs are byte-identical to the 504 migration; defensive DELETE
--          makes apply order between the two dashboards irrelevant.
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
-- Also wipe fsm_% rows so re-applying after dashboard 504 (food_safety_monitor)
-- and this 503 migration produces the same end state regardless of order.
DELETE FROM query_charts     WHERE index LIKE 'fsm_%';
DELETE FROM component_maps   WHERE index LIKE 'fsm_%';
DELETE FROM component_charts WHERE index LIKE 'fsm_%';
DELETE FROM components       WHERE id BETWEEN 1021 AND 1025;

-- ── 1. components ───────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1011, 'food_poisoning_trend',   '食物中毒趨勢'),
  (1012, 'food_venue_risk',        '場所不合格件數'),
  (1013, 'food_safety_map',        '食安認證餐廳與食品工廠'),
  (1014, 'food_violation_types',   '違規原因分析'),
  (1015, 'food_testing_rate',      '年度檢驗違規件數')
ON CONFLICT (index) DO NOTHING;

-- ── 2. component_charts ─────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('food_poisoning_trend',
   ARRAY['#E53935','#F57F17'],
   ARRAY['ColumnLineChart'], '件/人'),
  ('food_venue_risk',
   ARRAY['#43A047','#1565C0','#FF9800','#FFC107','#8BC34A','#26C6DA'],
   ARRAY['ColumnChart'], '件'),
  ('food_safety_map',
   ARRAY['#43A047','#FFA000','#1565C0'],
   ARRAY['MapLegend'], '家'),
  ('food_violation_types',
   ARRAY['#E53935','#8E24AA','#FF6D00','#F57F17','#388E3C','#0288D1','#9E9E9E'],
   ARRAY['DonutChart'], '件'),
  ('food_testing_rate',
   ARRAY['#43A047','#1565C0','#FFCCBC'],
   ARRAY['ColumnChart'], '件')
ON CONFLICT (index) DO NOTHING;

-- ── 3. component_maps ──────────────────────────────────────────
INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('food_restaurant_tpe', '臺北認證餐廳', 'circle', 'geojson', 'big',
   '{"circle-color":["match",["get","grade"],"優","#43A047","#FFA000"],"circle-radius":5,"circle-opacity":0.85}'::json),
  ('food_factory_ntpc', '新北食品工廠', 'circle', 'geojson', 'big',
   '{"circle-color":"#1565C0","circle-radius":5,"circle-opacity":0.75}'::json);

-- 1011 食物中毒趨勢 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_poisoning_trend', 'time',
  $$SELECT x_axis, y_axis, ROUND(AVG(data)) AS data FROM (SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '食物中毒人數' AS y_axis, food_poisoning_cases AS data FROM food_inspection_tpe UNION ALL SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '不合格場所' AS y_axis, total_noncompliance AS data FROM food_inspection_tpe) d GROUP BY x_axis, y_axis ORDER BY x_axis$$,
  'taipei', '臺北市衛生局',
  '臺北市食物中毒人數與不合格場所趨勢（2006-2025）。',
  '食物中毒案例自169例（2023）激增至909例（2025），5.4倍增幅發出強烈警訊。雙軸設計同時呈現食物中毒人數與場所不合格件數，協助研究者分析執法力道與食安風險的關聯。',
  '衛生局追蹤食安政策成效，市民了解食安風險趨勢，學術研究分析稽查與中毒的關聯性。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1011 食物中毒趨勢 — metrotaipei
-- Data limitation: MOHW 10521-01-03 by-city xlsx provides 不合格家次 by city/year
-- but NOT 食物中毒人數 by city. Pivot: dual-city comparison uses NC counts (the
-- common metric available for both). TPE poisoning persons retained as a third
-- line for context.
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_poisoning_trend', 'time',
  $$SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '臺北市不合格場所' AS y_axis, total_noncompliance AS data FROM food_inspection_tpe UNION ALL SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '新北市不合格場所' AS y_axis, noncompliance AS data FROM food_inspection_by_city WHERE city = '新北市' AND venue = '合計' UNION ALL SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '臺北市食物中毒人數' AS y_axis, food_poisoning_cases AS data FROM food_inspection_tpe ORDER BY x_axis, y_axis$$,
  'metrotaipei', '臺北市衛生局 / 衛福部',
  '雙北食安趨勢：不合格場所家次（雙城比較）+ 臺北食物中毒人數。',
  '雙線比較雙北年度不合格家次（TPE 2006-2025；NTPC 2010-2025），輔以 TPE 食物中毒人數作為食安風險脈動。NTPC 食物中毒人數無 by-city 公開，故略。',
  '衛生局追蹤雙城食安趨勢；市民比較雙城食安風險；研究者分析查驗強度與中毒事件的相關性。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
);

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

-- 1013 食安地圖 — taipei (1 layer: TPE restaurants)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  -- map_legend query is legend-only synthesized rows; real data is served from
  -- FE/public/mapData/food_restaurant_tpe.geojson via the linked component_maps row.
  'food_safety_map', 'map_legend',
  $$SELECT unnest(array['優等認證餐廳','良好認證餐廳']) as name, unnest(array['circle','circle']) as type$$,
  'taipei', '臺北市衛生局',
  '臺北市通過衛生管理分級評核業者地圖（1,686家）。',
  '標示臺北市114年通過餐飲衛生分級評核業者，綠色為優等（優）、黃色為良好（良），協助市民查詢附近通過認證的餐廳。',
  '市民查詢附近衛生評核優良餐廳，餐飲業者了解鄰近競業的認證狀況。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index = 'food_restaurant_tpe'),
  '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1013 食安地圖 — metrotaipei (2 layers: TPE restaurants + NTPC factories)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  -- map_legend query is legend-only synthesized rows; real data is served from
  -- FE/public/mapData/food_restaurant_tpe.geojson + food_factory_ntpc.geojson.
  'food_safety_map', 'map_legend',
  $$SELECT unnest(array['台北優等餐廳','台北良好餐廳','新北食品工廠']) as name, unnest(array['circle','circle','circle']) as type$$,
  'metrotaipei', '衛生局 / 新北市經發局',
  '雙北食安地圖：臺北認證餐廳（1,686家）+ 新北食品工廠（1,230家）。',
  '雙層疊合：臺北市餐飲衛生評核業者（優/良分色）與新北市列管食品工廠，呈現雙北食安生態全貌。',
  '市民跨城查詢食安認證場所，政策研究者分析食品供應鏈地理分布。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('food_restaurant_tpe','food_factory_ntpc') ORDER BY id),
  '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- 1014 違規原因分析 — taipei (TPE 7 categories cumulative 2022-2025)
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

-- 1014 違規原因分析 — metrotaipei (combined dual-city sum per category, single donut)
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

-- ── 4b. food_safety_monitor 校內+校外 components (1021/1022) ──────
-- Mirror of scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql
-- so dashboard 503 also exposes the school + restaurant maps. Both
-- migrations write IDENTICAL fsm_* rows; the defensive DELETE above means
-- the order of apply.sh runs doesn't matter — last writer wins identically.

INSERT INTO components (id, index, name) VALUES
  (1021, 'fsm_school_map',         '校內食安地圖'),
  (1022, 'fsm_restaurant_map',     '校外食安地圖')
ON CONFLICT (index) DO NOTHING;

INSERT INTO component_charts (index, color, types, unit) VALUES
  ('fsm_school_map',       ARRAY['#00E5FF','#FF1744','#FFC107'], ARRAY['FoodSafetyControls'], '校'),
  ('fsm_restaurant_map',   ARRAY['#FF1744','#FF6D00','#FFC107','#00E676','#00E5FF'], ARRAY['FoodSafetyExternalLegend'], '家')
ON CONFLICT (index) DO NOTHING;

INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('fsm_schools',       '學校節點',       'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","recent_alert"],"red","#FF1744","#00E5FF"],"circle-radius":["match",["get","recent_alert"],"red",6,4],"circle-opacity":1,"circle-stroke-width":["match",["get","recent_alert"],"red",4,3],"circle-stroke-color":["match",["get","recent_alert"],"red","#FF1744","#00E5FF"],"circle-stroke-opacity":0.25,"circle-blur":0.18}'::json),
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
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (503, 'food_safety_radar', '食安風險追蹤器',
   ARRAY[1011,1012,1013,1014,1015,1016,1021,1022], 'restaurant', NOW(), NOW())
ON CONFLICT (index) DO UPDATE
  SET components = EXCLUDED.components,
      updated_at = NOW();

-- ── 6. dashboard_groups ──────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (503, 2),
  (503, 3)
ON CONFLICT DO NOTHING;

COMMIT;
