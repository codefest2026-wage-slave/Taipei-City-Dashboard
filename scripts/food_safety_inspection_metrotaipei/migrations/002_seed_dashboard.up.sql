-- scripts/food_safety_inspection_metrotaipei/migrations/002_seed_dashboard.up.sql
-- Project: 食安抽檢不合格率 (Food Inspection Rate Chart)
-- Purpose: Register dashboard 1200 with component 1200 (food_inspection_rate),
--          2 query_charts (taipei / metrotaipei city variants), and
--          dashboard_groups membership in the `dashboardmanager` database.
-- down:    migrations/002_seed_dashboard.down.sql
-- Order:   components → component_charts → query_charts → dashboards → dashboard_groups
--
-- NOTE on city semantics:
--   city='taipei'      → filters food_safety_inspection_metrotaipei WHERE city='臺北市'
--   city='metrotaipei' → filters food_safety_inspection_metrotaipei WHERE city='新北市'
-- The 'metrotaipei' variant intentionally shows 新北市-only data for this component
-- (the city-select button label shows "雙北" due to the existing cityManager mapping).
BEGIN;

-- Defensive cleanup
DELETE FROM query_charts  WHERE index = 'food_inspection_rate';
DELETE FROM component_charts WHERE index = 'food_inspection_rate';
DELETE FROM components    WHERE id = 1200;

-- ── 1. components ───────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1200, 'food_inspection_rate', '食安抽檢不合格率')
ON CONFLICT (index) DO NOTHING;

-- ── 2. component_charts ─────────────────────────────────────────
-- color[0] = blue (#2894FF) for 抽檢量 series
-- color[1] = orange (#FF7A00) for 不合格率 series
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('food_inspection_rate',
   ARRAY['#2894FF', '#FF7A00'],
   ARRAY['TimelineSeparateChart'], '%')
ON CONFLICT (index) DO NOTHING;

-- ── 3. query_charts ─────────────────────────────────────────────

-- 1200 食安抽檢不合格率 — taipei (臺北市)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_inspection_rate', 'time',
  $$SELECT DATE_TRUNC('month', inspection_date)::timestamp AS x_axis, '抽檢量' AS y_axis, COUNT(*)::float AS data FROM food_safety_inspection_metrotaipei WHERE city = '臺北市' AND inspection_date IS NOT NULL GROUP BY DATE_TRUNC('month', inspection_date) UNION ALL SELECT DATE_TRUNC('month', inspection_date)::timestamp AS x_axis, '不合格率' AS y_axis, ROUND(COUNT(*) FILTER (WHERE inspection_result NOT IN ('合格'))::numeric * 100.0 / NULLIF(COUNT(*), 0), 2)::float AS data FROM food_safety_inspection_metrotaipei WHERE city = '臺北市' AND inspection_date IS NOT NULL GROUP BY DATE_TRUNC('month', inspection_date) ORDER BY x_axis, y_axis$$,
  'taipei', '雙北食品查核及檢驗資訊平台',
  '臺北市每月食品稽查抽檢量與不合格率。',
  '以月為單位統計臺北市食品稽查抽檢總量（藍線）及不合格率百分比（橘線），資料來源為食品查核及檢驗資訊平台，涵蓋個人農場與商業業者。不合格率計算方式：不合格件數 ÷ 當月抽檢總數 × 100%。',
  '衛生局掌握食安稽查趨勢，追蹤各月不合格率異常，作為強化稽查頻率的決策依據。',
  'static', NULL, 1, 'month', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1200 食安抽檢不合格率 — metrotaipei (新北市)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_inspection_rate', 'time',
  $$SELECT DATE_TRUNC('month', inspection_date)::timestamp AS x_axis, '抽檢量' AS y_axis, COUNT(*)::float AS data FROM food_safety_inspection_metrotaipei WHERE city = '新北市' AND inspection_date IS NOT NULL GROUP BY DATE_TRUNC('month', inspection_date) UNION ALL SELECT DATE_TRUNC('month', inspection_date)::timestamp AS x_axis, '不合格率' AS y_axis, ROUND(COUNT(*) FILTER (WHERE inspection_result NOT IN ('合格'))::numeric * 100.0 / NULLIF(COUNT(*), 0), 2)::float AS data FROM food_safety_inspection_metrotaipei WHERE city = '新北市' AND inspection_date IS NOT NULL GROUP BY DATE_TRUNC('month', inspection_date) ORDER BY x_axis, y_axis$$,
  'metrotaipei', '雙北食品查核及檢驗資訊平台',
  '新北市每月食品稽查抽檢量與不合格率。',
  '以月為單位統計新北市食品稽查抽檢總量（藍線）及不合格率百分比（橘線），資料來源為食品查核及檢驗資訊平台，涵蓋個人農場與商業業者。不合格率計算方式：不合格件數 ÷ 當月抽檢總數 × 100%。',
  '衛生局掌握食安稽查趨勢，追蹤各月不合格率異常，作為強化稽查頻率的決策依據。',
  'static', NULL, 1, 'month', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- ── 4. dashboards ────────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (1200, 'food_inspection_rate_chart', '食安抽檢不合格率',
   ARRAY[1200], 'assignment', NOW(), NOW())
ON CONFLICT (index) DO NOTHING;

-- ── 5. dashboard_groups ──────────────────────────────────────────
-- Group 2 = taipei, Group 3 = metrotaipei
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (1200, 2),
  (1200, 3)
ON CONFLICT DO NOTHING;

COMMIT;
