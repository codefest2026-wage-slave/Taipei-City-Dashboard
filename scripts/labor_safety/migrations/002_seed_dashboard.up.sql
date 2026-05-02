-- scripts/labor_safety/migrations/002_seed_dashboard.up.sql
-- Project: 工作安全燈號 (Labor Safety Radar)
-- Purpose: Register dashboard 502 with 6 components (1005-1010), 12 query_charts
--          (6 components × 2 cities: taipei + metrotaipei), 2 component_maps,
--          and dashboard_groups membership in the `dashboardmanager` database.
-- down:    migrations/002_seed_dashboard.down.sql
-- Order:   components → component_charts → component_maps → query_charts
--          → dashboards → dashboard_groups
BEGIN;

-- Defensive cleanup: any prior partial seed of labor_% rows is wiped
-- before we re-insert. Safe — only labor_% indexes touched.
DELETE FROM query_charts WHERE index LIKE 'labor_%';
DELETE FROM component_maps WHERE index LIKE 'labor_disaster%';

-- ── 1. components ────────────────────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1005, 'labor_violation_search',   '雙北雇主違規快查'),
  (1006, 'labor_disaster_map',       '雙北重大職災熱點地圖'),
  (1007, 'labor_violations_monthly', '雙北月度違規趨勢'),
  (1008, 'labor_disputes_industry',  '臺北行業別勞資爭議'),
  (1009, 'labor_law_category',       '雙北違規法規分布'),
  (1010, 'labor_market_health',      '臺北勞動市場健康指標')
ON CONFLICT (index) DO NOTHING;

-- ── 2. component_charts ──────────────────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('labor_violation_search',   ARRAY['#E53935','#8E24AA','#FF6D00'], ARRAY['SearchableViolationTable'], '件'),
  ('labor_disaster_map',       ARRAY['#D50000','#FF6D00','#BF360C'], ARRAY['MapLegend'], '件'),
  ('labor_violations_monthly', ARRAY['#1565C0','#E65100','#42A5F5'], ARRAY['BarChart'], '件'),
  ('labor_disputes_industry',  ARRAY['#F57F17','#FF8F00','#FFCA28'], ARRAY['BarChart'], '件'),
  ('labor_law_category',       ARRAY['#E53935','#8E24AA','#FF6D00'], ARRAY['DonutChart'], '件'),
  ('labor_market_health',      ARRAY['#1B5E20','#2E7D32','#66BB6A'], ARRAY['BarChart'], '人')
ON CONFLICT (index) DO NOTHING;

-- ── 3. component_maps ────────────────────────────────────────────────────────
INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('labor_disasters_tpe', '臺北職災點位', 'circle', 'geojson', 'big',
   '{"circle-color":["match",["get","severity"],"fatal","#D50000","#FF6D00"],"circle-radius":7,"circle-opacity":0.85}'::json),
  ('labor_disasters_ntpc', '新北行政區職災數', 'circle', 'geojson', 'big',
   '{"circle-color":"#F4511E","circle-radius":["interpolate",["linear"],["get","incidents"],1,8,5,14,10,20,20,28],"circle-opacity":0.8}'::json);

-- ── 4. query_charts ──────────────────────────────────────────────────────────

