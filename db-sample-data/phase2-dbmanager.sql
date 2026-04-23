-- =============================================================
-- Phase 2: DBManager - 新組件註冊
-- 執行對象: DBManager (dashboardmanager database)
-- 說明: 新增 3 個照護沙漠相關組件，並建立/更新雙北高齡照護儀表板
--
-- Schema 說明:
--   components(id, index, name)
--   query_charts(index, history_config, map_config_ids, map_filter,
--     time_from, time_to, update_freq, update_freq_unit, source,
--     short_desc, long_desc, use_case, links, contributors,
--     created_at, updated_at, query_type, query_chart, query_history, city)
--   component_charts(index, color, types, unit)
--   component_maps(id, index, title, type, source, size, icon, paint, property)
--   dashboards(id, index, name, components, icon, updated_at, created_at)
-- =============================================================

-- =============================================================
-- 任務 2-1: 照護沙漠熱力圖 (ltc_desert_map)
-- =============================================================

INSERT INTO components (index, name)
VALUES ('ltc_desert_map', '照護沙漠熱力圖')
ON CONFLICT (index) DO NOTHING;

INSERT INTO query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
) VALUES (
    'ltc_desert_map',
    NULL, '{}', '{}',
    'static', NULL,
    1, 'day',
    '臺北市政府資料開放平台 [2026] / 新北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '雙北各行政區照護沙漠指數',
    '整合各行政區老化比例與長照機構密度，計算「照護沙漠指數」。指數越高代表高齡人口多但長照資源相對不足，需要優先投入資源。',
    '識別需優先增設長照資源的行政區，支援長照政策資源配置決策。',
    ARRAY['https://data.ntpc.gov.tw/', 'https://data.taipei/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'two_d',
    'SELECT district AS x_axis, desert_score AS data
     FROM ltc_desert_index
     ORDER BY desert_score DESC
     LIMIT 30',
    NULL,
    'metrotaipei'
)
ON CONFLICT (index) DO UPDATE SET updated_at = NOW();

INSERT INTO component_charts (index, color, types, unit)
VALUES (
    'ltc_desert_map',
    ARRAY['#D62828', '#F77F00', '#FCBF49', '#EAE2B7', '#2EC4B6'],
    ARRAY['BarChart'],
    '分'
)
ON CONFLICT (index) DO NOTHING;

INSERT INTO component_maps (index, title, type, source, size, icon, paint, property)
VALUES (
    'ltc_desert_map',
    '照護沙漠指數（行政區）',
    'fill',
    'ltc_desert_index',
    'small',
    'elderly',
    '{"fill-color": ["interpolate", ["linear"], ["get", "desert_score"], 0, "#EAE2B7", 50, "#F77F00", 100, "#D62828"], "fill-opacity": 0.7}'::json,
    NULL
)
ON CONFLICT (index) DO NOTHING;

-- =============================================================
-- 任務 2-2: 長照資源密度分析 (ltc_resource_density)
-- =============================================================

INSERT INTO components (index, name)
VALUES ('ltc_resource_density', '長照資源密度分析')
ON CONFLICT (index) DO NOTHING;

INSERT INTO query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
) VALUES (
    'ltc_resource_density',
    NULL, '{}', '{}',
    'static', NULL,
    1, 'day',
    '新北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '雙北長照機構服務項目分布',
    '依行政區與服務項目（居家服務/日間照顧/住宿式機構）統計長照機構數量，呈現服務類型的地區差異。',
    '評估各行政區長照服務類型是否均衡，識別特定服務類型的供給缺口。',
    ARRAY['https://data.ntpc.gov.tw/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'three_d',
    'SELECT zone AS y_axis, service_item AS x_axis, COUNT(*) AS data
     FROM long_term_nwtpe
     GROUP BY zone, service_item
     ORDER BY zone, service_item',
    NULL,
    'metrotaipei'
)
ON CONFLICT (index) DO UPDATE SET updated_at = NOW();

INSERT INTO component_charts (index, color, types, unit)
VALUES (
    'ltc_resource_density',
    ARRAY['#2E86AB', '#A23B72', '#F18F01', '#C73E1D'],
    ARRAY['BarChart', 'ColumnChart'],
    '間'
)
ON CONFLICT (index) DO NOTHING;

-- =============================================================
-- 任務 2-3: 高齡人口分布 (aging_population_dist)
-- =============================================================

INSERT INTO components (index, name)
VALUES ('aging_population_dist', '高齡人口分布')
ON CONFLICT (index) DO NOTHING;

INSERT INTO query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
) VALUES (
    'aging_population_dist',
    NULL, '{}', '{}',
    'static', NULL,
    1, 'month',
    '臺北市政府資料開放平台 [2026] / 新北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '雙北各行政區高齡化比例',
    '呈現雙北各行政區 65 歲以上人口佔總人口比例，反映各地區高齡化程度差異。',
    '作為長照資源配置的需求端指標，搭配長照機構密度共同分析。',
    ARRAY['https://data.taipei/', 'https://data.ntpc.gov.tw/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'two_d',
    'SELECT district AS x_axis, ROUND(aging_ratio, 1) AS data
     FROM ltc_desert_index
     ORDER BY aging_ratio DESC',
    NULL,
    'metrotaipei'
)
ON CONFLICT (index) DO UPDATE SET updated_at = NOW();

INSERT INTO component_charts (index, color, types, unit)
VALUES (
    'aging_population_dist',
    ARRAY['#E63946', '#457B9D'],
    ARRAY['BarChart'],
    '%'
)
ON CONFLICT (index) DO NOTHING;

-- =============================================================
-- 任務 2-4: 建立「雙北高齡照護資源」儀表板
-- 注意：components 欄位是 integer array（component ID），
--       需先查詢新組件的 ID
-- =============================================================

-- Step 1: 查詢既有組件 ID（已知：ltc_care_newtpe 在 dashboard 355 有 {214,215,216,218}）
-- Step 2: 查詢新建組件 ID
-- SELECT id, index FROM components
-- WHERE index IN ('ltc_desert_map', 'ltc_resource_density', 'aging_population_dist');

-- Step 3: 建立新儀表板（用 DO block 自動取得新組件 ID）
DO $$
DECLARE
    v_desert_id    integer;
    v_density_id   integer;
    v_aging_id     integer;
BEGIN
    -- 取得新組件 ID
    SELECT id INTO v_desert_id  FROM components WHERE index = 'ltc_desert_map';
    SELECT id INTO v_density_id FROM components WHERE index = 'ltc_resource_density';
    SELECT id INTO v_aging_id   FROM components WHERE index = 'aging_population_dist';

    -- 建立儀表板（若已存在則 skip）
    INSERT INTO dashboards (index, name, components, icon, updated_at, created_at)
    VALUES (
        'aging_care_metrotaipei',
        '雙北高齡照護資源',
        ARRAY[218, 214, v_desert_id, v_density_id, v_aging_id, 215],
        'elderly',
        NOW(), NOW()
    )
    ON CONFLICT (index) DO UPDATE
        SET components = ARRAY[218, 214, v_desert_id, v_density_id, v_aging_id, 215],
            updated_at = NOW();
END $$;

-- =============================================================
-- 驗證查詢
-- =============================================================
-- SELECT c.id, c.index, c.name FROM components c
-- WHERE c.index IN ('ltc_desert_map','ltc_resource_density','aging_population_dist');

-- SELECT index, short_desc, query_type, city FROM query_charts
-- WHERE index IN ('ltc_desert_map','ltc_resource_density','aging_population_dist');

-- SELECT * FROM dashboards WHERE index = 'aging_care_metrotaipei';
