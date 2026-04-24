-- ============================================================
-- DB_MANAGER registration SQL for Green Mobility Dashboard
-- Dashboard: 雙北綠色出行 (green_mobility), ID=101
-- Components: 1001–1004
-- ============================================================

-- ------------------------------------------------------------
-- 1. components (id, index, name)
-- ------------------------------------------------------------
INSERT INTO public.components (id, index, name) VALUES
  (1001, 'ev_scooter_charging', '雙北電動機車充電站分布'),
  (1002, 'ev_car_charging',     '雙北電動汽車充電站分布'),
  (1003, 'bus_route_map',       '雙北公車路線地圖'),
  (1004, 'garbage_truck_route', '雙北垃圾車收運路線')
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 2. component_charts (index, color, types, unit)
-- ------------------------------------------------------------
INSERT INTO public.component_charts (index, color, types, unit) VALUES
  (
    'ev_scooter_charging',
    '{"#22c55e","#16a34a","#15803d","#166534","#4ade80","#86efac","#bbf7d0","#052e16","#dcfce7","#f0fdf4"}',
    '{"DistrictChart","BarChart"}',
    '站'
  ),
  (
    'ev_car_charging',
    '{"#06b6d4","#0891b2","#0e7490","#22d3ee","#67e8f9","#a5f3fc","#cffafe","#164e63","#083344","#ecfeff"}',
    '{"DonutChart","BarChart"}',
    '站'
  ),
  (
    'bus_route_map',
    '{"#f59e0b","#d97706","#b45309","#fbbf24","#fcd34d","#fde68a","#fef3c7","#78350f","#92400e","#fffbeb"}',
    '{"MapLegend"}',
    '條'
  ),
  (
    'garbage_truck_route',
    '{"#84cc16","#65a30d","#4d7c0f","#a3e635","#bef264","#d9f99d","#ecfccb","#365314","#3f6212","#f7fee7"}',
    '{"DistrictChart","MapLegend"}',
    '路線'
  )
ON CONFLICT (index) DO NOTHING;

-- ------------------------------------------------------------
-- 3. component_maps (id, index, title, type, source, size, icon, paint, property)
-- ------------------------------------------------------------
INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property) VALUES
  (
    1001,
    'ev_scooter_charging',
    '電動機車充電站',
    'circle',
    'geojson',
    NULL,
    NULL,
    '{"circle-color":["match",["get","city"],"taipei","#22c55e","#16a34a"],"circle-radius":6,"circle-opacity":0.8}',
    '[{"key":"name","name":"站名"},{"key":"address","name":"地址"},{"key":"district","name":"行政區"},{"key":"city","name":"城市"}]'
  ),
  (
    1002,
    'ev_car_charging',
    '電動汽車充電站',
    'circle',
    'geojson',
    NULL,
    NULL,
    '{"circle-color":["match",["get","charger_type"],"DC","#ef4444","AC+DC","#8b5cf6","#06b6d4"],"circle-radius":7,"circle-opacity":0.85}',
    '[{"key":"name","name":"站名"},{"key":"charger_type","name":"充電類型"},{"key":"city","name":"城市"}]'
  ),
  (
    1003,
    'bus_route_map',
    '公車路線',
    'line',
    'geojson',
    NULL,
    NULL,
    '{"line-color":["match",["get","city"],"taipei","#f59e0b","#d97706"],"line-width":1.5,"line-opacity":0.7}',
    '[{"key":"route_name","name":"路線名稱"},{"key":"city","name":"城市"}]'
  ),
  (
    1004,
    'garbage_truck_route',
    '垃圾車收運路線',
    'circle',
    'geojson',
    NULL,
    NULL,
    '{"circle-color":"#84cc16","circle-radius":5,"circle-opacity":0.75}',
    '[{"key":"district","name":"行政區"},{"key":"route_name","name":"路線名稱"},{"key":"weekday","name":"收運日"}]'
  )
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 4. query_charts
-- Columns: index, history_config, map_config_ids, map_filter,
--          time_from, time_to, update_freq, update_freq_unit,
--          source, short_desc, long_desc, use_case, links,
--          contributors, created_at, updated_at,
--          query_type, query_chart, query_history, city
-- ------------------------------------------------------------

