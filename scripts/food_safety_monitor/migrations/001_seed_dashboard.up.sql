-- scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql
-- Project: 食安監控系統 (Food Safety Monitor)
-- Purpose: Register dashboard 504 with 2 components (1021 校內食安地圖, 1022
--          校外食安地圖), 5 component_maps, 4 query_charts (2 components × 2
--          cities: taipei + metrotaipei), and dashboard_groups membership
--          in the `dashboardmanager` database.
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
  (1022, 'fsm_restaurant_map',     '雙北食安地圖');

-- ── 2. component_charts ────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('fsm_school_map',       ARRAY['#00E5FF','#FF1744','#FFC107'], ARRAY['FoodSafetyControls'], '校'),
  ('fsm_restaurant_map',   ARRAY['#FF1744','#FF6D00','#FFC107','#00E676','#00E5FF'], ARRAY['FoodSafetyExternalLegend'], '家');

-- ── 3. component_maps ──────────────────────────────────────────
-- Re-sync sequence before INSERT — see food_safety/002 for rationale
-- (DELETE doesn't reset sequences; collisions happen if max(id) > seq).
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
  ('fsm_supplier_dots',  '供應商中心點',   'circle', 'geojson', 'big',
    '{"circle-color":["case",["any",["==",["get","hazard_level"],"Critical"],["==",["get","hazard_level"],"High"]],"#FF1744","#00E5FF"],"circle-radius":3.5,"circle-opacity":1,"circle-stroke-width":1,"circle-stroke-color":"#0A1228","circle-stroke-opacity":0.6}'::json),
  ('fsm_restaurants',   '校外稽查業者',   'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","hazard_level"],"critical","#FF1744","high","#FF6D00","medium","#FFC107","low","#00E676","#00E5FF"],"circle-radius":["match",["get","hazard_level"],"critical",5,"high",5,"medium",4,"low",4,3],"circle-opacity":1,"circle-stroke-width":["match",["get","hazard_level"],"critical",4,"high",4,"medium",3,"low",3,2],"circle-stroke-color":["match",["get","hazard_level"],"critical","#FF1744","high","#FF6D00","medium","#FFC107","low","#00E676","#00E5FF"],"circle-stroke-opacity":0.25,"circle-blur":0.18}'::json),
  ('fsm_district_heat', '行政區違規密度', 'fill',   'geojson', 'big',
    '{"fill-color":["interpolate",["linear"],["get","density"],0,"#003344",50,"#0088AA",100,"#00E5FF"],"fill-opacity":0.35,"fill-outline-color":"#00E5FF"}'::json);

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
  ARRAY(SELECT id FROM component_maps WHERE index = 'fsm_schools'),
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
  ARRAY(SELECT id FROM component_maps WHERE index = 'fsm_schools'),
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
  '臺北市 12 區違規密度 choropleth + 校外業者節點（hazard_level 三色），點擊業者展開稽查歷史。',
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


-- ── 5. dashboards ──────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (504, 'food_safety_monitor', '食安監控系統',
   ARRAY[1021,1022], 'health_and_safety', NOW(), NOW());

-- ── 6. dashboard_groups ────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (504, 2),
  (504, 3);

COMMIT;
