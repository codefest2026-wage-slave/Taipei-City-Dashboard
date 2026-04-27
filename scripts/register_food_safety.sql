-- scripts/register_food_safety.sql
-- Register 食安風險追蹤器 dashboard (ID 503) with 5 components (1011-1015)
-- Order: components → component_charts → component_maps → query_charts → dashboards → dashboard_groups

-- Clean up any prior partial runs
DELETE FROM query_charts WHERE index LIKE 'food_%';
DELETE FROM component_maps WHERE index LIKE 'food_%';
DELETE FROM component_charts WHERE index LIKE 'food_%';
DELETE FROM components WHERE id BETWEEN 1011 AND 1015;

-- ── 1. components ─────────────────────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1011, 'food_poisoning_trend',   '食物中毒趨勢'),
  (1012, 'food_venue_risk',        '場所不合格率'),
  (1013, 'food_safety_map',        '食安認證餐廳與食品工廠'),
  (1014, 'food_violation_types',   '違規原因分析'),
  (1015, 'food_testing_rate',      '年度檢驗違規率')
ON CONFLICT (index) DO NOTHING;

-- ── 2. component_charts ───────────────────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('food_poisoning_trend',
   ARRAY['#E53935','#F57F17'],
   ARRAY['ColumnLineChart'], '件/人'),
  ('food_venue_risk',
   ARRAY['#E91E63','#FF5722','#FF9800','#FFC107','#8BC34A','#26C6DA'],
   ARRAY['BarChart'], '%'),
  ('food_safety_map',
   ARRAY['#43A047','#FFA000','#1565C0'],
   ARRAY['MapLegend'], '家'),
  ('food_violation_types',
   ARRAY['#E53935','#8E24AA','#FF6D00','#F57F17','#388E3C','#0288D1','#9E9E9E'],
   ARRAY['DonutChart'], '件'),
  ('food_testing_rate',
   ARRAY['#FF5722','#FF8A65','#FFCCBC'],
   ARRAY['BarChart'], '%')
ON CONFLICT (index) DO NOTHING;

-- ── 3. component_maps ─────────────────────────────────────────────────────────
INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('food_restaurant_tpe', '臺北認證餐廳', 'circle', 'geojson', 'big',
   '{"circle-color":["match",["get","grade"],"優","#43A047","#FFA000"],"circle-radius":5,"circle-opacity":0.85}'::json),
  ('food_factory_ntpc', '新北食品工廠', 'circle', 'geojson', 'big',
   '{"circle-color":"#1565C0","circle-radius":5,"circle-opacity":0.75}'::json);

-- ── 4. query_charts ───────────────────────────────────────────────────────────

-- 1011: 食物中毒趨勢 (ColumnLineChart, time) — taipei
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

-- 1011: 食物中毒趨勢 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_poisoning_trend', 'time',
  $$SELECT x_axis, y_axis, ROUND(AVG(data)) AS data FROM (SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '食物中毒人數' AS y_axis, food_poisoning_cases AS data FROM food_inspection_tpe UNION ALL SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '不合格場所' AS y_axis, total_noncompliance AS data FROM food_inspection_tpe) d GROUP BY x_axis, y_axis ORDER BY x_axis$$,
  'metrotaipei', '臺北市衛生局',
  '臺北市食物中毒人數與不合格場所趨勢（2006-2025）。',
  '食物中毒案例自169例（2023）激增至909例（2025），5.4倍增幅為近20年最高。',
  '衛生局追蹤食安政策成效，市民了解食安風險趨勢。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1012: 場所不合格率 (BarChart, two_d) — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_venue_risk', 'two_d',
  $$SELECT venue AS x_axis, ROUND(SUM(nc)::numeric * 100 / NULLIF(SUM(insp), 0), 1) AS data FROM (SELECT '餐飲店' AS venue, restaurant_insp AS insp, restaurant_nc AS nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '冷飲店', drink_shop_insp, drink_shop_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '飲食攤販', street_vendor_insp, street_vendor_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '傳統市場', market_insp, market_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '超級市場', supermarket_insp, supermarket_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '製造廠商', manufacturer_insp, manufacturer_nc FROM food_inspection_tpe WHERE year >= 2020) t GROUP BY venue ORDER BY data DESC$$,
  'taipei', '臺北市衛生局',
  '臺北市各類場所食安不合格率排行（2020-2025累計）。',
  '比較餐飲店、冷飲店、飲食攤販、傳統市場、超級市場、製造廠商的不合格率，識別風險最高的場所類型。',
  '市民選擇安全用餐環境，衛生局優先配置稽查資源。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1012: 場所不合格率 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_venue_risk', 'two_d',
  $$SELECT venue AS x_axis, ROUND(SUM(nc)::numeric * 100 / NULLIF(SUM(insp), 0), 1) AS data FROM (SELECT '餐飲店' AS venue, restaurant_insp AS insp, restaurant_nc AS nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '冷飲店', drink_shop_insp, drink_shop_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '飲食攤販', street_vendor_insp, street_vendor_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '傳統市場', market_insp, market_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '超級市場', supermarket_insp, supermarket_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '製造廠商', manufacturer_insp, manufacturer_nc FROM food_inspection_tpe WHERE year >= 2020) t GROUP BY venue ORDER BY data DESC$$,
  'metrotaipei', '臺北市衛生局',
  '臺北市各類場所食安不合格率排行（注：目前僅含臺北市資料）。',
  '比較各類食品場所的不合格率，識別食安風險最高的場所類型。',
  '市民選擇安全用餐環境，衛生局優先配置稽查資源。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1013: 食安地圖 (MapLegend, map_legend) — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
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