-- ev_scooter_charging — taipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'ev_scooter_charging',
  NULL, '{1001}', '{}',
  'static', NULL, 0, NULL,
  '能源局',
  '顯示臺北電動機車充電站各行政區分布。',
  '顯示臺北市電動機車充電站依行政區統計之分布情形，可用於評估充電基礎設施覆蓋密度與資源配置均衡度。',
  '適用於分析臺北市電動機車充電站的空間分布，支援綠色運輸政策規劃與民眾充電需求評估。',
  '{}', '{doit}',
  NOW(), NOW(),
  'two_d',
  'SELECT district AS x_axis, COUNT(*) AS data FROM ev_scooter_charging_tpe WHERE district IS NOT NULL GROUP BY district ORDER BY data DESC',
  NULL,
  'taipei'
) ON CONFLICT DO NOTHING;

-- ev_scooter_charging — metrotaipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'ev_scooter_charging',
  NULL, '{1001}', '{}',
  'static', NULL, 0, NULL,
  '能源局',
  '顯示雙北電動機車充電站各行政區分布。',
  '顯示臺北市與新北市電動機車充電站依行政區統計之分布情形，可用於評估雙北充電基礎設施覆蓋密度與跨市資源配置均衡度。',
  '適用於分析雙北電動機車充電站的空間分布，支援跨市綠色運輸政策規劃與民眾充電需求評估。',
  '{}', '{doit,ntpc}',
  NOW(), NOW(),
  'two_d',
  'SELECT x_axis, SUM(data) AS data FROM (SELECT district AS x_axis, COUNT(*) AS data FROM ev_scooter_charging_tpe WHERE district IS NOT NULL GROUP BY district UNION ALL SELECT district AS x_axis, COUNT(*) AS data FROM ev_scooter_charging_ntpc WHERE district IS NOT NULL GROUP BY district) combined GROUP BY x_axis ORDER BY data DESC',
  NULL,
  'metrotaipei'
) ON CONFLICT DO NOTHING;

-- ev_car_charging — taipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'ev_car_charging',
  NULL, '{1002}', '{}',
  'static', NULL, 0, NULL,
  '能源局',
  '顯示臺北電動汽車充電站依充電類型分布。',
  '顯示臺北市電動汽車充電站依充電類型（AC、DC、AC+DC）統計之分布情形，可用於評估快充與慢充設施的配比現況。',
  '適用於分析臺北市電動汽車充電基礎設施組成，支援綠色運輸政策與電動車普及推廣規劃。',
  '{}', '{doit}',
  NOW(), NOW(),
  'two_d',
  'SELECT COALESCE(charger_type,''未知'') AS x_axis, COUNT(*) AS data FROM ev_car_charging_tpe GROUP BY charger_type ORDER BY data DESC',
  NULL,
  'taipei'
) ON CONFLICT DO NOTHING;

-- ev_car_charging — metrotaipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'ev_car_charging',
  NULL, '{1002}', '{}',
  'static', NULL, 0, NULL,
  '能源局',
  '顯示雙北電動汽車充電站依充電類型分布。',
  '顯示臺北市與新北市電動汽車充電站依充電類型（AC、DC、AC+DC）統計之分布情形，可用於比較雙北快充與慢充設施的配比現況。',
  '適用於分析雙北電動汽車充電基礎設施組成，支援跨市綠色運輸政策與電動車普及推廣規劃。',
  '{}', '{doit,ntpc}',
  NOW(), NOW(),
  'two_d',
  'SELECT x_axis, SUM(data) AS data FROM (SELECT COALESCE(charger_type,''未知'') AS x_axis, COUNT(*) AS data FROM ev_car_charging_tpe GROUP BY charger_type UNION ALL SELECT COALESCE(charger_type,''未知'') AS x_axis, COUNT(*) AS data FROM ev_car_charging_ntpc GROUP BY charger_type) combined GROUP BY x_axis ORDER BY data DESC',
  NULL,
  'metrotaipei'
) ON CONFLICT DO NOTHING;

