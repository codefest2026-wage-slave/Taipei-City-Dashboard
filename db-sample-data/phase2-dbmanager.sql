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

-- metrotaipei（新北市資料）
INSERT INTO query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
) VALUES (
    'ltc_desert_map',
    NULL, ARRAY[301], '{}',
    'static', NULL,
    1, 'day',
    '新北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '新北市各行政區照護沙漠指數',
    '整合新北市各行政區老化比例與長照機構密度，計算「照護沙漠指數」。指數越高代表高齡人口多但長照資源相對不足，需要優先投入資源。',
    '識別需優先增設長照資源的行政區，支援長照政策資源配置決策。',
    ARRAY['https://data.ntpc.gov.tw/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'two_d',
    'SELECT district AS x_axis, desert_score AS data
     FROM ltc_desert_index
     WHERE city LIKE ''%新北%''
     ORDER BY desert_score DESC
     LIMIT 30',
    NULL,
    'metrotaipei'
)
ON CONFLICT (index, city) DO UPDATE SET updated_at = NOW();

-- taipei（臺北市資料）
INSERT INTO query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
) VALUES (
    'ltc_desert_map',
    NULL, ARRAY[302], '{}',
    'static', NULL,
    1, 'day',
    '臺北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '臺北市各行政區照護沙漠指數',
    '整合臺北市各行政區老化比例與長照機構密度，計算「照護沙漠指數」。指數越高代表高齡人口多但長照資源相對不足，需要優先投入資源。',
    '識別需優先增設長照資源的行政區，支援長照政策資源配置決策。',
    ARRAY['https://data.taipei/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'two_d',
    'SELECT district AS x_axis, desert_score AS data FROM public.ltc_desert_index_tpe ORDER BY desert_score DESC LIMIT 30',
    NULL,
    'taipei'
)
ON CONFLICT (index, city) DO UPDATE SET updated_at = NOW();

INSERT INTO component_charts (index, color, types, unit)
VALUES (
    'ltc_desert_map',
    ARRAY['#D62828', '#F77F00', '#FCBF49', '#EAE2B7', '#2EC4B6'],
    ARRAY['BarChart'],
    '分'
)
ON CONFLICT (index) DO NOTHING;

-- component_maps 用 explicit ID（301=新北, 302=臺北），ON CONFLICT (id) 防止重複
INSERT INTO component_maps (id, index, title, type, source, size, icon, paint, property)
VALUES (
    301, 'ltc_desert_map', '照護沙漠指數（新北市）', 'fill',
    'ltc_desert_index', 'small', 'elderly',
    '{"fill-color":["interpolate",["linear"],["get","desert_score"],0,"#EAE2B7",50,"#F77F00",100,"#D62828"],"fill-opacity":0.7}'::json,
    '[{"key":"district","name":"行政區"},{"key":"aging_ratio","name":"老化比率(%)"},{"key":"ltc_count","name":"長照機構數"},{"key":"desert_score","name":"沙漠指數"}]'::json
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO component_maps (id, index, title, type, source, size, icon, paint, property)
VALUES (
    302, 'ltc_desert_map', '照護沙漠指數（臺北市）', 'fill',
    'ltc_desert_index_tpe', 'small', 'elderly',
    '{"fill-color":["interpolate",["linear"],["get","desert_score"],0,"#EAE2B7",50,"#F77F00",100,"#D62828"],"fill-opacity":0.7}'::json,
    '[{"key":"district","name":"行政區"},{"key":"aging_ratio","name":"老化比率(%)"},{"key":"ltc_count","name":"長照機構數"},{"key":"desert_score","name":"沙漠指數"}]'::json
)
ON CONFLICT (id) DO NOTHING;

-- =============================================================
-- 任務 2-2: 長照資源密度分析 (ltc_resource_density)
-- =============================================================

INSERT INTO components (index, name)
VALUES ('ltc_resource_density', '長照資源密度分析')
ON CONFLICT (index) DO NOTHING;

-- metrotaipei（新北市資料）
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
    '新北市長照機構服務項目分布',
    '依行政區與服務項目（居家服務/日間照顧/住宿式機構）統計新北市長照機構數量，呈現服務類型的地區差異。',
    '評估新北市各行政區長照服務類型是否均衡，識別特定服務類型的供給缺口。',
    ARRAY['https://data.ntpc.gov.tw/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'three_d',
    'SELECT zone AS y_axis, service_item AS x_axis, COUNT(*) AS data
     FROM long_term_nwtpe
     WHERE zone IS NOT NULL AND service_item IS NOT NULL
     GROUP BY zone, service_item
     ORDER BY zone, service_item',
    NULL,
    'metrotaipei'
)
ON CONFLICT (index, city) DO UPDATE SET updated_at = NOW();

-- taipei（臺北市資料）
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
    '臺北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '臺北市長照機構服務項目分布',
    '依行政區與服務項目（私立住宿/公立住宿）統計臺北市長照機構數量，呈現服務類型的地區差異。',
    '評估臺北市各行政區長照服務類型是否均衡，識別特定服務類型的供給缺口。',
    ARRAY['https://data.taipei/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'three_d',
    'SELECT zone AS y_axis, property AS x_axis, COUNT(*) AS data
     FROM long_term_tpe
     WHERE zone IS NOT NULL AND property IS NOT NULL
     GROUP BY zone, property
     ORDER BY zone, property',
    NULL,
    'taipei'
)
ON CONFLICT (index, city) DO UPDATE SET updated_at = NOW();

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

-- metrotaipei（新北市資料）
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
    '新北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '新北市各行政區高齡化比例',
    '呈現新北市各行政區 65 歲以上人口佔總人口比例，反映各地區高齡化程度差異。',
    '作為長照資源配置的需求端指標，搭配長照機構密度共同分析。',
    ARRAY['https://data.ntpc.gov.tw/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'two_d',
    'SELECT district AS x_axis, ROUND(aging_ratio::numeric, 1) AS data
     FROM ltc_desert_index
     WHERE city LIKE ''%新北%''
     ORDER BY aging_ratio DESC',
    NULL,
    'metrotaipei'
)
ON CONFLICT (index, city) DO UPDATE SET updated_at = NOW();

-- taipei（臺北市資料）
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
    '臺北市政府資料開放平台 [2026] 依政府資料開放授權條款 v1.0 釋出',
    '臺北市各行政區高齡化比例',
    '呈現臺北市各行政區 65 歲以上人口佔總人口比例，反映各地區高齡化程度差異。',
    '作為長照資源配置的需求端指標，搭配長照機構密度共同分析。',
    ARRAY['https://data.taipei/'],
    ARRAY['codefest2026-wage-slave'],
    NOW(), NOW(),
    'two_d',
    'SELECT district AS x_axis, ROUND(aging_ratio, 1) AS data FROM public.ltc_desert_index_tpe ORDER BY aging_ratio DESC',
    NULL,
    'taipei'
)
ON CONFLICT (index, city) DO UPDATE SET updated_at = NOW();

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

-- Step 1: 查詢新建組件 ID（供參考確認）
-- SELECT id, index FROM components
-- WHERE index IN ('ltc_desert_map', 'ltc_resource_density', 'aging_population_dist');

-- Step 2: 建立新儀表板（用 DO block 自動取得新組件 ID），並加入 dashboard_groups 側邊欄群組
DO $$
DECLARE
    v_desert_id    integer;
    v_density_id   integer;
    v_aging_id     integer;
    v_dashboard_id integer;
BEGIN
    -- 取得新組件 ID（Phase 2 任務 2-1~2-3 INSERT 後才有值）
    SELECT id INTO v_desert_id  FROM components WHERE index = 'ltc_desert_map';
    SELECT id INTO v_density_id FROM components WHERE index = 'ltc_resource_density';
    SELECT id INTO v_aging_id   FROM components WHERE index = 'aging_population_dist';

    -- 建立儀表板（若已存在則更新 components 清單）
    -- components 陣列排列：原創組件優先，既有輔助組件在後
    -- 已知既有組件 ID：218=aging_kpi, 214=dependency_aging(扶養比)
    INSERT INTO dashboards (index, name, components, icon, updated_at, created_at)
    VALUES (
        'aging_care_metrotaipei',
        '雙北高齡照護資源',
        ARRAY[v_desert_id, v_density_id, v_aging_id, 218, 214]::integer[],
        'elderly',
        NOW(), NOW()
    )
    ON CONFLICT (index) DO UPDATE
        SET components = ARRAY[v_desert_id, v_density_id, v_aging_id, 218, 214]::integer[],
            updated_at = NOW();

    -- 取得剛建立（或已存在）的 dashboard id
    SELECT id INTO v_dashboard_id FROM dashboards WHERE index = 'aging_care_metrotaipei';

    -- ⚠️ 加入側邊欄群組（舊計劃完全漏掉此步驟）
    -- group_id=3 → 雙北儀表板側邊欄（metrotaipei，前端 city=metrotaipei）
    INSERT INTO dashboard_groups (dashboard_id, group_id)
    VALUES (v_dashboard_id, 3)
    ON CONFLICT DO NOTHING;

    -- group_id=2 → 臺北儀表板側邊欄（taipei，前端 city=taipei）
    INSERT INTO dashboard_groups (dashboard_id, group_id)
    VALUES (v_dashboard_id, 2)
    ON CONFLICT DO NOTHING;
END $$;

-- =============================================================
-- 驗證查詢
-- =============================================================
-- 確認組件 ID
-- SELECT id, index, name FROM components
-- WHERE index IN ('ltc_desert_map','ltc_resource_density','aging_population_dist');

-- 確認 query_charts（每個 index 應有 taipei + metrotaipei 兩筆）
-- SELECT index, query_type, city FROM query_charts
-- WHERE index IN ('ltc_desert_map','ltc_resource_density','aging_population_dist')
-- ORDER BY index, city;

-- 確認 dashboard 與 dashboard_groups（應有 group_id=2 和 group_id=3 兩筆）
-- SELECT d.index, d.name, d.components, dg.group_id
-- FROM dashboards d
-- JOIN dashboard_groups dg ON d.id = dg.dashboard_id
-- WHERE d.index = 'aging_care_metrotaipei';
