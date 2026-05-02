-- scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql
-- Project: 食安監控系統 (Food Safety Monitor)
-- Purpose: Register dashboard 504 with 5 components (1021-1025), 4 component_maps,
--          10 query_charts (5 components × 2 cities: taipei + metrotaipei),
--          and dashboard_groups membership in the `dashboardmanager` database.
-- Down:    migrations/001_seed_dashboard.down.sql
-- Order:   components → component_charts → component_maps → query_charts
--          → dashboards → dashboard_groups
BEGIN;

-- Defensive cleanup
DELETE FROM query_charts   WHERE index LIKE 'fsm_%';
DELETE FROM component_maps WHERE index LIKE 'fsm_%';
DELETE FROM component_charts WHERE index LIKE 'fsm_%';
DELETE FROM components WHERE id BETWEEN 1021 AND 1025;
DELETE FROM dashboard_groups WHERE dashboard_id = 504;
DELETE FROM dashboards WHERE id = 504;

-- ── 1. components ──────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1021, 'fsm_school_map',         '校內食安地圖'),
  (1022, 'fsm_restaurant_map',     '校外食安地圖'),
  (1023, 'fsm_violation_rank',     '違規食品類別排行'),
  (1024, 'fsm_inspection_trend',   '稽查強度趨勢'),
  (1025, 'fsm_risk_matrix',        '風險矩陣');

-- ── 2. component_charts ────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('fsm_school_map',       ARRAY['#43A047','#E53935','#FFA000'], ARRAY['MapLegend'],         '校'),
  ('fsm_restaurant_map',   ARRAY['#1565C0','#FFA000','#E53935'], ARRAY['MapLegend'],         '家'),
  ('fsm_violation_rank',   ARRAY['#E53935','#FFA000','#43A047','#1565C0','#8E24AA','#26C6DA','#9E9E9E'], ARRAY['BarChart'], '件'),
  ('fsm_inspection_trend', ARRAY['#1565C0','#E53935'],            ARRAY['ColumnLineChart'],   '件/%'),
  ('fsm_risk_matrix',      ARRAY['#E53935','#FF9800','#1565C0','#43A047'], ARRAY['RiskMatrixChart'], '家');

-- ── 3. component_maps ──────────────────────────────────────────
INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('fsm_schools',       '學校節點',       'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","incident_status"],"red","#E53935","yellow","#FFA000","#43A047"],"circle-radius":6,"circle-opacity":0.85}'::json),
  ('fsm_supply_chain',  '供應鏈連線',     'arc',    'geojson', 'big',
    '{"arc-color":["#FFA000","#E53935"],"arc-width":2,"arc-opacity":0.6,"arc-animate":true}'::json),
  ('fsm_restaurants',   '餐廳稽查點',     'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","grade"],"優","#43A047","良","#FFA000","#E53935"],"circle-radius":4,"circle-opacity":0.8}'::json),
  ('fsm_district_heat', '行政區違規密度', 'fill',   'geojson', 'big',
    '{"fill-color":["interpolate",["linear"],["get","density"],0,"#43A047",50,"#FFA000",100,"#E53935"],"fill-opacity":0.5}'::json);

-- ── 4. query_charts (5 components × 2 cities = 10) ─────────────