-- bus_route_map — taipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'bus_route_map',
  NULL, '{1003}', '{}',
  'static', NULL, 0, NULL,
  '交通局',
  '顯示臺北公車路線總數。',
  '顯示臺北市公車路線地圖，呈現全市公車路線分布情形，可用於掌握公共運輸路網涵蓋範圍。',
  '適用於分析臺北市公車路網密度，支援公共運輸規劃與路線最佳化決策。',
  '{}', '{doit}',
  NOW(), NOW(),
  'map_legend',
  'SELECT ''臺北'' AS x_axis, COUNT(*) AS data FROM bus_route_map_tpe',
  NULL,
  'taipei'
) ON CONFLICT DO NOTHING;

-- bus_route_map — metrotaipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'bus_route_map',
  NULL, '{1003}', '{}',
  'static', NULL, 0, NULL,
  '交通局',
  '顯示雙北公車路線依城市分布。',
  '顯示臺北市與新北市公車路線地圖，比較雙北各城市公車路線數量，可用於掌握跨市公共運輸路網涵蓋範圍。',
  '適用於分析雙北公車路網密度與城市間差異，支援跨市公共運輸規劃與路線最佳化決策。',
  '{}', '{doit,ntpc}',
  NOW(), NOW(),
  'map_legend',
  'SELECT city AS x_axis, COUNT(*) AS data FROM (SELECT ''臺北'' AS city FROM bus_route_map_tpe UNION ALL SELECT ''新北'' AS city FROM bus_route_map_ntpc) combined GROUP BY city',
  NULL,
  'metrotaipei'
) ON CONFLICT DO NOTHING;

-- garbage_truck_route — taipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'garbage_truck_route',
  NULL, '{1004}', '{}',
  'static', NULL, 0, NULL,
  '環保局',
  '顯示臺北垃圾車收運路線各行政區分布。',
  '顯示臺北市垃圾車收運路線依行政區統計之分布情形，可用於了解各區垃圾收運頻率與路線配置。',
  '適用於分析臺北市垃圾收運效率與區域服務均衡度，支援環境衛生管理政策規劃。',
  '{}', '{doit}',
  NOW(), NOW(),
  'two_d',
  'SELECT COALESCE(district,''未知'') AS x_axis, COUNT(*) AS data FROM garbage_truck_route_tpe GROUP BY district ORDER BY data DESC',
  NULL,
  'taipei'
) ON CONFLICT DO NOTHING;

-- garbage_truck_route — metrotaipei
INSERT INTO public.query_charts (
  index, history_config, map_config_ids, map_filter,
  time_from, time_to, update_freq, update_freq_unit,
  source, short_desc, long_desc, use_case,
  links, contributors,
  created_at, updated_at,
  query_type, query_chart, query_history, city
) VALUES (
  'garbage_truck_route',
  NULL, '{1004}', '{}',
  'static', NULL, 0, NULL,
  '環保局',
  '顯示雙北垃圾車收運路線各行政區分布。',
  '顯示臺北市與新北市垃圾車收運路線依行政區統計之分布情形，可用於比較雙北各區垃圾收運頻率與路線配置。',
  '適用於分析雙北垃圾收運效率與跨市區域服務均衡度，支援環境衛生管理政策規劃。',
  '{}', '{doit,ntpc}',
  NOW(), NOW(),
  'two_d',
  'SELECT x_axis, SUM(data) AS data FROM (SELECT COALESCE(district,''未知'') AS x_axis, COUNT(*) AS data FROM garbage_truck_route_tpe GROUP BY district UNION ALL SELECT COALESCE(district,''未知'') AS x_axis, COUNT(*) AS data FROM garbage_truck_route_ntpc GROUP BY district) combined GROUP BY x_axis ORDER BY data DESC',
  NULL,
  'metrotaipei'
) ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- 5. dashboards (id, index, name, components, icon, updated_at, created_at)
-- ------------------------------------------------------------
INSERT INTO public.dashboards (id, index, name, components, icon, updated_at, created_at) VALUES
  (
    101,
    'green_mobility',
    '雙北綠色出行',
    '{1001,1002,1003,1004}',
    'directions_bus',
    NOW(),
    NOW()
  )
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 6. dashboard_groups — assign to metrotaipei group (id=3)
-- ------------------------------------------------------------
INSERT INTO public.dashboard_groups (dashboard_id, group_id) VALUES
  (101, 3)
ON CONFLICT DO NOTHING;
