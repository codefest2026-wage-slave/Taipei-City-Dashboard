-- ──────────────────────────────────────────────────────────────────
-- L-04-1 就業資源可及性缺口地圖：DB_MANAGER 註冊
-- 順序：components → component_charts → component_maps → query_charts → dashboard.components 更新
-- Run: docker exec -i postgres-manager psql -U postgres -d dashboardmanager < scripts/register_employment_accessibility.sql

BEGIN;

-- ── 1. components ────────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1021, 'employment_accessibility', '雙北就業資源可及性缺口地圖')
ON CONFLICT (index) DO UPDATE SET name = EXCLUDED.name;

-- ── 2. component_charts ──────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('employment_accessibility',
   ARRAY['#16a34a','#84cc16','#fde047','#f59e0b','#ea580c','#dc2626'],
   ARRAY['EmploymentAccessibilityRanking'],
   '分')
ON CONFLICT (index) DO UPDATE SET
  color = EXCLUDED.color, types = EXCLUDED.types, unit = EXCLUDED.unit;

-- ── 3. component_maps：TPE + NTPC choropleth fill ─────────────────
DELETE FROM component_maps WHERE index IN ('employment_accessibility', 'employment_accessibility_ntpc');

INSERT INTO component_maps (id, index, title, type, source, size, icon, paint, property) VALUES
  (1021, 'employment_accessibility',
   '里級可及性缺口（臺北）', 'fill', 'geojson', NULL, NULL,
   '{"fill-color":["interpolate",["linear"],["get","gap_score"],0,"#16a34a",30,"#84cc16",60,"#fde047",80,"#f59e0b",100,"#ea580c",120,"#dc2626"],"fill-opacity":0.6,"fill-outline-color":"#1f2937"}'::json,
   NULL),
  (1022, 'employment_accessibility_ntpc',
   '里級可及性缺口（新北）', 'fill', 'geojson', NULL, NULL,
   '{"fill-color":["interpolate",["linear"],["get","gap_score"],0,"#16a34a",30,"#84cc16",60,"#fde047",80,"#f59e0b",100,"#ea580c",120,"#dc2626"],"fill-opacity":0.6,"fill-outline-color":"#1f2937"}'::json,
   NULL);

-- ── 4. query_charts ──────────────────────────────────────────────
DELETE FROM query_charts WHERE index = 'employment_accessibility';

INSERT INTO query_charts (
  index, query_type, city, query_chart, query_history, history_config,
  map_config_ids, map_filter, time_from, time_to,
  update_freq, update_freq_unit, source, short_desc, long_desc, use_case,
  links, contributors, created_at, updated_at
) VALUES (
  'employment_accessibility',
  'two_d',
  'taipei',
  $$SELECT json_build_object(
      'district', district, 'village', village,
      'dist_m', ROUND(nearest_dist_m::numeric, 0),
      'nearest_center', nearest_center,
      'in_service', in_service,
      'total_pop', total_pop,
      'midage_pop', midage_pop,
      'elder_pop', elder_pop,
      'vulnerable', vulnerable_proxy,
      'avg_disposable', avg_disposable_kntd,
      'service_radius', 1000,
      'city', '臺北', 'src_city', 'taipei'
    )::text AS x_axis, gap_score AS data
    FROM employment_accessibility_tpe
    ORDER BY gap_score DESC NULLS LAST LIMIT 30$$,
  NULL,
  '{}'::json,
  ARRAY[1021]::int[],
  NULL,
  'static', 'static',
  0, 'month',
  '勞動部勞動力發展署, 內政部戶政司, 主計總處',
  '計算每里質心距最近就業服務站距離，疊加中高齡/高齡人口比例與行政區所得，輸出可及性缺口排名供新設據點決策。',
  '台北採 1km 服務半徑（步行可及）；新北 3km（依賴交通工具）。台北版加權含 12 行政區家庭收支（每戶可支配所得倒數）；新北版僅以人口年齡層作弱勢代理（行政區所得資料未公開為已知限制）。AI 推薦每里是否新設據點與選址理由。',
  '就服中心主任每月討論轄區服務缺口時使用；社工/里幹事規劃外展訪視路線參考。',
  ARRAY['https://data.gov.tw/dataset/24562','https://data.gov.tw/dataset/77132','https://data.taipei'],
  ARRAY['tuic'],
  NOW(), NOW()
);

INSERT INTO query_charts (
  index, query_type, city, query_chart, query_history, history_config,
  map_config_ids, map_filter, time_from, time_to,
  update_freq, update_freq_unit, source, short_desc, long_desc, use_case,
  links, contributors, created_at, updated_at
) VALUES (
  'employment_accessibility',
  'two_d',
  'metrotaipei',
  $$SELECT json_build_object(
      'district', district, 'village', village,
      'dist_m', ROUND(nearest_dist_m::numeric, 0),
      'nearest_center', nearest_center,
      'in_service', in_service,
      'total_pop', total_pop,
      'midage_pop', midage_pop,
      'elder_pop', elder_pop,
      'vulnerable', vulnerable_proxy,
      'avg_disposable', avg_disposable_kntd,
      'service_radius', service_radius,
      'city', src_label, 'src_city', src_city
    )::text AS x_axis, gap_score AS data FROM (
      SELECT *, '臺北' AS src_label, 'taipei' AS src_city, 1000 AS service_radius
      FROM employment_accessibility_tpe
      UNION ALL
      SELECT *, '新北' AS src_label, 'newtaipei' AS src_city, 3000 AS service_radius
      FROM employment_accessibility_ntpc
    ) combined ORDER BY gap_score DESC NULLS LAST LIMIT 40$$,
  NULL,
  '{}'::json,
  ARRAY[1021, 1022]::int[],
  NULL,
  'static', 'static',
  0, 'month',
  '勞動部勞動力發展署, 內政部戶政司, 主計總處',
  '雙北合併視圖：橫跨兩市的可及性缺口排序，地圖呈現雙北里級熱力色階。',
  '同台北版（請見 taipei row）。',
  '跨城協作會議、跨市資源調配前瞻分析。',
  ARRAY['https://data.gov.tw/dataset/24562','https://data.gov.tw/dataset/77132','https://data.taipei'],
  ARRAY['tuic'],
  NOW(), NOW()
);

-- ── 5. 加入 labor_safety_radar dashboard（id=502） ───────────────
UPDATE dashboards
SET components = components || ARRAY[1021]::int[],
    updated_at = NOW()
WHERE id = 502 AND NOT (1021 = ANY(components));

COMMIT;

SELECT 'component' AS k, id::text AS v FROM components WHERE index='employment_accessibility'
UNION ALL SELECT 'maps_count', COUNT(*)::text FROM component_maps WHERE index LIKE 'employment_accessibility%'
UNION ALL SELECT 'query_charts_count', COUNT(*)::text FROM query_charts WHERE index='employment_accessibility'
UNION ALL SELECT 'dashboard_502_components',
  (SELECT array_to_string(components, ',') FROM dashboards WHERE id=502);
