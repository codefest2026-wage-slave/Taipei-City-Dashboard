-- scripts/food_safety/migrations/004_seed_risk_dashboard.up.sql
-- Project: 食安風險矩陣 — 註冊 component 1016 並建立獨立 dashboard 504
-- Purpose: Register food_risk_matrix component with 2 query_charts (taipei,
--          metrotaipei) in the `dashboardmanager` database. 獨立 dashboard 504
--          可跨環境運作（不依賴 food-safety-radar 完整 apply 才能掛載）。
-- down:    migrations/004_seed_risk_dashboard.down.sql
-- Order:   components → component_charts → query_charts → dashboards → dashboard_groups
BEGIN;

-- Defensive cleanup
DELETE FROM dashboard_groups WHERE dashboard_id = 504;
DELETE FROM query_charts     WHERE index = 'food_risk_matrix';
DELETE FROM component_charts WHERE index = 'food_risk_matrix';
DELETE FROM components       WHERE id = 1016;

-- ── 1. components ───────────────────────────────────────────────
INSERT INTO components (id, index, name) VALUES
  (1016, 'food_risk_matrix', '食安風險矩陣')
ON CONFLICT (index) DO NOTHING;

-- ── 2. component_charts ─────────────────────────────────────────
-- 4 象限色（依使用者圖象限位置）：
--   左上 持續違規（紅） / 右上 新興風險（黃） / 左下 改善中（藍） / 右下 優良（綠）
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('food_risk_matrix',
   ARRAY['#E53935','#FBC02D','#1E88E5','#43A047'],
   ARRAY['RiskQuadrantChart'], '家')
ON CONFLICT (index) DO NOTHING;

