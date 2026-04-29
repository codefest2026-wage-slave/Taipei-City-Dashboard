-- ──────────────────────────────────────────────────────────────────
-- L-01-1 複查優先佇列引擎：DB_MANAGER 註冊
-- ──────────────────────────────────────────────────────────────────
-- 順序：components → component_charts → component_maps → query_charts → dashboard.components 更新
-- Run: docker exec -i postgres-manager psql -U postgres -d dashboardmanager < scripts/register_recheck_priority.sql

BEGIN;

-- ──────────────────────────────────────────────
-- 1. components
-- ──────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1019, 'labor_recheck_priority', '雙北複查優先佇列引擎')
ON CONFLICT (index) DO UPDATE SET name = EXCLUDED.name;

-- ──────────────────────────────────────────────
-- 2. component_charts
-- BarChart 顯示前 20 名風險分數，TableChart 用作排名清單
-- ──────────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('labor_recheck_priority',
   ARRAY['#dc2626','#ea580c','#f59e0b','#eab308','#84cc16','#22c55e','#10b981','#06b6d4','#3b82f6','#6366f1'],
   ARRAY['BarChart'],
   '分')
ON CONFLICT (index) DO UPDATE SET
  color = EXCLUDED.color, types = EXCLUDED.types, unit = EXCLUDED.unit;

-- ──────────────────────────────────────────────
-- 3. component_maps：TPE + NTPC 兩個圖層
-- ──────────────────────────────────────────────
DELETE FROM component_maps WHERE index IN ('labor_recheck_priority', 'labor_recheck_priority_ntpc');

INSERT INTO component_maps (id, index, title, type, source, size, icon, paint, property) VALUES
  (1019, 'labor_recheck_priority',
   '高風險雇主分布（臺北）', 'circle', 'geojson', 'big', NULL,
   '{"circle-color":["interpolate",["linear"],["get","risk_score"],50,"#fde047",70,"#f97316",90,"#dc2626",110,"#7f1d1d"],"circle-radius":["interpolate",["linear"],["get","risk_score"],50,4,90,10,110,16],"circle-opacity":0.85,"circle-stroke-color":"#ffffff","circle-stroke-width":1}'::json,
   NULL),
  (1020, 'labor_recheck_priority_ntpc',
   '高風險雇主分布（新北）', 'circle', 'geojson', 'big', NULL,
   '{"circle-color":["interpolate",["linear"],["get","risk_score"],50,"#bae6fd",70,"#0ea5e9",90,"#0369a1",110,"#082f49"],"circle-radius":["interpolate",["linear"],["get","risk_score"],50,4,90,10,110,16],"circle-opacity":0.85,"circle-stroke-color":"#ffffff","circle-stroke-width":1}'::json,
   NULL);

-- ──────────────────────────────────────────────
-- 4. query_charts：taipei + metrotaipei 兩列（雙北切換邏輯核心）
-- ──────────────────────────────────────────────
DELETE FROM query_charts WHERE index = 'labor_recheck_priority';

-- TPE 排名前 20：BarChart x_axis = 公司名稱, data = risk_score
INSERT INTO query_charts (
  index, query_type, city, query_chart, query_history, history_config,
  map_config_ids, map_filter, time_from, time_to,
  update_freq, update_freq_unit, source, short_desc, long_desc, use_case,
  links, contributors, created_at, updated_at
) VALUES (
  'labor_recheck_priority',
  'two_d',
  'taipei',
  $$SELECT company_name AS x_axis, risk_score AS data
    FROM labor_recheck_priority_tpe
    ORDER BY risk_score DESC NULLS LAST LIMIT 20$$,
  NULL,
  '{}'::json,
  ARRAY[1019]::int[],
  NULL,
  'static', 'static',
  0, 'month',
  '臺北市勞動局, 新北市勞工局, 商業司, 主計總處',
  '依違規頻率、職災記錄、員工規模代理（資本額）、距上次違規天數綜合評分，協助勞檢員排定本季複查優先順序。',
  '結合 32,464 筆台北違規 + 18,350 筆新北違規 + 356 筆雙北重大職災 + 商業司公司基本資料，並透過行業別套用差異化權重（台北版聚焦工時違規、新北版聚焦製造業職安）。AI 模型根據結構化風險特徵生成「為什麼這家排第一」的解釋段落。',
  '勞檢員每季規劃複查時打開系統，直接看到風險排序前 20 家雇主清單，並依 AI 解釋判斷重點稽查項目。',
  ARRAY['https://data.taipei','https://data.ntpc.gov.tw','https://data.gcis.nat.gov.tw'],
  ARRAY['tuic'],
  NOW(), NOW()
);

-- 雙北 metrotaipei：UNION 兩市資料，map 顯示兩個圖層
INSERT INTO query_charts (
  index, query_type, city, query_chart, query_history, history_config,
  map_config_ids, map_filter, time_from, time_to,
  update_freq, update_freq_unit, source, short_desc, long_desc, use_case,
  links, contributors, created_at, updated_at
) VALUES (
  'labor_recheck_priority',
  'two_d',
  'metrotaipei',
  $$SELECT company_name AS x_axis, risk_score AS data FROM (
      SELECT company_name, risk_score, '臺北' AS src FROM labor_recheck_priority_tpe
      UNION ALL
      SELECT company_name, risk_score, '新北' AS src FROM labor_recheck_priority_ntpc
    ) combined
    ORDER BY risk_score DESC NULLS LAST LIMIT 20$$,
  NULL,
  '{}'::json,
  ARRAY[1019, 1020]::int[],
  NULL,
  'static', 'static',
  0, 'month',
  '臺北市勞動局, 新北市勞工局, 商業司, 主計總處',
  '雙北合併視圖：橫跨兩市的高風險雇主排序，地圖呈現雙北雇主密度。',
  '同台北版（請見 taipei row）。',
  '勞檢員或局長每季使用，跨市協作或全市排序時切換到此視圖。',
  ARRAY['https://data.taipei','https://data.ntpc.gov.tw','https://data.gcis.nat.gov.tw'],
  ARRAY['tuic'],
  NOW(), NOW()
);

-- ──────────────────────────────────────────────
-- 5. 加入 labor_safety_radar dashboard（id=502）
-- ──────────────────────────────────────────────
UPDATE dashboards
SET components = ARRAY[1019]::int[] || components,
    updated_at = NOW()
WHERE id = 502 AND NOT (1019 = ANY(components));

COMMIT;

-- ──────────────────────────────────────────────
-- 驗證
-- ──────────────────────────────────────────────
SELECT 'component' AS k, id::text AS v FROM components WHERE index='labor_recheck_priority'
UNION ALL SELECT 'maps_count', COUNT(*)::text FROM component_maps WHERE index LIKE 'labor_recheck_priority%'
UNION ALL SELECT 'query_charts_count', COUNT(*)::text FROM query_charts WHERE index='labor_recheck_priority'
UNION ALL SELECT 'dashboard_502_components',
  (SELECT array_to_string(components, ',') FROM dashboards WHERE id=502);