-- 1005: 違規快查 (SearchableViolationTable) — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_violation_search', 'two_d',
  $$SELECT json_build_object('company_name', company_name, 'penalty_date', TO_CHAR(penalty_date, 'YYYY-MM-DD'), 'law_category', law_category, 'violation_content', violation_content, 'fine_amount', fine_amount, 'city', '臺北')::text AS x_axis, COALESCE(fine_amount, 0) AS data FROM labor_violations_tpe WHERE penalty_date IS NOT NULL ORDER BY penalty_date DESC$$,
  'taipei', '勞動局',
  '查詢臺北市雇主勞動違規記錄（勞基法、性平法、職安法）。',
  '整合臺北市三大勞動法規的違規事業單位公告資料，支援公司名稱模糊搜尋與多維篩選。',
  '求職者確認雇主違規記錄，或政策研究者分析違規趨勢。',
  'static', '', 1, 'day', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1005: 違規快查 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_violation_search', 'two_d',
  $$SELECT json_build_object('company_name', company_name, 'penalty_date', TO_CHAR(penalty_date, 'YYYY-MM-DD'), 'law_category', law_category, 'violation_content', violation_content, 'fine_amount', fine_amount, 'city', city)::text AS x_axis, COALESCE(fine_amount, 0) AS data FROM (SELECT company_name, penalty_date, law_category, violation_content, fine_amount, '臺北' AS city FROM labor_violations_tpe UNION ALL SELECT company_name, penalty_date, law_category, violation_content, fine_amount, '新北' AS city FROM labor_violations_ntpc) combined WHERE penalty_date IS NOT NULL ORDER BY penalty_date DESC$$,
  'metrotaipei', '勞動局',
  '查詢雙北雇主勞動違規記錄（勞基法、性平法、職安法）。',
  '整合臺北市與新北市三大勞動法規違規事業單位資料，為全台首個雙城合一可搜尋查詢工具。',
  '求職者查詢目標雇主是否有違規記錄，工會追蹤特定企業違規歷史。',
  'static', '', 1, 'day', '{}', '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- 1006: 職災地圖 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_disaster_map', 'two_d',
  'SELECT EXTRACT(YEAR FROM incident_date)::text AS x_axis, COUNT(*) AS data FROM labor_disasters_tpe GROUP BY 1 ORDER BY 1',
  'taipei', '勞動部',
  '顯示臺北市重大職災發生地點（精確 GPS 點位）。',
  '每筆職災以紅色（死亡）或橙色（僅受傷）標記於地圖，點擊查看事業單位名稱與災害類型。',
  '勞動局稽查資源配置、工安研究者分析職災空間分布。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index = 'labor_disasters_tpe'),
  '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1006: 職災地圖 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_disaster_map', 'two_d',
  'SELECT EXTRACT(YEAR FROM incident_date)::text AS x_axis, COUNT(*) AS data FROM (SELECT incident_date FROM labor_disasters_tpe UNION ALL SELECT incident_date FROM labor_disasters_ntpc) combined GROUP BY 1 ORDER BY 1',
  'metrotaipei', '勞動部',
  '顯示雙北重大職災熱點（臺北點位 + 新北行政區密度）。',
  '雙層疊合地圖：臺北市以精確 GPS 點位標示，新北市以行政區多邊形顏色深淺表示事故密度。',
  '勞動局稽查資源配置、市民了解自身工作區域的職安狀況。',
  'static', '', 1, 'year',
  ARRAY(SELECT id FROM component_maps WHERE index IN ('labor_disasters_tpe','labor_disasters_ntpc') ORDER BY id),
  '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- 1007: 月度趨勢 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_violations_monthly', 'two_d',
  'SELECT TO_CHAR(DATE_TRUNC(''month'',penalty_date),''YYYY-MM'') AS x_axis, COUNT(*) AS data FROM labor_violations_tpe WHERE penalty_date >= ''2022-01-01'' GROUP BY 1 ORDER BY 1',
  'taipei', '勞動局',
  '顯示臺北市每月違規件數趨勢。', '統計臺北市三大法規每月處分件數。', '觀察稽查力度週期性變化。',
  'static', '', 1, 'day', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1007: 月度趨勢 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_violations_monthly', 'two_d',
  'SELECT TO_CHAR(d,''YYYY-MM'') AS x_axis, SUM(cnt) AS data FROM (SELECT DATE_TRUNC(''month'',penalty_date) AS d, COUNT(*) AS cnt FROM labor_violations_tpe WHERE penalty_date >= ''2022-01-01'' GROUP BY 1 UNION ALL SELECT DATE_TRUNC(''month'',penalty_date) AS d, COUNT(*) AS cnt FROM labor_violations_ntpc WHERE penalty_date >= ''2022-01-01'' GROUP BY 1) t GROUP BY 1 ORDER BY 1',
  'metrotaipei', '勞動局',
  '顯示雙北每月違規件數趨勢。', '整合臺北市與新北市每月處分件數。', '比較雙城稽查規模。',
  'static', '', 1, 'day', '{}', '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- 1008: 行業別勞資爭議 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_disputes_industry', 'two_d',
  'SELECT industry AS x_axis, SUM(case_count) AS data FROM labor_disputes_industry_tpe WHERE year >= 2021 GROUP BY industry ORDER BY data DESC LIMIT 15',
  'taipei', '勞動局',
  '臺北市行業別勞資爭議件數排行。', '統計2021年迄今各行業勞資爭議累計件數。', '識別高爭議行業。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1008: 行業別勞資爭議 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_disputes_industry', 'two_d',
  'SELECT industry AS x_axis, SUM(case_count) AS data FROM labor_disputes_industry_tpe WHERE year >= 2021 GROUP BY industry ORDER BY data DESC LIMIT 15',
  'metrotaipei', '勞動局',
  '臺北市行業別勞資爭議件數排行（注：目前僅含臺北市資料）。', '統計2021年迄今各行業勞資爭議累計件數。', '識別高爭議行業。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1009: 法規類別圓餅 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_law_category', 'two_d',
  'SELECT law_category AS x_axis, COUNT(*) AS data FROM labor_violations_tpe GROUP BY law_category ORDER BY data DESC',
  'taipei', '勞動局',
  '臺北市違規法規類別占比。', '勞基法、性平法、職安法三大法規違規件數比例。', '了解執法重點。',
  'static', '', 1, 'day', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1009: 法規類別圓餅 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_law_category', 'two_d',
  'SELECT law_category AS x_axis, COUNT(*) AS data FROM (SELECT law_category FROM labor_violations_tpe UNION ALL SELECT law_category FROM labor_violations_ntpc) combined GROUP BY law_category ORDER BY data DESC',
  'metrotaipei', '勞動局',
  '雙北違規法規類別占比。', '整合雙北三大法規違規件數比例。', '比較雙城執法側重。',
  'static', '', 1, 'day', '{}', '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- 1010: 勞動市場健康 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_market_health', 'two_d',
  'SELECT TO_CHAR(period_date,''YYYY-MM'') AS x_axis, insured_persons AS data FROM labor_insurance_monthly_tpe WHERE period_date >= ''2020-01-01'' ORDER BY period_date',
  'taipei', '勞動局',
  '臺北市勞保投保人數月趨勢（2020起）。', '反映勞動市場景氣的投保人數月度變化。', '監測勞動市場健康度，投保人數下降預警裁員。',
  'static', '', 1, 'month', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- 1010: 勞動市場健康 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source, short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit, map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'labor_market_health', 'two_d',
  'SELECT TO_CHAR(period_date,''YYYY-MM'') AS x_axis, insured_persons AS data FROM labor_insurance_monthly_tpe WHERE period_date >= ''2020-01-01'' ORDER BY period_date',
  'metrotaipei', '勞動局',
  '臺北市勞保投保人數月趨勢（注：目前僅含臺北市資料）。', '反映勞動市場景氣的投保人數月度變化。', '監測勞動市場健康度。',
  'static', '', 1, 'month', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- ── 5. dashboards ────────────────────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (502, 'labor_safety_radar', '工作安全燈號',
   ARRAY[1005,1006,1007,1008,1009,1010], 'work', NOW(), NOW())
ON CONFLICT (index) DO NOTHING;

-- ── 6. dashboard_groups ──────────────────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (502, 2),
  (502, 3)
ON CONFLICT DO NOTHING;

COMMIT;
