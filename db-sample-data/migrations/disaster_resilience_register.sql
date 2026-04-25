-- Disaster Resilience Dashboard — Component Registration
-- Run against: postgres-manager → dashboardmanager DB
-- docker exec -i postgres-manager psql -U postgres -d dashboardmanager < disaster_resilience_register.sql

BEGIN;

-- ── 1. component_maps ────────────────────────────────────────────────────────

INSERT INTO component_maps (index, title, type, source, size, icon, paint, property) VALUES
(
  'disaster_shelter',
  '臺北市避難收容所',
  'circle',
  'geojson',
  'big',
  'circle',
  '{"circle-color":["match",["get","primary_type"],"flood","#3b82f6","earthquake","#f97316","mudflow","#a16207","tsunami","#7c3aed","#6b7280"],"circle-radius":["interpolate",["linear"],["coalesce",["to-number",["get","person"]],50],50,6,500,14,5000,22],"circle-opacity":0.85}',
  '[{"key":"name","name":"收容所名稱"},{"key":"person","name":"收容人數"},{"key":"district","name":"行政區"},{"key":"suit_flood","name":"水災適用"},{"key":"suit_earthquake","name":"地震適用"},{"key":"suit_weak","name":"弱勢友善"}]'
),
(
  'disaster_shelter_ntpc',
  '新北市避難收容所',
  'circle',
  'geojson',
  'big',
  'circle',
  '{"circle-color":["match",["get","primary_type"],"flood","#3b82f6","earthquake","#f97316","mudflow","#a16207","tsunami","#7c3aed","#6b7280"],"circle-radius":["interpolate",["linear"],["coalesce",["to-number",["get","person"]],50],50,6,500,14,5000,22],"circle-opacity":0.85}',
  '[{"key":"name","name":"收容所名稱"},{"key":"person","name":"收容人數"},{"key":"district","name":"行政區"},{"key":"suit_flood","name":"水災適用"},{"key":"suit_earthquake","name":"地震適用"},{"key":"suit_weak","name":"弱勢友善"}]'
),
(
  'river_water_level',
  '河川水位站',
  'circle',
  'geojson',
  NULL,
  'circle',
  '{"circle-color":["case",[">=",["get","level_out"],10],"#ef4444",[">=",["get","level_out"],6],"#f97316",[">=",["get","level_out"],3],"#f59e0b",[">=",["get","level_out"],0],"#22c55e","#94a3b8"],"circle-radius":9,"circle-opacity":0.9,"circle-stroke-width":2,"circle-stroke-color":"#1e293b"}',
  '[{"key":"name","name":"測站名稱"},{"key":"level_out","name":"水位(m)"},{"key":"alert","name":"警戒等級"},{"key":"rec_time","name":"記錄時間"}]'
),
(
  'slope_risk_tpe',
  '山坡高風險聚落',
  'circle',
  'geojson',
  NULL,
  'circle',
  '{"circle-color":["case",["<=",["get","red_threshold"],300],"#ef4444",["<=",["get","red_threshold"],400],"#f97316","#f59e0b"],"circle-radius":["case",["==",["get","risk_type"],"settlement"],["interpolate",["linear"],["coalesce",["to-number",["get","person_count"]],1],1,6,30,12,80,20],7],"circle-opacity":0.85,"circle-stroke-width":1,"circle-stroke-color":"#fff"}',
  '[{"key":"name","name":"名稱"},{"key":"district","name":"行政區"},{"key":"red_threshold","name":"紅色警戒雨量(mm)"},{"key":"person_count","name":"保全人數"},{"key":"risk_type","name":"類型"}]'
);

-- ── 1b. component_charts (defines chart type + colors shown in FE) ──────────

INSERT INTO component_charts (index, color, types, unit) VALUES
('disaster_shelter',  ARRAY['#3b82f6','#f97316','#a16207','#7c3aed'], ARRAY['BarChart','MapLegend'], '人'),
('river_water_level', ARRAY['#22c55e','#f59e0b','#f97316','#ef4444'], ARRAY['BarChart','MapLegend'], '公尺'),
('slope_risk_tpe',    ARRAY['#ef4444','#f97316','#f59e0b'],           ARRAY['BarChart','MapLegend'], '人');

-- ── 2. components ────────────────────────────────────────────────────────────