-- 1021 校內食安地圖 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_school_map', 'map_legend',
  $$SELECT unnest(array['一般學校','曾發生事件','供應商有疑慮']) as name, unnest(array['circle','circle','circle']) as type$$,
  'taipei', '臺北市政府教育局（mock）',
  '臺北市國中小食安地圖 — 學校節點與供應鏈網絡。',
  '以學校節點呈現臺北市國中小，紅色標示曾發生食安事件學校，黃色標示供應商有疑慮學校。點擊節點展開供應鏈連線。',
  '家長挑學校；衛生局追蹤校園食安；研究者分析供應鏈風險。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_schools','fsm_supply_chain') ORDER BY id),
  '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1021 校內食安地圖 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_school_map', 'map_legend',
  $$SELECT unnest(array['一般學校','曾發生事件','供應商有疑慮']) as name, unnest(array['circle','circle','circle']) as type$$,
  'metrotaipei', '雙北教育局（mock）',
  '雙北國中小食安地圖 — 學校節點與供應鏈網絡。',
  '雙城國中小節點疊加，紅黃綠三色標示風險等級，點擊學校展開供應鏈連線（deck.gl ArcLayer）。',
  '家長跨城挑學校；衛生局聯合追蹤；研究者分析雙北供應鏈交織。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_schools','fsm_supply_chain') ORDER BY id),
  '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1022 校外食安地圖 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_restaurant_map', 'map_legend',
  $$SELECT unnest(array['行政區違規密度','優等餐廳','良好餐廳','需改善餐廳']) as name, unnest(array['fill','circle','circle','circle']) as type$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市校外食安地圖 — 區域熱點與餐廳稽查狀態。',
  '臺北市 12 區違規密度 choropleth + 餐廳節點（grade 三色），點擊餐廳展開稽查歷史。',
  '家長外食前查詢；衛生局調配稽查資源；店家了解所在區域風險評級。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_district_heat','fsm_restaurants') ORDER BY id),
  '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1022 校外食安地圖 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_restaurant_map', 'map_legend',
  $$SELECT unnest(array['行政區違規密度','優等餐廳','良好餐廳','需改善餐廳']) as name, unnest(array['fill','circle','circle','circle']) as type$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北校外食安地圖 — 區域熱點與餐廳稽查狀態。',
  '雙北 41 區違規密度疊合 + 雙城餐廳節點，支援區域 / 違規程度 / 時間區間 篩選。',
  '家長跨城外食；衛生局比較雙城稽查強度；研究者分析地理風險分布。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_district_heat','fsm_restaurants') ORDER BY id),
  '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1023 違規食品類別排行 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_violation_rank', 'two_d',
  $$SELECT * FROM (VALUES
    ('水產', 142), ('蔬菜', 118), ('肉類', 86), ('加工食品', 71),
    ('飲料', 49), ('米飯', 40), ('蛋類', 23), ('罐頭', 18),
    ('乳品', 11), ('麵粉', 9), ('調味品', 6), ('健康食品', 4)
  ) AS t(x_axis, data) ORDER BY data DESC$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市違規食品類別排行 Top 12（mock）。',
  '12 大食品類別違規件數累積排行，告訴父母外食時要特別注意哪些類型的食材容易出問題。',
  '家長預防性決策；店家風險自查；衛生局抽查重點規劃。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1023 違規食品類別排行 — metrotaipei (雙北合計)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_violation_rank', 'two_d',
  $$SELECT * FROM (VALUES
    ('水產', 213), ('蔬菜', 176), ('肉類', 129), ('加工食品', 104),
    ('飲料', 74), ('米飯', 60), ('蛋類', 34), ('罐頭', 27),
    ('乳品', 17), ('麵粉', 13), ('調味品', 9), ('健康食品', 5)
  ) AS t(x_axis, data) ORDER BY data DESC$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北違規食品類別排行 Top 12（mock）。',
  '12 大食品類別違規件數累積排行（雙城合計）。對齊 mockup 3 左側 Rank。',
  '家長跨城預防；店家風險自查；衛生局聯合抽查重點規劃。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1024 稽查強度趨勢 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_inspection_trend', 'time',
  $$SELECT TO_TIMESTAMP(ym, 'YYYY-MM') AS x_axis, label AS y_axis, val AS data
    FROM (VALUES
      ('2024-04','抽驗數',1812),('2024-05','抽驗數',1955),('2024-06','抽驗數',2103),
      ('2024-07','抽驗數',2240),('2024-08','抽驗數',2188),('2024-09','抽驗數',2310),
      ('2024-10','抽驗數',2055),('2024-11','抽驗數',1988),('2024-12','抽驗數',2102),
      ('2025-01','抽驗數',1860),('2025-02','抽驗數',1975),('2025-03','抽驗數',2210),
      ('2024-04','違規率',8.2),('2024-05','違規率',7.5),('2024-06','違規率',9.1),
      ('2024-07','違規率',8.7),('2024-08','違規率',9.4),('2024-09','違規率',8.0),
      ('2024-10','違規率',10.2),('2024-11','違規率',7.8),('2024-12','違規率',8.5),
      ('2025-01','違規率',9.0),('2025-02','違規率',8.3),('2025-03','違規率',7.9)
    ) AS t(ym, label, val) ORDER BY x_axis, y_axis$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市稽查強度月度趨勢 — 抽驗數 vs 違規率（mock）。',
  '雙軸折線：抽驗數（左軸件）+ 違規率（右軸 %）。呈現「效度」—— 稽查得夠多才能反映真實食安水準。',
  '衛生局自評稽查強度；研究者分析效度。',
  'static', '', 1, 'month', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1024 稽查強度趨勢 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_inspection_trend', 'time',
  $$SELECT TO_TIMESTAMP(ym, 'YYYY-MM') AS x_axis, label AS y_axis, val AS data
    FROM (VALUES
      ('2024-04','抽驗數',2812),('2024-05','抽驗數',3055),('2024-06','抽驗數',3203),
      ('2024-07','抽驗數',3340),('2024-08','抽驗數',3288),('2024-09','抽驗數',3410),
      ('2024-10','抽驗數',3155),('2024-11','抽驗數',3088),('2024-12','抽驗數',3202),
      ('2025-01','抽驗數',2960),('2025-02','抽驗數',3075),('2025-03','抽驗數',3310),
      ('2024-04','違規率',7.5),('2024-05','違規率',7.0),('2024-06','違規率',8.4),
      ('2024-07','違規率',8.1),('2024-08','違規率',8.8),('2024-09','違規率',7.6),
      ('2024-10','違規率',9.5),('2024-11','違規率',7.2),('2024-12','違規率',7.9),
      ('2025-01','違規率',8.3),('2025-02','違規率',7.7),('2025-03','違規率',7.4)
    ) AS t(ym, label, val) ORDER BY x_axis, y_axis$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北稽查強度月度趨勢 — 抽驗數 vs 違規率（mock）。',
  '雙軸折線（雙城合計）。對齊 mockup 3 上中區。',
  '雙城稽查強度比較；研究者分析雙北效度差異。',
  'static', '', 1, 'month', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1025 風險矩陣 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_risk_matrix', 'two_d',
  $$SELECT * FROM (VALUES
    ('高危險店家', 8), ('新興風險', 5), ('改善中', 11), ('優良店家', 42)
  ) AS t(x_axis, data)$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市餐廳風險四象限分布（mock）。',
  '依「一年前是否違規」× 「一年內是否違規」分四象限：高危險（兩期皆違規）、新興風險（最近才開始）、改善中（已改善）、優良。',
  '衛生局快速辨識高風險店家；CEO/CTO/政府單位視覺化掌握全局。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1025 風險矩陣 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_risk_matrix', 'two_d',
  $$SELECT * FROM (VALUES
    ('高危險店家', 12), ('新興風險', 8), ('改善中', 15), ('優良店家', 65)
  ) AS t(x_axis, data)$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北餐廳風險四象限分布（mock）。',
  '依「一年前是否違規」× 「一年內是否違規」分四象限。對齊 mockup 3 右下。',
  '雙城衛生局聯合辨識；政策制定者快速視覺化。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- ── 5. dashboards ──────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (504, 'food_safety_monitor', '食安監控系統',
   ARRAY[1021,1022,1023,1024,1025], 'health_and_safety', NOW(), NOW());

-- ── 6. dashboard_groups ────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (504, 2),
  (504, 3);

COMMIT;