-- ── 3. query_charts: taipei ─────────────────────────────────────
-- 散點圖資料：每筆 = 一家業者
--   X 軸 = 「-歷史違規數」（cutoff 2025-01-01 之前的不合格次數）
--          → 用負值是因為 Apex 軸由小到大為由左到右，
--             「-h」越大（h越小）表示歷史違規越少，視覺上「左多右少」即「歷史多→歷史少」
--   Y 軸 = 近期違規數（cutoff 之後的不合格次數）
--   x_axis 字串編碼為 "{x_value}|{biz_name}" 讓 FE tooltip 能顯示業者名
--   jitter 用 hashtext(biz_key) 衍生 → 同業者每次位置一致
--   優良象限業者太多（4700+），抽樣 60 家避免散點過密
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_risk_matrix', 'two_d',
  $$WITH per_biz AS (
    SELECT
      business_name || '@' || COALESCE(address,'') AS biz_key,
      MAX(business_name) AS biz_name,
      -- 二元分類：一年前有沒有違規、一年內有沒有違規
      BOOL_OR(inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_bool,
      BOOL_OR(inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_bool,
      -- 細部次數給 tooltip 顯示用
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_n,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_n
    FROM food_risk_inspection
    WHERE city = '臺北市'
    GROUP BY biz_key
  ),
  violators AS (
    SELECT * FROM per_biz WHERE (h_bool OR r_bool)
  ),
  combined AS (
    SELECT * FROM violators
    UNION ALL
    -- 優良業者每小時輪替展示 250 家：
    --   hash seed 包含 'YYYY-MM-DD-HH'，每整點換一批
    --   subquery wrap：避免 PG 把 ORDER BY/LIMIT 套到整個 UNION
    SELECT * FROM (
      SELECT * FROM per_biz
      WHERE NOT h_bool AND NOT r_bool
      ORDER BY hashtext(biz_key || to_char(NOW(), 'YYYY-MM-DD-HH24'))
      LIMIT 350
    ) goods_sample
  )
  SELECT
    -- X: cell center ±1.2、jitter ±1.15 → 範圍 ±[0.05, 2.35]，幾乎全 chart 寬
    --    距切線 0.05 (不跨象限)、距 chart edge 0.05 (邊緣全用上)
    -- Y 不對稱：上半受 badge 限制 → [0.5, 1.95]；下半無限制 → [-2.2, -0.5]
    --   上半 cell center +1.225, jitter ±0.725
    --   下半 cell center -1.35,  jitter ±0.85
    ROUND((
      (CASE WHEN h_bool THEN -1.2 ELSE 1.2 END)
      + ((((hashtext(biz_key) % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 2.3
    )::numeric, 3)::text
      || '|' || COALESCE(NULLIF(biz_name,''), '匿名業者')
      || '|h=' || h_n::text || '|r=' || r_n::text
      || '|gt=' || (SELECT COUNT(*) FROM per_biz WHERE NOT h_bool AND NOT r_bool)::text  AS x_axis,
    CASE
      WHEN r_bool THEN
         1.225 + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.45
      ELSE
        -1.35  + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.7
    END  AS data
  FROM combined$$,
  'taipei', '臺北市衛生局 / 食藥署食品查核及檢驗資訊平台',
  '臺北市食安風險矩陣（歷史違規 × 近期違規）。',
  '以業者為單位、依違規時間切兩段（cutoff 2025-01-01）：橫軸 = 歷史違規數（左多→右少）、縱軸 = 近期違規數（下少→上多）。四象限：左上紅 = 持續違規（歷史 + 近期都違 → 待處理）；左下藍 = 改善中（曾違規但近期已停 → 暫緩）；右上黃 = 新興風險（過去無違規但近期才違 → 密切關注）；右下綠 = 優良（持續良好，含合格業者抽樣 60 家）。資料來源：食藥署食品查核及檢驗資訊平台 2026-05-02 稽查紀錄。',
  '主管機關優先稽查業者識別；研究者觀察食安行為趨勢；市民了解所在區域食安狀況。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
);

-- ── 4. query_charts: metrotaipei (雙北合計) ─────────────────────
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'food_risk_matrix', 'two_d',
  $$WITH per_biz AS (
    SELECT
      business_name || '@' || COALESCE(address,'') AS biz_key,
      MAX(business_name) AS biz_name,
      BOOL_OR(inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_bool,
      BOOL_OR(inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_bool,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date <  DATE '2025-05-03') AS h_n,
      COUNT(*) FILTER (WHERE inspection_result='不合格' AND inspection_date >= DATE '2025-05-03') AS r_n
    FROM food_risk_inspection
    WHERE city IN ('臺北市','新北市')
    GROUP BY biz_key
  ),
  violators AS (
    SELECT * FROM per_biz WHERE (h_bool OR r_bool)
  ),
  combined AS (
    SELECT * FROM violators
    UNION ALL
    -- 優良業者每小時輪替展示 250 家：
    --   hash seed 包含 'YYYY-MM-DD-HH'，每整點換一批
    --   subquery wrap：避免 PG 把 ORDER BY/LIMIT 套到整個 UNION
    SELECT * FROM (
      SELECT * FROM per_biz
      WHERE NOT h_bool AND NOT r_bool
      ORDER BY hashtext(biz_key || to_char(NOW(), 'YYYY-MM-DD-HH24'))
      LIMIT 350
    ) goods_sample
  )
  SELECT
    -- X: cell center ±1.2、jitter ±1.15 → 範圍 ±[0.05, 2.35]，幾乎全 chart 寬
    --    距切線 0.05 (不跨象限)、距 chart edge 0.05 (邊緣全用上)
    -- Y 不對稱：上半受 badge 限制 → [0.5, 1.95]；下半無限制 → [-2.2, -0.5]
    --   上半 cell center +1.225, jitter ±0.725
    --   下半 cell center -1.35,  jitter ±0.85
    ROUND((
      (CASE WHEN h_bool THEN -1.2 ELSE 1.2 END)
      + ((((hashtext(biz_key) % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 2.3
    )::numeric, 3)::text
      || '|' || COALESCE(NULLIF(biz_name,''), '匿名業者')
      || '|h=' || h_n::text || '|r=' || r_n::text
      || '|gt=' || (SELECT COUNT(*) FROM per_biz WHERE NOT h_bool AND NOT r_bool)::text  AS x_axis,
    CASE
      WHEN r_bool THEN
         1.225 + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.45
      ELSE
        -1.35  + ((((hashtext(biz_key || '|y') % 1000) + 1000) % 1000)::float / 1000.0 - 0.5) * 1.7
    END  AS data
  FROM combined$$,
  'metrotaipei', '雙北衛生局 / 食藥署',
  '雙北食安風險矩陣（雙城合計，歷史違規 × 近期違規）。',
  '雙城業者違規記錄合併聚合，每點 = 一家業者，cutoff 2025-01-01 切歷史/近期。象限定義同臺北版，資料範圍擴大為臺北市 + 新北市。優良象限抽樣 80 家。',
  '雙城聯合稽查資源配置；跨域食安政策評估；新北市民比較雙北食安風險落差。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{doit,ntpc}', NOW(), NOW()
);

-- ── 5. dashboards：建獨立 dashboard 「食安風險矩陣」(id=504) ────
-- 採獨立 dashboard 而非掛入 503 (食安風險追蹤器)，理由：
--   1. 跨環境穩定 — 不假設 food-safety-radar/apply.sh 跑過
--   2. UI 上單獨呈現「風險矩陣」更突出，便於 demo
--   3. 雙北切換邏輯獨立，不被同 dashboard 其他組件 city 設定影響
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at)
VALUES (504, 'food_risk_matrix', '食安風險矩陣',
        ARRAY[1016], 'restaurant', NOW(), NOW())
ON CONFLICT (id) DO UPDATE
  SET index = EXCLUDED.index,
      name = EXCLUDED.name,
      components = CASE
        WHEN 1016 = ANY(dashboards.components) THEN dashboards.components
        ELSE array_append(dashboards.components, 1016) END,
      updated_at = NOW();

-- ── 6. dashboard_groups：加入 taipei (2) + metrotaipei (3) 兩 group ──
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (504, 2),  -- taipei
  (504, 3)   -- metrotaipei
ON CONFLICT (dashboard_id, group_id) DO NOTHING;

COMMIT;