INSERT INTO components (index, name) VALUES
  ('disaster_shelter',  '雙北避難收容所地圖'),
  ('river_water_level', '臺北河川水位即時警戒'),
  ('slope_risk_tpe',    '山坡高風險聚落風險圖');

-- ── 3. query_charts — 6 rows (2 per component: one taipei + one metrotaipei)
-- Pattern: ONE two_d row per city. Map data is served from static GeoJSON (nginx),
-- NOT from query_charts map rows. Each city row queries its own data table.
-- disaster_shelter city separation:
--   taipei row → disaster_shelter.geojson (TPE only, 6052 features) + disaster_shelter_tpe table
--   metrotaipei row → disaster_shelter.geojson + disaster_shelter_ntpc.geojson (both cities)
--                     + UNION query over both tables

-- disaster_shelter: taipei view → TPE 防空避難處所清冊 (6052 records, TPE map layer only)
INSERT INTO query_charts (index, history_config, map_config_ids, map_filter, time_from, time_to, update_freq, update_freq_unit, source, short_desc, long_desc, use_case, links, contributors, created_at, updated_at, query_type, query_chart, query_history, city)
VALUES (
  'disaster_shelter', '{}'::json,
  ARRAY(SELECT id FROM component_maps WHERE index='disaster_shelter'),
  '{}'::json, 'static', NULL, 0, NULL,
  '臺北市政府',
  '顯示臺北市防空避難處所依行政區的容量分布。',
  '顯示臺北市各行政區防空避難處所的總容留人數，協助了解各區的避難承載能量。',
  '適用於災害發生前評估各區避難容量，支援疏散指揮決策。',
  '{}'::text[], ARRAY['taipei']::text[],
  NOW(), NOW(), 'two_d',
  'SELECT district AS x_axis, SUM(person) AS data FROM disaster_shelter_tpe WHERE district IS NOT NULL GROUP BY district ORDER BY data DESC',
  NULL, 'taipei'
);

-- disaster_shelter: metrotaipei view → UNION TPE + NTPC; map shows both city layers
INSERT INTO query_charts (index, history_config, map_config_ids, map_filter, time_from, time_to, update_freq, update_freq_unit, source, short_desc, long_desc, use_case, links, contributors, created_at, updated_at, query_type, query_chart, query_history, city)
VALUES (
  'disaster_shelter', '{}'::json,
  ARRAY(SELECT id FROM component_maps WHERE index IN ('disaster_shelter','disaster_shelter_ntpc') ORDER BY id),
  '{}'::json, 'static', NULL, 0, NULL,
  '臺北市政府、新北市政府消防局',
  '顯示雙北市避難收容所依行政區的容量分布。',
  '整合臺北市防空避難處所與新北市避難收容所，依行政區顯示總容納人數，協助全域評估避難承載能量。',
  '適用於災害發生前評估雙北各區避難容量，支援跨城市疏散指揮決策。',
  '{}'::text[], ARRAY['taipei','ntpc']::text[],
  NOW(), NOW(), 'two_d',
  'SELECT district AS x_axis, SUM(person) AS data FROM (SELECT district, person FROM disaster_shelter_tpe UNION ALL SELECT district, person FROM disaster_shelter_ntpc) combined WHERE district IS NOT NULL GROUP BY district ORDER BY data DESC',
  NULL, 'metrotaipei'
);

-- river_water_level: taipei view → TPE stations by water level
INSERT INTO query_charts (index, history_config, map_config_ids, map_filter, time_from, time_to, update_freq, update_freq_unit, source, short_desc, long_desc, use_case, links, contributors, created_at, updated_at, query_type, query_chart, query_history, city)
VALUES (
  'river_water_level', '{}'::json,
  ARRAY(SELECT id FROM component_maps WHERE index='river_water_level'),
  '{}'::json, 'static', NULL, 10, 'minute',
  '臺北市水利處',
  '即時顯示臺北市各河川測站當前水位。',
  '顯示臺北市31個河川水位站的即時水位數值，依水位高低排序，以顏色標示警戒等級。',
  '適用於颱風豪雨期間監測各河川水位動態，協助研判淹水風險。',
  '{}'::text[], ARRAY['tpewater']::text[],
  NOW(), NOW(), 'two_d',
  'SELECT station_name AS x_axis, ROUND(level_out::numeric, 2)::float AS data FROM river_water_level_tpe ORDER BY level_out DESC',
  NULL, 'taipei'
);