-- 1013: 食安地圖 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
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

-- 1014: 違規原因分析 (DonutChart, two_d) — taipei
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

-- 1014: 違規原因分析 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_violation_types', 'two_d',
  $$SELECT violation_type AS x_axis, SUM(total) AS data FROM (SELECT '違規標示' AS violation_type, viol_labeling AS total FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '違規廣告', viol_ad FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '食品添加物', viol_additive FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '微生物超標', viol_microbe FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '真菌毒素', viol_mycotoxin FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '化學成分', viol_chemical FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '其他原因', viol_other FROM food_testing_tpe WHERE year >= 2022) t WHERE total > 0 GROUP BY violation_type ORDER BY data DESC$$,
  'metrotaipei', '臺北市衛生局',
  '臺北市食品抽驗違規原因分類（注：目前僅含臺北市資料）。',
  '統計食品抽驗不合格件數依違規原因分析，揭示食安違規的主要型態。',
  '食品業者了解重點合規項目，消費者了解食品違規常見原因。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1015: 年度檢驗違規率 (BarChart, two_d) — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_testing_rate', 'two_d',
  $$SELECT year::text AS x_axis, violation_rate AS data FROM food_testing_tpe WHERE year >= 2015 ORDER BY year$$,
  'taipei', '臺北市衛生局',
  '臺北市食品抽驗不合格率年度趨勢（2015-2025）。',
  '年度食品抽驗不合格比率，顯示近年從0.34%（2020）攀升至0.75%（2024），揭示食安違規比例的上升趨勢。',
  '政府評估食安政策成效，消費者了解整體食品安全水準的變化。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1015: 年度檢驗違規率 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_testing_rate', 'two_d',
  $$SELECT year::text AS x_axis, violation_rate AS data FROM food_testing_tpe WHERE year >= 2015 ORDER BY year$$,
  'metrotaipei', '臺北市衛生局',
  '臺北市食品抽驗不合格率年度趨勢（注：目前僅含臺北市資料）。',
  '年度食品抽驗不合格比率趨勢，揭示近年食安違規比例的上升。',
  '政府評估食安政策成效，消費者了解整體食品安全水準變化。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- ── 5. dashboards ─────────────────────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (503, 'food_safety_radar', '食安風險追蹤器',
   ARRAY[1011,1012,1013,1014,1015], 'restaurant', NOW(), NOW())
ON CONFLICT (index) DO NOTHING;

-- ── 6. dashboard_groups ───────────────────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (503, 2),
  (503, 3)
ON CONFLICT DO NOTHING;

-- ── Verify ────────────────────────────────────────────────────────────────────
SELECT id, name FROM components WHERE id BETWEEN 1011 AND 1015;
SELECT cc.index, cc.types[1] FROM component_charts cc WHERE cc.index LIKE 'food_%';
SELECT id, index, title FROM component_maps WHERE index LIKE 'food_%';
SELECT index, city, query_type FROM query_charts WHERE index LIKE 'food_%' ORDER BY index, city;
SELECT id, name, components FROM dashboards WHERE id = 503;