-- river_water_level: metrotaipei view → same TPE data (no NTPC river level dataset)
INSERT INTO query_charts (index, history_config, map_config_ids, map_filter, time_from, time_to, update_freq, update_freq_unit, source, short_desc, long_desc, use_case, links, contributors, created_at, updated_at, query_type, query_chart, query_history, city)
VALUES (
  'river_water_level', '{}'::json,
  ARRAY(SELECT id FROM component_maps WHERE index='river_water_level'),
  '{}'::json, 'static', NULL, 10, 'minute',
  '臺北市水利處',
  '即時顯示臺北市各河川測站當前水位。',
  '顯示臺北市31個河川水位站的即時水位數值，依水位高低排序，以顏色標示警戒等級。',
  '適用於颱風豪雨期間監測各河川水位動態，協助研判淹水風險。',
  '{}'::text[], ARRAY['tpewater']::text[],
  NOW(), NOW(), 'two_d',
  'SELECT station_name AS x_axis, ROUND(level_out::numeric, 2)::float AS data FROM river_water_level_tpe ORDER BY level_out DESC',
  NULL, 'metrotaipei'
);

-- slope_risk_tpe: taipei view → TPE settlements by person count
INSERT INTO query_charts (index, history_config, map_config_ids, map_filter, time_from, time_to, update_freq, update_freq_unit, source, short_desc, long_desc, use_case, links, contributors, created_at, updated_at, query_type, query_chart, query_history, city)
VALUES (
  'slope_risk_tpe', '{}'::json,
  ARRAY(SELECT id FROM component_maps WHERE index='slope_risk_tpe'),
  '{}'::json, 'static', NULL, 0, NULL,
  '臺北市政府工務局大地工程處',
  '顯示臺北市列管邊坡與老舊聚落保全人數分布。',
  '整合臺北市8個列管邊坡與24個老舊聚落，依保全人數排序，呈現高風險區域受威脅人口規模。',
  '適用於颱風豪雨前評估各山坡地聚落的疏散優先順序，支援指揮決策。',
  '{}'::text[], ARRAY['tpegeo']::text[],
  NOW(), NOW(), 'two_d',
  'SELECT name AS x_axis, person_count AS data FROM old_settlement_tpe WHERE person_count > 0 ORDER BY person_count DESC LIMIT 10',
  NULL, 'taipei'
);

-- slope_risk_tpe: metrotaipei view → same TPE data (no NTPC slope dataset)
INSERT INTO query_charts (index, history_config, map_config_ids, map_filter, time_from, time_to, update_freq, update_freq_unit, source, short_desc, long_desc, use_case, links, contributors, created_at, updated_at, query_type, query_chart, query_history, city)
VALUES (
  'slope_risk_tpe', '{}'::json,
  ARRAY(SELECT id FROM component_maps WHERE index='slope_risk_tpe'),
  '{}'::json, 'static', NULL, 0, NULL,
  '臺北市政府工務局大地工程處',
  '顯示臺北市列管邊坡與老舊聚落保全人數分布。',
  '整合臺北市8個列管邊坡與24個老舊聚落，依保全人數排序，呈現高風險區域受威脅人口規模。',
  '適用於颱風豪雨前評估各山坡地聚落的疏散優先順序，支援指揮決策。',
  '{}'::text[], ARRAY['tpegeo']::text[],
  NOW(), NOW(), 'two_d',
  'SELECT name AS x_axis, person_count AS data FROM old_settlement_tpe WHERE person_count > 0 ORDER BY person_count DESC LIMIT 10',
  NULL, 'metrotaipei'
);

-- ── 4. dashboards — add new component IDs ────────────────────────────────────

UPDATE dashboards
SET
  components = components || ARRAY(
    SELECT id FROM components
    WHERE index IN ('disaster_shelter', 'river_water_level', 'slope_risk_tpe')
    ORDER BY id
  ),
  updated_at = NOW()
WHERE id = 501;

COMMIT;

-- Verify
SELECT 'Registration complete' AS result;
SELECT id, index, name FROM components WHERE index IN ('disaster_shelter','river_water_level','slope_risk_tpe');
SELECT id, index, title FROM component_maps WHERE index IN ('disaster_shelter','river_water_level','slope_risk_tpe');
SELECT components FROM dashboards WHERE id = 501;
SELECT index, query_type, city, LEFT(query_chart, 60) FROM query_charts WHERE index IN ('disaster_shelter','river_water_level','slope_risk_tpe') ORDER BY index, query_type;
