# Food Safety Monitor Dashboard 504 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement frontend-first dashboard 504「食安監控系統」on the Taipei City Dashboard, with mock data, alongside existing 503「食安風險追蹤器」.

**Architecture:** Minimal BE seed migration (hardcoded VALUES, no new tables) registers dashboard 504 + 5 components in the manager DB. Frontend implements 3 sidebar charts (Rank/折線/RiskMatrix), 2 mutually-exclusive map layers (校內/校外), and a `FoodSafetyOverlays.vue` floating-panel layer (7 sub-panels) controlled by a new `foodSafetyStore` Pinia store. All map data and mock entities live as static GeoJSON/JSON files under `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/`.

**Tech Stack:** Vue 3 + Pinia, Mapbox-GL-JS (existing `mapStore`), deck.gl ArcLayer (existing `AddArcMapLayer`), ApexCharts (`vue3-apexcharts` already in deps), PostgreSQL (manager DB seed).

**No automated tests** (D6 in spec): every task ends with manual browser/psql verification.

**Reference spec:** `docs/superpowers/specs/2026-05-02-food-safety-monitor-design.md`

---

## File Structure (decomposition lock-in)

| Path | Responsibility |
|---|---|
| `scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql` | Register dashboard 504 + 5 components + 4 component_maps + 10 query_charts |
| `scripts/food_safety_monitor/migrations/001_seed_dashboard.down.sql` | Reverse the above |
| `scripts/food_safety_monitor/apply.sh` / `rollback.sh` / `_db_env.sh` | Workflow scripts (copied from 503) |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson` | ~60 雙北 elementary/junior-high Point features |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/suppliers.geojson` | ~25 supplier Point features |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/supply_chain.geojson` | LineString features for ArcLayer |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/incidents.json` | 5–8 mock food-safety incidents |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/district_heatmap.geojson` | 雙北 41 區 polygon w/ density |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson` | 雙北 ~400 restaurant points w/ grade + risk_quadrant |
| `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurant_inspections.json` | Inspection history keyed by restaurant_id |
| `Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js` | Pinia: activeLayer / selection / mock cache / actions |
| `Taipei-City-Dashboard-FE/src/dashboardComponent/components/RiskMatrixChart.vue` | New chart: ApexCharts scatter, 4 quadrants |
| `Taipei-City-Dashboard-FE/src/dashboardComponent/assets/chart/RiskMatrixChart.svg` | Thumbnail icon |
| `Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts` | Register `RiskMatrixChart` in the dictionary |
| `Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue` | Import + dispatch `RiskMatrixChart` |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/FoodSafetyOverlays.vue` | Container, conditional render of 7 sub-panels |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/SchoolSearchBar.vue` | Top-center search (校內) |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/LayerToggle.vue` | Bottom-left toggles (校內) |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/SchoolAnalysisPanel.vue` | Right-side school/supplier/incident panel (校內) |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/RecentIncidentsStrip.vue` | Bottom horizontal incident cards (校內) |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/RestaurantFilterBar.vue` | Top-center filters (校外) |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/RestaurantInspectionPanel.vue` | Right-side inspection history (校外) |
| `Taipei-City-Dashboard-FE/src/components/foodSafety/ExternalStatsStrip.vue` | Bottom stats + Top 5 mini DonutChart (校外) |
| `Taipei-City-Dashboard-FE/src/views/MapView.vue` | Mount `<FoodSafetyOverlays/>` conditionally |

---

## Phase 1 — Backend seed (manager DB only)

### Task 1: Scaffold `scripts/food_safety_monitor/` infrastructure

**Files:**
- Create: `scripts/food_safety_monitor/_db_env.sh`
- Create: `scripts/food_safety_monitor/.env.script.example`
- Create: `scripts/food_safety_monitor/.gitignore`
- Create: `scripts/food_safety_monitor/apply.sh`
- Create: `scripts/food_safety_monitor/rollback.sh`
- Create: `scripts/food_safety_monitor/backup_db.sh`
- Create: `scripts/food_safety_monitor/README.md`

- [ ] **Step 1: Copy boilerplate from 503**

```bash
git show feat/food-safety-radar:scripts/food_safety/_db_env.sh > scripts/food_safety_monitor/_db_env.sh
git show feat/food-safety-radar:scripts/food_safety/.env.script.example > scripts/food_safety_monitor/.env.script.example
git show feat/food-safety-radar:scripts/food_safety/.gitignore > scripts/food_safety_monitor/.gitignore
git show feat/food-safety-radar:scripts/food_safety/backup_db.sh > scripts/food_safety_monitor/backup_db.sh
chmod +x scripts/food_safety_monitor/backup_db.sh
```

- [ ] **Step 2: Write `apply.sh` (no ETL, only manager-DB migration)**

Create `scripts/food_safety_monitor/apply.sh`:

```bash
#!/usr/bin/env bash
# Apply food-safety-monitor (dashboard 504) seed migration.
# Idempotent: safe to re-run. Rollback via rollback.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
echo

echo "1/2 migration up ..."
pg_psql MANAGER -1 < "$ROOT/migrations/001_seed_dashboard.up.sql"

echo "2/2 verify ..."
pg_psql MANAGER -c "
  SELECT id, index, name FROM dashboards WHERE id = 504;
  SELECT id, index, name FROM components WHERE id BETWEEN 1021 AND 1025 ORDER BY id;
"

echo "✅ apply complete — dashboard 504 食安監控系統 registered"
```

```bash
chmod +x scripts/food_safety_monitor/apply.sh
```

- [ ] **Step 3: Write `rollback.sh`**

Create `scripts/food_safety_monitor/rollback.sh`:

```bash
#!/usr/bin/env bash
# Rollback dashboard 504 seed (removes all 504-related rows).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ rolling back dashboard 504 ..."
pg_psql MANAGER -1 < "$ROOT/migrations/001_seed_dashboard.down.sql"

echo "▶ verify ..."
pg_psql MANAGER -c "SELECT id FROM dashboards WHERE id = 504;"
echo "✅ rollback complete"
```

```bash
chmod +x scripts/food_safety_monitor/rollback.sh
```

- [ ] **Step 4: Write `README.md`**

Create `scripts/food_safety_monitor/README.md`:

```markdown
# 食安監控系統 Dashboard 504 — Standalone Seed

Self-contained registration for dashboard 504. **No new tables, no ETL.** All data
is hardcoded in `migrations/001_seed_dashboard.up.sql` (chart) or served from
`Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/*` (geojson/json).

Coexists with 503「食安風險追蹤器」.

## Quickstart

```bash
./scripts/food_safety_monitor/backup_db.sh        # optional safety net
./scripts/food_safety_monitor/apply.sh            # register dashboard 504
# open http://localhost:8080 → login → dashboard 504「食安監控系統」
./scripts/food_safety_monitor/rollback.sh         # remove dashboard 504
```

Idempotent. Re-running `apply.sh` produces identical state.
```

- [ ] **Step 5: Verify shell scripts are syntactically valid**

```bash
bash -n scripts/food_safety_monitor/apply.sh
bash -n scripts/food_safety_monitor/rollback.sh
bash -n scripts/food_safety_monitor/backup_db.sh
```

Expected: no output (silent success). Any output = syntax error.

- [ ] **Step 6: Commit**

```bash
mkdir -p scripts/food_safety_monitor/migrations  # placeholder for next task
git add scripts/food_safety_monitor/
git commit -m "feat(food-safety-monitor): scaffold dashboard 504 workflow scripts

apply.sh / rollback.sh / backup_db.sh + README. Migration files added in next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Write `001_seed_dashboard` migration (up + down)

**Files:**
- Create: `scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql`
- Create: `scripts/food_safety_monitor/migrations/001_seed_dashboard.down.sql`

- [ ] **Step 1: Write `001_seed_dashboard.up.sql`**

Create the file with 6 sections: defensive cleanup → components → component_charts → component_maps → query_charts (10 rows) → dashboards → dashboard_groups.

```sql
-- scripts/food_safety_monitor/migrations/001_seed_dashboard.up.sql
-- Project: 食安監控系統 (Food Safety Monitor)
-- Purpose: Register dashboard 504 with 5 components (1021-1025), 4 component_maps,
--          10 query_charts (5 components × 2 cities: taipei + metrotaipei),
--          and dashboard_groups membership in the `dashboardmanager` database.
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
  (1022, 'fsm_restaurant_map',     '校外食安地圖'),
  (1023, 'fsm_violation_rank',     '違規食品類別排行'),
  (1024, 'fsm_inspection_trend',   '稽查強度趨勢'),
  (1025, 'fsm_risk_matrix',        '風險矩陣');

-- ── 2. component_charts ────────────────────────────────────────
INSERT INTO component_charts (index, color, types, unit) VALUES
  ('fsm_school_map',       ARRAY['#43A047','#E53935','#FFA000'], ARRAY['MapLegend'],         '校'),
  ('fsm_restaurant_map',   ARRAY['#1565C0','#FFA000','#E53935'], ARRAY['MapLegend'],         '家'),
  ('fsm_violation_rank',   ARRAY['#E53935','#FFA000','#43A047','#1565C0','#8E24AA','#26C6DA','#9E9E9E'], ARRAY['BarChart'], '件'),
  ('fsm_inspection_trend', ARRAY['#1565C0','#E53935'],            ARRAY['ColumnLineChart'],   '件/%'),
  ('fsm_risk_matrix',      ARRAY['#E53935','#FF9800','#1565C0','#43A047'], ARRAY['RiskMatrixChart'], '家');

-- ── 3. component_maps ──────────────────────────────────────────
INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('fsm_schools',       '學校節點',       'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","incident_status"],"red","#E53935","yellow","#FFA000","#43A047"],"circle-radius":6,"circle-opacity":0.85}'::json),
  ('fsm_supply_chain',  '供應鏈連線',     'arc',    'geojson', 'big',
    '{"arc-color":["#FFA000","#E53935"],"arc-width":2,"arc-opacity":0.6,"arc-animate":true}'::json),
  ('fsm_restaurants',   '餐廳稽查點',     'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","grade"],"優","#43A047","良","#FFA000","#E53935"],"circle-radius":4,"circle-opacity":0.8}'::json),
  ('fsm_district_heat', '行政區違規密度', 'fill',   'geojson', 'big',
    '{"fill-color":["interpolate",["linear"],["get","density"],0,"#43A047",50,"#FFA000",100,"#E53935"],"fill-opacity":0.5}'::json);

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
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_schools','fsm_supply_chain') ORDER BY id),
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
  ARRAY(SELECT id FROM component_maps WHERE index IN ('fsm_schools','fsm_supply_chain') ORDER BY id),
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
  '臺北市 12 區違規密度 choropleth + 餐廳節點（grade 三色），點擊餐廳展開稽查歷史。',
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

-- 1023 違規食品類別排行 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_violation_rank', 'two_d',
  $$SELECT * FROM (VALUES
    ('水產', 142), ('蔬菜', 118), ('肉類', 86), ('加工食品', 71),
    ('飲料', 49), ('米飯', 40), ('蛋類', 23), ('罐頭', 18),
    ('乳品', 11), ('麵粉', 9), ('調味品', 6), ('健康食品', 4)
  ) AS t(x_axis, data) ORDER BY data DESC$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市違規食品類別排行 Top 12（mock）。',
  '12 大食品類別違規件數累積排行，告訴父母外食時要特別注意哪些類型的食材容易出問題。',
  '家長預防性決策；店家風險自查；衛生局抽查重點規劃。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1023 違規食品類別排行 — metrotaipei (雙北合計)
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_violation_rank', 'two_d',
  $$SELECT * FROM (VALUES
    ('水產', 213), ('蔬菜', 176), ('肉類', 129), ('加工食品', 104),
    ('飲料', 74), ('米飯', 60), ('蛋類', 34), ('罐頭', 27),
    ('乳品', 17), ('麵粉', 13), ('調味品', 9), ('健康食品', 5)
  ) AS t(x_axis, data) ORDER BY data DESC$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北違規食品類別排行 Top 12（mock）。',
  '12 大食品類別違規件數累積排行（雙城合計）。對齊 mockup 3 左側 Rank。',
  '家長跨城預防；店家風險自查；衛生局聯合抽查重點規劃。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1024 稽查強度趨勢 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_inspection_trend', 'time',
  $$SELECT TO_TIMESTAMP(ym, 'YYYY-MM') AS x_axis, label AS y_axis, val AS data
    FROM (VALUES
      ('2024-04','抽驗數',1812),('2024-05','抽驗數',1955),('2024-06','抽驗數',2103),
      ('2024-07','抽驗數',2240),('2024-08','抽驗數',2188),('2024-09','抽驗數',2310),
      ('2024-10','抽驗數',2055),('2024-11','抽驗數',1988),('2024-12','抽驗數',2102),
      ('2025-01','抽驗數',1860),('2025-02','抽驗數',1975),('2025-03','抽驗數',2210),
      ('2024-04','違規率',8.2),('2024-05','違規率',7.5),('2024-06','違規率',9.1),
      ('2024-07','違規率',8.7),('2024-08','違規率',9.4),('2024-09','違規率',8.0),
      ('2024-10','違規率',10.2),('2024-11','違規率',7.8),('2024-12','違規率',8.5),
      ('2025-01','違規率',9.0),('2025-02','違規率',8.3),('2025-03','違規率',7.9)
    ) AS t(ym, label, val) ORDER BY x_axis, y_axis$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市稽查強度月度趨勢 — 抽驗數 vs 違規率（mock）。',
  '雙軸折線：抽驗數（左軸件）+ 違規率（右軸 %）。呈現「效度」—— 稽查得夠多才能反映真實食安水準。',
  '衛生局自評稽查強度；研究者分析效度。',
  'static', '', 1, 'month', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1024 稽查強度趨勢 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_inspection_trend', 'time',
  $$SELECT TO_TIMESTAMP(ym, 'YYYY-MM') AS x_axis, label AS y_axis, val AS data
    FROM (VALUES
      ('2024-04','抽驗數',2812),('2024-05','抽驗數',3055),('2024-06','抽驗數',3203),
      ('2024-07','抽驗數',3340),('2024-08','抽驗數',3288),('2024-09','抽驗數',3410),
      ('2024-10','抽驗數',3155),('2024-11','抽驗數',3088),('2024-12','抽驗數',3202),
      ('2025-01','抽驗數',2960),('2025-02','抽驗數',3075),('2025-03','抽驗數',3310),
      ('2024-04','違規率',7.5),('2024-05','違規率',7.0),('2024-06','違規率',8.4),
      ('2024-07','違規率',8.1),('2024-08','違規率',8.8),('2024-09','違規率',7.6),
      ('2024-10','違規率',9.5),('2024-11','違規率',7.2),('2024-12','違規率',7.9),
      ('2025-01','違規率',8.3),('2025-02','違規率',7.7),('2025-03','違規率',7.4)
    ) AS t(ym, label, val) ORDER BY x_axis, y_axis$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北稽查強度月度趨勢 — 抽驗數 vs 違規率（mock）。',
  '雙軸折線（雙城合計）。對齊 mockup 3 上中區。',
  '雙城稽查強度比較；研究者分析雙北效度差異。',
  'static', '', 1, 'month', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1025 風險矩陣 — taipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_risk_matrix', 'two_d',
  $$SELECT * FROM (VALUES
    ('高危險店家', 8), ('新興風險', 5), ('改善中', 11), ('優良店家', 42)
  ) AS t(x_axis, data)$$,
  'taipei', '臺北市衛生局（mock）',
  '臺北市餐廳風險四象限分布（mock）。',
  '依「一年前是否違規」× 「一年內是否違規」分四象限：高危險（兩期皆違規）、新興風險（最近才開始）、改善中（已改善）、優良。',
  '衛生局快速辨識高風險店家；CEO/CTO/政府單位視覺化掌握全局。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- 1025 風險矩陣 — metrotaipei
INSERT INTO query_charts (index, query_type, query_chart, city, source,
  short_desc, long_desc, use_case,
  time_from, time_to, update_freq, update_freq_unit,
  map_config_ids, map_filter, links, contributors, created_at, updated_at)
VALUES (
  'fsm_risk_matrix', 'two_d',
  $$SELECT * FROM (VALUES
    ('高危險店家', 12), ('新興風險', 8), ('改善中', 15), ('優良店家', 65)
  ) AS t(x_axis, data)$$,
  'metrotaipei', '雙北衛生局（mock）',
  '雙北餐廳風險四象限分布（mock）。',
  '依「一年前是否違規」× 「一年內是否違規」分四象限。對齊 mockup 3 右下。',
  '雙城衛生局聯合辨識；政策制定者快速視覺化。',
  'static', '', 1, 'year', '{}', '{}', '{}', '{mock}', NOW(), NOW()
);

-- ── 5. dashboards ──────────────────────────────────────────────
INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (504, 'food_safety_monitor', '食安監控系統',
   ARRAY[1021,1022,1023,1024,1025], 'health_and_safety', NOW(), NOW());

-- ── 6. dashboard_groups ────────────────────────────────────────
INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (504, 2),
  (504, 3);

COMMIT;
```

- [ ] **Step 2: Write `001_seed_dashboard.down.sql`**

Create `scripts/food_safety_monitor/migrations/001_seed_dashboard.down.sql`:

```sql
-- scripts/food_safety_monitor/migrations/001_seed_dashboard.down.sql
-- Reverse 001_seed_dashboard.up.sql. Removes ALL dashboard 504 / fsm_* rows.
BEGIN;
DELETE FROM dashboard_groups WHERE dashboard_id = 504;
DELETE FROM dashboards WHERE id = 504;
DELETE FROM query_charts WHERE index LIKE 'fsm_%';
DELETE FROM component_maps WHERE index LIKE 'fsm_%';
DELETE FROM component_charts WHERE index LIKE 'fsm_%';
DELETE FROM components WHERE id BETWEEN 1021 AND 1025;
COMMIT;
```

- [ ] **Step 3: Validate SQL files (lint)**

```bash
# psql --no-psqlrc dry-run if local DB available, otherwise just inspect
wc -l scripts/food_safety_monitor/migrations/*.sql
```

Expected: up.sql > 100 lines, down.sql < 20 lines.

Quick eyeball-check the SQL for matching `BEGIN;`/`COMMIT;` pairs.

- [ ] **Step 4: Commit**

```bash
git add scripts/food_safety_monitor/migrations/
git commit -m "feat(food-safety-monitor): add seed migration for dashboard 504

Registers 5 components (1021-1025), 4 component_maps (fsm_schools / fsm_supply_chain
/ fsm_restaurants / fsm_district_heat), and 10 query_charts (5 components × 2 cities)
into dashboardmanager DB. No new tables; chart values hardcoded inline. Coexists
with dashboard 503.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Apply migration locally and verify

**Files:** none (DB-only verification).

- [ ] **Step 1: Ensure local manager DB is reachable**

```bash
cp scripts/food_safety_monitor/.env.script.example scripts/food_safety_monitor/.env.script
# Edit if not localhost defaults
```

If you don't have a local manager DB, skip to Step 5 (the migration text was eyeballed in Task 2; full DB verify can happen on first deploy).

- [ ] **Step 2: Apply**

```bash
./scripts/food_safety_monitor/apply.sh
```

Expected output (last lines):

```
 id  |        index         |     name
-----+----------------------+--------------
 504 | food_safety_monitor  | 食安監控系統
(1 row)

  id  |          index           |      name
------+--------------------------+------------------
 1021 | fsm_school_map           | 校內食安地圖
 1022 | fsm_restaurant_map       | 校外食安地圖
 1023 | fsm_violation_rank       | 違規食品類別排行
 1024 | fsm_inspection_trend     | 稽查強度趨勢
 1025 | fsm_risk_matrix          | 風險矩陣
(5 rows)

✅ apply complete — dashboard 504 食安監控系統 registered
```

- [ ] **Step 3: Verify query_charts row count**

```bash
source scripts/food_safety_monitor/_db_env.sh
pg_psql MANAGER -c "SELECT COUNT(*) FROM query_charts WHERE index LIKE 'fsm_%';"
```

Expected: `count = 10`.

- [ ] **Step 4: Verify rollback**

```bash
./scripts/food_safety_monitor/rollback.sh
pg_psql MANAGER -c "SELECT COUNT(*) FROM dashboards WHERE id = 504;"
```

Expected: `count = 0`.

Then re-apply for the rest of the plan:

```bash
./scripts/food_safety_monitor/apply.sh
```

- [ ] **Step 5: Mark task done — no commit needed**

(Verification only; SQL was committed in Task 2.)

---

## Phase 2 — Mock data files

> All paths in this phase are under `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/`.

### Task 4: Create `schools.geojson` (~60 雙北 國中小)

**Files:**
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson`

- [ ] **Step 1: Generate the GeoJSON**

Create the file with semi-realistic mock data per spec D4. Each school has all properties documented in spec §4.2. Sample (truncated to 3 entries; the engineer fills out the remaining ~57 schools using real 雙北 國中小 names with mock incident_status / supplier_ids):

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "id": "TPE-EL-001",
        "name": "臺北市信義國小",
        "city": "臺北市",
        "district": "信義區",
        "type": "elementary",
        "incident_status": "red",
        "incident_count": 2,
        "supplier_ids": ["SUP-001", "SUP-005"]
      },
      "geometry": { "type": "Point", "coordinates": [121.567, 25.033] }
    },
    {
      "type": "Feature",
      "properties": {
        "id": "TPE-EL-002",
        "name": "臺北市大安國小",
        "city": "臺北市",
        "district": "大安區",
        "type": "elementary",
        "incident_status": "green",
        "incident_count": 0,
        "supplier_ids": ["SUP-003"]
      },
      "geometry": { "type": "Point", "coordinates": [121.543, 25.026] }
    },
    {
      "type": "Feature",
      "properties": {
        "id": "NTPC-JH-021",
        "name": "新北市板橋國中",
        "city": "新北市",
        "district": "板橋區",
        "type": "junior_high",
        "incident_status": "yellow",
        "incident_count": 1,
        "supplier_ids": ["SUP-001", "SUP-008"]
      },
      "geometry": { "type": "Point", "coordinates": [121.460, 25.013] }
    }
  ]
}
```

Target: ~30 臺北市 + ~30 新北市 = ~60 features. Distribute incident_status: ~5 red, ~10 yellow, ~45 green. Use real district names; coordinates jittered around district centroids. Each school has 1–2 supplier_ids drawn from SUP-001 to SUP-025 (defined in Task 5).

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; d=json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson')); print(len(d['features']), 'features')"
```

Expected: `60 features` (or close).

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson
git commit -m "feat(food-safety-monitor): add schools.geojson mock (~60 雙北 國中小)"
```

---

### Task 5: Create `suppliers.geojson` + `supply_chain.geojson`

**Files:**
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/suppliers.geojson`
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/supply_chain.geojson`

- [ ] **Step 1: Write `suppliers.geojson`**

25 supplier features. Each has id `SUP-001` … `SUP-025` matching `served_school_ids` referencing schools.geojson IDs. Sample (3 of 25):

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "id": "SUP-001",
        "name": "大樹團膳企業股份有限公司",
        "address": "新北市板橋區文化路一段100號",
        "city": "新北市",
        "hazard_level": "Critical",
        "last_inspection": "2025-08-12",
        "last_status": "未通過",
        "served_school_ids": ["TPE-EL-001", "TPE-EL-007", "NTPC-JH-021"]
      },
      "geometry": { "type": "Point", "coordinates": [121.460, 25.010] }
    },
    {
      "type": "Feature",
      "properties": {
        "id": "SUP-003",
        "name": "晨光營養午餐公司",
        "address": "臺北市內湖區...",
        "city": "臺北市",
        "hazard_level": "Low",
        "last_inspection": "2025-12-03",
        "last_status": "通過",
        "served_school_ids": ["TPE-EL-002", "TPE-EL-015"]
      },
      "geometry": { "type": "Point", "coordinates": [121.582, 25.080] }
    },
    {
      "type": "Feature",
      "properties": {
        "id": "SUP-005",
        "name": "陽光食品供應鏈",
        "address": "新北市三重區...",
        "city": "新北市",
        "hazard_level": "High",
        "last_inspection": "2025-09-22",
        "last_status": "限期改善",
        "served_school_ids": ["TPE-EL-001", "NTPC-EL-031", "NTPC-EL-038"]
      },
      "geometry": { "type": "Point", "coordinates": [121.484, 25.067] }
    }
  ]
}
```

Distribute hazard_level: ~3 Critical, ~5 High, ~10 Medium, ~7 Low.

- [ ] **Step 2: Write `supply_chain.geojson`**

LineString features connecting each `(supplier, school)` pair. Derived from supplier.served_school_ids. ~50–80 lines total. Sample:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "school_id": "TPE-EL-001",
        "supplier_id": "SUP-001",
        "risk": "high"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [[121.567, 25.033], [121.460, 25.010]]
      }
    }
  ]
}
```

`risk` value: derived from supplier.hazard_level (Critical/High → "high", Medium → "medium", Low → "low").

- [ ] **Step 3: Validate consistency**

```bash
python3 << 'EOF'
import json
schools = {f['properties']['id'] for f in json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson'))['features']}
suppliers = json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/suppliers.geojson'))
sup_ids = {f['properties']['id'] for f in suppliers['features']}
for sup in suppliers['features']:
    for sid in sup['properties']['served_school_ids']:
        assert sid in schools, f"Supplier {sup['properties']['id']} references missing school {sid}"
chain = json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/supply_chain.geojson'))
for f in chain['features']:
    assert f['properties']['school_id'] in schools
    assert f['properties']['supplier_id'] in sup_ids
print(f"{len(suppliers['features'])} suppliers, {len(chain['features'])} chain links — all references valid")
EOF
```

Expected: e.g. `25 suppliers, 60 chain links — all references valid`.

- [ ] **Step 4: Commit**

```bash
git add Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/suppliers.geojson \
        Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/supply_chain.geojson
git commit -m "feat(food-safety-monitor): add suppliers + supply_chain mock geojson"
```

---

### Task 6: Create `incidents.json` (5–8 mock 食安事件)

**Files:**
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/incidents.json`

- [ ] **Step 1: Write the file**

5 incidents minimum, each referencing real schools + suppliers from prior tasks. Sample structure from spec §4.2; here's one full example, repeat for 5 total:

```json
[
  {
    "id": "INC-2025-09-15",
    "occurred_at": "2025-09-15",
    "severity": "Critical",
    "school_id": "TPE-EL-001",
    "school_name": "臺北市信義國小",
    "supplier_id": "SUP-001",
    "title": "信義國小午餐 15 名學童疑似食物中毒",
    "deaths": 0,
    "injured": 15,
    "hospitalized": 4,
    "confirmed_food": "雞肉飯",
    "suspected_food": "雞肉飯 / 高麗菜",
    "ai_summary": "信義國小近三年共 4 起食安事件，均與大樹團膳企業（SUP-001）相關。本次食物中毒爆發於 2025-09-15 午餐後 3 小時內，15 名學童出現嘔吐、腹瀉症狀，4 人住院。同供應商於板橋國中（NTPC-JH-021）2024-11 亦有類似案例。",
    "news_links": [
      { "title": "聯合新聞網報導", "url": "https://example.com/news/INC-2025-09-15-1" },
      { "title": "中央社", "url": "https://example.com/news/INC-2025-09-15-2" }
    ],
    "affected_school_ids": ["TPE-EL-001", "TPE-EL-007", "NTPC-JH-021"]
  }
]
```

Add 4–7 more incidents covering: severity High / Medium / Low; different schools across 雙北; some sharing supplier_id (for path-2 demo).

- [ ] **Step 2: Validate JSON + consistency**

```bash
python3 << 'EOF'
import json
schools = {f['properties']['id'] for f in json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson'))['features']}
suppliers = {f['properties']['id'] for f in json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/suppliers.geojson'))['features']}
incidents = json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/incidents.json'))
for inc in incidents:
    assert inc['school_id'] in schools, inc['id']
    assert inc['supplier_id'] in suppliers, inc['id']
    for s in inc['affected_school_ids']:
        assert s in schools
print(f"{len(incidents)} incidents, all references valid")
EOF
```

Expected: e.g. `6 incidents, all references valid`.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/incidents.json
git commit -m "feat(food-safety-monitor): add incidents.json mock (5+ events with cross-school impact)"
```

---

### Task 7: Create `district_heatmap.geojson`

**Files:**
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/district_heatmap.geojson`

- [ ] **Step 1: Generate from existing town geojson**

Run a script that reads the existing 雙北 town boundary and adds a mock `density: 0–100` integer to each feature:

```bash
cd Taipei-City-Dashboard-FE
python3 << 'EOF'
import json, random
random.seed(42)
src = json.load(open('public/mapData/metrotaipei_town.geojson'))
out = {'type': 'FeatureCollection', 'features': []}
for f in src['features']:
    p = dict(f.get('properties') or {})
    p['density'] = random.randint(5, 95)
    out['features'].append({'type': 'Feature', 'properties': p, 'geometry': f['geometry']})
json.dump(out, open('public/mockData/food_safety_monitor/district_heatmap.geojson', 'w'), ensure_ascii=False)
print(f"{len(out['features'])} districts written")
EOF
cd ..
```

Expected: `41 districts written` (12 臺北 + 29 新北).

- [ ] **Step 2: Commit**

```bash
git add Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/district_heatmap.geojson
git commit -m "feat(food-safety-monitor): add district_heatmap with mock density per 雙北 district"
```

---

### Task 8: Create `restaurants.geojson` + `restaurant_inspections.json`

**Files:**
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson`
- Create: `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurant_inspections.json`

- [ ] **Step 1: Borrow base from 503 + augment**

```bash
git show feat/food-safety-radar:Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson \
  > Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson
```

- [ ] **Step 2: Augment each feature with `risk_quadrant` + `severity` + bias new北 mock points**

```bash
python3 << 'EOF'
import json, random
random.seed(7)
src = json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson'))
quadrants = ['high_risk', 'emerging', 'improving', 'good']
weights   = [0.10, 0.07, 0.13, 0.70]
sev_map   = {'high_risk':'high', 'emerging':'high', 'improving':'medium', 'good':'low'}

# Augment existing TPE points
for f in src['features']:
    p = f.setdefault('properties', {})
    p.setdefault('city', '臺北市')
    p.setdefault('district', p.get('district', '中正區'))
    p['risk_quadrant'] = random.choices(quadrants, weights=weights, k=1)[0]
    p['severity'] = sev_map[p['risk_quadrant']]
    p.setdefault('grade', random.choice(['優', '良', '需改善']))

# Add ~200 NTPC mock points around district centroids
ntpc_districts = {
  '板橋區': (121.460, 25.011), '三重區': (121.484, 25.067),
  '中和區': (121.499, 24.998), '永和區': (121.514, 25.011),
  '新莊區': (121.450, 25.036), '蘆洲區': (121.471, 25.085),
  '土城區': (121.443, 24.973), '汐止區': (121.643, 25.063),
  '樹林區': (121.420, 24.991), '淡水區': (121.443, 25.171),
}
for i in range(200):
    name = random.choice(list(ntpc_districts.keys()))
    cx, cy = ntpc_districts[name]
    q = random.choices(quadrants, weights=weights, k=1)[0]
    src['features'].append({
        'type': 'Feature',
        'properties': {
            'id': f'NTPC-RES-{i:03d}',
            'name': f'{name}{random.choice(["小館","食堂","餐坊","美食"])}{i:03d}',
            'address': f'新北市{name}',
            'city': '新北市',
            'district': name,
            'grade': random.choice(['優', '良', '需改善']),
            'risk_quadrant': q,
            'severity': sev_map[q],
        },
        'geometry': {
            'type': 'Point',
            'coordinates': [cx + random.uniform(-0.015, 0.015), cy + random.uniform(-0.012, 0.012)]
        }
    })

json.dump(src, open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson', 'w'), ensure_ascii=False)
print(f"{len(src['features'])} restaurants written")
EOF
```

Expected: ~1,800 features (1,686 from 503 + 200 mock 新北).

- [ ] **Step 3: Write `restaurant_inspections.json`**

Picks the first 20 restaurant IDs and gives each 2–4 inspection history rows:

```bash
python3 << 'EOF'
import json, random
random.seed(11)
src = json.load(open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson'))
out = {}
for f in src['features'][:20]:
    rid = f['properties'].get('id') or f['properties'].get('name')
    name = f['properties'].get('name')
    history = []
    for _ in range(random.randint(2, 4)):
        history.append({
            'date': f"202{random.randint(3,5)}/{random.randint(1,12):02d}/{random.randint(1,28):02d}",
            'status': random.choice(['PASS','PASS','FAIL']),
            'issue': random.choice(['餐具大腸桿菌超標','油品酸價超標','食材標示不全','未發現問題','從業人員衛生不合格'])
        })
    out[rid] = {'name': name, 'history': history}
json.dump(out, open('Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurant_inspections.json', 'w'), ensure_ascii=False)
print(f"{len(out)} restaurants with inspection history")
EOF
```

Expected: `20 restaurants with inspection history`.

- [ ] **Step 4: Commit**

```bash
git add Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurants.geojson \
        Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/restaurant_inspections.json
git commit -m "feat(food-safety-monitor): add restaurants + inspection history mock"
```

---

## Phase 3 — Foundation: Pinia store + new chart type

### Task 9: Create `foodSafetyStore` Pinia store

**Files:**
- Create: `Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js`

- [ ] **Step 1: Write the store**

```js
// Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js
// Pinia store for dashboard 504 (食安監控系統).
// Manages: active layer (school|restaurant), selection focus, mock data cache,
// search/filter state, and orchestrates mapStore add/remove/redraw operations.

import { defineStore } from "pinia";
import axios from "axios";
import { useMapStore } from "./mapStore";

const MOCK_BASE = "/mockData/food_safety_monitor";

export const useFoodSafetyStore = defineStore("foodSafety", {
	state: () => ({
		// Mode (mutex toggle result; null = neither layer active)
		activeLayer: null,            // 'school' | 'restaurant' | null

		// Sub-toggles for school map (LayerToggle.vue)
		layerToggles: {
			showSupplyChain: false,
			showIncidentSchools: true,
		},

		// Single covering analysis focus (covers school | supplier | incident)
		analysisFocus: null,          // { type, payload } | null

		// Restaurant selection (independent panel)
		selectedRestaurant: null,

		// School map UX
		schoolSearchQuery: "",

		// Restaurant map UX
		restaurantFilters: {
			district: "all",
			severity: "all",
			timeRange: "1y",
		},

		// Mock data cache (lazy-populated by loadAllMockData())
		schools: [],
		suppliers: [],
		supplyChain: [],
		incidents: [],
		districtHeatmap: null,
		restaurants: [],
		restaurantInspections: {},

		// Loading flags
		loading: {
			schools: false, suppliers: false, supplyChain: false,
			incidents: false, districtHeatmap: false,
			restaurants: false, restaurantInspections: false,
		},
		loadedAt: null,
	}),

	getters: {
		// Filtered schools matching current search query (for SchoolSearchBar dropdown)
		schoolSearchResults(state) {
			const q = state.schoolSearchQuery.trim();
			if (!q) return [];
			return state.schools.filter(
				(f) => f.properties.name.includes(q),
			).slice(0, 8);
		},
		// Recent N incidents sorted by date desc (RecentIncidentsStrip)
		recentIncidents(state) {
			return [...state.incidents].sort(
				(a, b) => b.occurred_at.localeCompare(a.occurred_at),
			);
		},
		// Stats for ExternalStatsStrip (校外底部 4 張卡)
		externalStats(state) {
			const total = state.restaurants.length;
			const fail = state.restaurants.filter(
				(f) => f.properties.risk_quadrant === "high_risk"
				    || f.properties.risk_quadrant === "emerging",
			).length;
			const failRate = total > 0 ? (fail / total * 100).toFixed(2) : "0.00";
			const highRiskDistricts = new Set(
				state.restaurants
					.filter((f) => f.properties.risk_quadrant === "high_risk")
					.map((f) => f.properties.district),
			).size;
			return { total, fail, failRate, highRiskDistricts };
		},
	},

	actions: {
		// ── Loading ─────────────────────────────────────────────
		async loadAllMockData() {
			if (this.loadedAt) return;
			const fetchJson = async (file, key) => {
				this.loading[key] = true;
				try {
					const r = await axios.get(`${MOCK_BASE}/${file}`);
					return r.data;
				} finally {
					this.loading[key] = false;
				}
			};
			const [schools, suppliers, chain, incidents, heat, rest, insp] =
				await Promise.all([
					fetchJson("schools.geojson", "schools"),
					fetchJson("suppliers.geojson", "suppliers"),
					fetchJson("supply_chain.geojson", "supplyChain"),
					fetchJson("incidents.json", "incidents"),
					fetchJson("district_heatmap.geojson", "districtHeatmap"),
					fetchJson("restaurants.geojson", "restaurants"),
					fetchJson("restaurant_inspections.json", "restaurantInspections"),
				]);
			this.schools = schools.features;
			this.suppliers = suppliers.features;
			this.supplyChain = chain.features;
			this.incidents = incidents;
			this.districtHeatmap = heat;
			this.restaurants = rest.features;
			this.restaurantInspections = insp;
			this.loadedAt = Date.now();
		},

		// ── Mutex layer toggle ──────────────────────────────────
		setActiveLayer(layer) {
			const mapStore = useMapStore();
			if (this.activeLayer === layer) {
				// toggle off
				this._removeLayerGroup(this.activeLayer, mapStore);
				this.activeLayer = null;
				this.analysisFocus = null;
				this.selectedRestaurant = null;
				return;
			}
			// switching: remove previous group, then add new
			if (this.activeLayer) {
				this._removeLayerGroup(this.activeLayer, mapStore);
			}
			this.activeLayer = layer;
			// New layer added by Mapbox via dashboard's normal toggle pipeline;
			// nothing extra here. Panels reactively render via watch on activeLayer.
		},

		_removeLayerGroup(layer, mapStore) {
			const ids =
				layer === "school"
					? ["fsm_schools", "fsm_supply_chain"]
					: ["fsm_restaurants", "fsm_district_heat"];
			ids.forEach((idx) => {
				// mapStore.currentLayers entries are `${index}-${type}-${city}`,
				// match by prefix.
				const matching = mapStore.currentLayers.filter(
					(l) => l.startsWith(`${idx}-`),
				);
				matching.forEach((l) => {
					const cfg = mapStore.mapConfigs[l];
					if (cfg) mapStore.removeMapLayer(cfg);
				});
			});
		},

		// ── Selection ───────────────────────────────────────────
		setAnalysisFocus(type, payload) {
			this.analysisFocus = { type, payload };
		},

		selectSchool(school) {
			const mapStore = useMapStore();
			this.setAnalysisFocus("school", school);
			const [lng, lat] = school.geometry.coordinates;
			mapStore.easeToLocation([[lng, lat], 14, 0, 0]);
			if (this.layerToggles.showSupplyChain) {
				const arcs = this.supplyChain.filter(
					(f) => f.properties.school_id === school.properties.id,
				);
				this.redrawSupplyArcs(arcs);
			}
		},

		selectSupplier(supplier) {
			this.setAnalysisFocus("supplier", supplier);
			const arcs = this.supplyChain.filter(
				(f) => f.properties.supplier_id === supplier.properties.id,
			);
			this.redrawSupplyArcs(arcs);
		},

		selectIncident(incident) {
			const mapStore = useMapStore();
			this.setAnalysisFocus("incident", incident);
			// Highlight all affected schools by drawing arcs from supplier → schools
			const arcs = this.supplyChain.filter(
				(f) =>
					f.properties.supplier_id === incident.supplier_id &&
					incident.affected_school_ids.includes(f.properties.school_id),
			);
			this.redrawSupplyArcs(arcs);
			// Fit bounds to affected schools
			const affected = this.schools.filter(
				(f) => incident.affected_school_ids.includes(f.properties.id),
			);
			if (affected.length === 0) return;
			const lats = affected.map((f) => f.geometry.coordinates[1]);
			const lngs = affected.map((f) => f.geometry.coordinates[0]);
			const center = [
				(Math.min(...lngs) + Math.max(...lngs)) / 2,
				(Math.min(...lats) + Math.max(...lats)) / 2,
			];
			mapStore.easeToLocation([center, 12, 0, 0]);
		},

		selectRestaurant(restaurant) {
			this.selectedRestaurant = restaurant;
		},

		// ── ArcLayer redraw (R2) ────────────────────────────────
		redrawSupplyArcs(filteredFeatures) {
			const mapStore = useMapStore();
			// Remove existing supply chain arc layer if any
			const existing = mapStore.currentLayers.filter(
				(l) => l.startsWith("fsm_supply_chain-"),
			);
			existing.forEach((l) => {
				const cfg = mapStore.mapConfigs[l];
				if (cfg) mapStore.removeMapLayer(cfg);
			});
			if (filteredFeatures.length === 0) return;
			// Re-add via mapStore.AddArcMapLayer
			const map_config = {
				index: "fsm_supply_chain",
				type: "arc",
				source: "geojson",
				city: mapStore.map?.style?.metadata?.city || "metrotaipei",
				layerId: `fsm_supply_chain-arc-${Date.now()}`,
				paint: {
					"arc-color": ["#FFA000", "#E53935"],
					"arc-width": 2,
					"arc-opacity": 0.7,
					"arc-animate": true,
				},
			};
			mapStore.AddArcMapLayer(
				map_config,
				{ type: "FeatureCollection", features: filteredFeatures },
			);
		},

		// ── Layer toggles within school map ─────────────────────
		toggleSubLayer(name) {
			this.layerToggles[name] = !this.layerToggles[name];
			// If supply chain just toggled and a school is focused, redraw
			if (name === "showSupplyChain" && this.analysisFocus?.type === "school") {
				if (this.layerToggles.showSupplyChain) {
					const id = this.analysisFocus.payload.properties.id;
					this.redrawSupplyArcs(
						this.supplyChain.filter((f) => f.properties.school_id === id),
					);
				} else {
					this.redrawSupplyArcs([]);
				}
			}
		},

		// ── Reset on dashboard exit ─────────────────────────────
		resetAll() {
			const mapStore = useMapStore();
			// Defensive removal of any fsm_* layers
			["fsm_schools", "fsm_supply_chain", "fsm_restaurants", "fsm_district_heat"]
				.forEach((idx) => {
					const matching = mapStore.currentLayers.filter(
						(l) => l.startsWith(`${idx}-`),
					);
					matching.forEach((l) => {
						const cfg = mapStore.mapConfigs[l];
						if (cfg) mapStore.removeMapLayer(cfg);
					});
				});
			this.$reset();
		},
	},
});
```

- [ ] **Step 2: Verify FE still builds**

```bash
cd Taipei-City-Dashboard-FE && npm run build 2>&1 | tail -20
```

Expected: build succeeds (or fails ONLY because of missing imports we'll add later — but the store file alone shouldn't break anything). If it fails on this file specifically, fix it.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js
git commit -m "feat(food-safety-monitor): add foodSafetyStore Pinia for layer/selection/mock state"
```

---

### Task 10: Create `RiskMatrixChart.vue` + thumbnail SVG

**Files:**
- Create: `Taipei-City-Dashboard-FE/src/dashboardComponent/components/RiskMatrixChart.vue`
- Create: `Taipei-City-Dashboard-FE/src/dashboardComponent/assets/chart/RiskMatrixChart.svg`

- [ ] **Step 1: Write `RiskMatrixChart.vue`**

```vue
<!-- ApexCharts scatter visualizing 4-quadrant restaurant risk matrix.
     Receives 4 buckets (高危險店家 / 新興風險 / 改善中 / 優良店家) with counts;
     renders each bucket as N jittered scatter points within its quadrant.
     X-axis: 一年內違規（0/1, jittered around quadrant center）.
     Y-axis: 一年前違規（0/1, jittered around quadrant center）. -->
<script setup>
import { computed } from "vue";
import VueApexCharts from "vue3-apexcharts";

const props = defineProps([
	"chart_config", "activeChart", "series", "map_config", "map_filter", "map_filter_on",
]);

// 4 quadrant centers in chart space (X: -1 to 1, Y: -1 to 1)
//   X axis = 一年內 violation (right = yes), Y axis = 一年前 violation (top = yes)
const QUADRANTS = {
	"高危險店家": { x: 0.5, y: 0.5,   color: "#E53935" },  // 1y有 + 1y前有
	"新興風險":   { x: 0.5, y: -0.5,  color: "#FF9800" },  // 1y有 + 1y前無
	"改善中":     { x: -0.5, y: 0.5,  color: "#1565C0" },  // 1y無 + 1y前有
	"優良店家":   { x: -0.5, y: -0.5, color: "#43A047" },  // 1y無 + 1y前無
};

function jitter(c, n, spread = 0.35) {
	// Deterministic pseudo-random scatter around center
	const out = [];
	for (let i = 0; i < n; i++) {
		const a = (i * 2.39996323) % (2 * Math.PI);  // golden angle
		const r = spread * Math.sqrt((i + 1) / n);
		out.push({ x: c.x + r * Math.cos(a), y: c.y + r * Math.sin(a) });
	}
	return out;
}

const apexSeries = computed(() => {
	// props.series shape per chart pipeline:
	//   [{ name: '...', data: [{x: '高危險店家', y: 12}, ...] }]
	// or two_d row form: [{ name, data: [12, 8, 15, 65] }] with labels in chart_config.labels
	// Defensive: support both shapes
	const raw = props.series?.[0]?.data ?? [];
	const buckets = raw.map((d) => {
		if (typeof d === "object" && d !== null) return { name: d.x, count: d.y ?? d.data ?? 0 };
		return { name: d, count: 0 };
	});
	return Object.entries(QUADRANTS).map(([label, c]) => {
		const b = buckets.find((x) => x.name === label);
		const count = b ? b.count : 0;
		return {
			name: `${label} (${count})`,
			data: jitter(c, count).map((p) => ({ x: p.x, y: p.y, label })),
		};
	});
});

const chartOptions = computed(() => ({
	chart: {
		type: "scatter",
		zoom: { enabled: false },
		toolbar: { show: false },
		animations: { enabled: true, speed: 400 },
		background: "transparent",
	},
	colors: Object.values(QUADRANTS).map((q) => q.color),
	dataLabels: { enabled: false },
	grid: {
		xaxis: { lines: { show: false } },
		yaxis: { lines: { show: false } },
	},
	xaxis: {
		min: -1, max: 1, tickAmount: 2,
		labels: {
			formatter: (v) => v < 0 ? "一年內無違規" : v > 0 ? "一年內有違規" : "",
			style: { colors: "#aaa", fontSize: "11px" },
		},
		axisBorder: { show: false }, axisTicks: { show: false },
	},
	yaxis: {
		min: -1, max: 1, tickAmount: 2,
		labels: {
			formatter: (v) => v < 0 ? "一年前無違規" : v > 0 ? "一年前有違規" : "",
			style: { colors: "#aaa", fontSize: "11px" },
		},
	},
	annotations: {
		yaxis: [{ y: 0, borderColor: "#666", strokeDashArray: 3 }],
		xaxis: [{ x: 0, borderColor: "#666", strokeDashArray: 3 }],
	},
	legend: { show: true, position: "bottom", labels: { colors: "#ccc" } },
	tooltip: {
		custom: ({ seriesIndex, dataPointIndex, w }) => {
			const point = w.config.series[seriesIndex].data[dataPointIndex];
			return `<div class="chart-tooltip"><h6>${point.label}</h6></div>`;
		},
	},
	markers: { size: 6, strokeWidth: 0 },
}));
</script>

<template>
  <div v-if="activeChart === 'RiskMatrixChart'">
    <VueApexCharts
      width="100%"
      height="320"
      type="scatter"
      :options="chartOptions"
      :series="apexSeries"
    />
  </div>
</template>
```

- [ ] **Step 2: Create thumbnail SVG**

`Taipei-City-Dashboard-FE/src/dashboardComponent/assets/chart/RiskMatrixChart.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <rect width="64" height="64" fill="#1f2125" rx="6"/>
  <line x1="32" y1="6"  x2="32" y2="58" stroke="#666" stroke-dasharray="2 2"/>
  <line x1="6"  y1="32" x2="58" y2="32" stroke="#666" stroke-dasharray="2 2"/>
  <circle cx="44" cy="20" r="2.5" fill="#E53935"/>
  <circle cx="48" cy="14" r="2.5" fill="#E53935"/>
  <circle cx="42" cy="24" r="2.5" fill="#E53935"/>
  <circle cx="44" cy="46" r="2.5" fill="#FF9800"/>
  <circle cx="50" cy="50" r="2.5" fill="#FF9800"/>
  <circle cx="20" cy="20" r="2.5" fill="#1565C0"/>
  <circle cx="14" cy="14" r="2.5" fill="#1565C0"/>
  <circle cx="20" cy="48" r="2.5" fill="#43A047"/>
  <circle cx="14" cy="44" r="2.5" fill="#43A047"/>
  <circle cx="22" cy="52" r="2.5" fill="#43A047"/>
</svg>
```

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/dashboardComponent/components/RiskMatrixChart.vue \
        Taipei-City-Dashboard-FE/src/dashboardComponent/assets/chart/RiskMatrixChart.svg
git commit -m "feat(food-safety-monitor): add RiskMatrixChart 4-quadrant scatter chart"
```

---

### Task 11: Register `RiskMatrixChart` in chart system

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts`
- Modify: `Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue`

- [ ] **Step 1: Update `chartTypes.ts`**

Edit `Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts`. Add the new entry after `TextUnitChart`:

```diff
 	IndicatorChart: "指標圖", // V
 	MapLegend: "地圖圖例", // V
 	TextUnitChart: "文字數值圖", // V
+	RiskMatrixChart: "風險矩陣四象限圖", // V
 };
```

- [ ] **Step 2: Update `DashboardComponent.vue` — add import**

Edit `Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue`. Add new import lines next to other chart imports (around line 30 area, after `TextUnitChart`):

```diff
 import TextUnitChart from "./components/TextUnitChart.vue";
+import RiskMatrixChart from "./components/RiskMatrixChart.vue";
```

And next to the SVG imports:

```diff
 import TextUnitChartSvg from "./assets/chart/TextUnitChart.svg";
+import RiskMatrixChartSvg from "./assets/chart/RiskMatrixChart.svg";
```

- [ ] **Step 3: Update `DashboardComponent.vue` — add dispatch case**

In the same file, find `returnChartComponent(name, svg)` (around line 185). Add the new case right before `default`:

```diff
 	case "TextUnitChart":
 		return svg ? TextUnitChartSvg : TextUnitChart;
+	case "RiskMatrixChart":
+		return svg ? RiskMatrixChartSvg : RiskMatrixChart;
 	default:
 		return svg ? MapLegendSvg : MapLegend;
```

- [ ] **Step 4: Verify FE builds**

```bash
cd Taipei-City-Dashboard-FE && npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts \
        Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue
git commit -m "feat(food-safety-monitor): register RiskMatrixChart in chart dispatch"
```

---

## Phase 4 — FoodSafetyOverlays shell + conditional mount

### Task 12: Create `FoodSafetyOverlays.vue` shell + 7 stub panels

**Files:**
- Create: `Taipei-City-Dashboard-FE/src/components/foodSafety/FoodSafetyOverlays.vue`
- Create (stubs): `SchoolSearchBar.vue`, `LayerToggle.vue`, `SchoolAnalysisPanel.vue`, `RecentIncidentsStrip.vue`, `RestaurantFilterBar.vue`, `RestaurantInspectionPanel.vue`, `ExternalStatsStrip.vue` — all in `Taipei-City-Dashboard-FE/src/components/foodSafety/`.

- [ ] **Step 1: Stub all 7 panel components**

For each panel file, write a placeholder `<template>` showing component name. This is so we can validate mounting before adding real content. Sample (`SchoolSearchBar.vue`):

```vue
<script setup></script>

<template>
  <div class="fsm-panel fsm-panel-search-bar">
    [stub] SchoolSearchBar
  </div>
</template>

<style scoped>
.fsm-panel { background: rgba(20,20,30,0.9); color: #fff; padding: 8px 12px;
             border-radius: 6px; pointer-events: auto; }
.fsm-panel-search-bar { position: absolute; top: 16px; left: 50%;
                         transform: translateX(-50%); width: 320px; }
</style>
```

Repeat for the other 6 with appropriate `position: absolute` placement and a `[stub] <Name>` body. Position spec:
- `LayerToggle.vue`: `bottom: 16px; left: 16px; min-width: 180px;`
- `SchoolAnalysisPanel.vue`: `top: 16px; right: 16px; width: 380px; max-height: 70vh; overflow: auto;`
- `RecentIncidentsStrip.vue`: `bottom: 16px; left: 50%; transform: translateX(-50%); width: 80%; height: 110px; overflow-x: auto;`
- `RestaurantFilterBar.vue`: same as `SchoolSearchBar.vue` (top center, 480px wide)
- `RestaurantInspectionPanel.vue`: same as `SchoolAnalysisPanel.vue`
- `ExternalStatsStrip.vue`: same as `RecentIncidentsStrip.vue` but with mini DonutChart slot

- [ ] **Step 2: Write `FoodSafetyOverlays.vue` container**

```vue
<!-- Conditional overlay container for dashboard 504 (食安監控系統).
     Mounts inside MapView and uses pointer-events: none on root so that
     the underlying Mapbox stays interactive; child panels opt into pointer
     events via .fsm-panel class. -->
<script setup>
import { onMounted, onBeforeUnmount, watch } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
import { useContentStore } from "../../store/contentStore";
import { useMapStore } from "../../store/mapStore";

import SchoolSearchBar          from "./SchoolSearchBar.vue";
import LayerToggle              from "./LayerToggle.vue";
import SchoolAnalysisPanel      from "./SchoolAnalysisPanel.vue";
import RecentIncidentsStrip     from "./RecentIncidentsStrip.vue";
import RestaurantFilterBar      from "./RestaurantFilterBar.vue";
import RestaurantInspectionPanel from "./RestaurantInspectionPanel.vue";
import ExternalStatsStrip       from "./ExternalStatsStrip.vue";

const fs = useFoodSafetyStore();
const content = useContentStore();
const mapStore = useMapStore();

onMounted(async () => {
	await fs.loadAllMockData();
});

// Bind layer-scoped click handlers when mapStore is ready and layer is added.
// We attach to specific layer ids when they appear on the map (R1).
watch(
	() => [...mapStore.currentLayers],
	(layers) => {
		layers.forEach((l) => attachLayerClickHandler(l));
	},
	{ deep: false },
);

const attachedHandlers = new Set();
function attachLayerClickHandler(layerId) {
	if (attachedHandlers.has(layerId)) return;
	if (!mapStore.map) return;
	if (layerId.startsWith("fsm_schools-")) {
		mapStore.map.on("click", layerId, (e) => {
			e.preventDefault?.();
			const f = e.features?.[0];
			if (!f) return;
			fs.selectSchool(f);
		});
		attachedHandlers.add(layerId);
	} else if (layerId.startsWith("fsm_restaurants-")) {
		mapStore.map.on("click", layerId, (e) => {
			e.preventDefault?.();
			const f = e.features?.[0];
			if (!f) return;
			fs.selectRestaurant(f);
		});
		attachedHandlers.add(layerId);
	}
}

onBeforeUnmount(() => {
	fs.resetAll();
	attachedHandlers.clear();
});
</script>

<template>
  <div class="fsm-overlays">
    <!-- 校內 mode panels -->
    <template v-if="fs.activeLayer === 'school'">
      <SchoolSearchBar />
      <LayerToggle />
      <SchoolAnalysisPanel />
      <RecentIncidentsStrip />
    </template>

    <!-- 校外 mode panels -->
    <template v-else-if="fs.activeLayer === 'restaurant'">
      <RestaurantFilterBar />
      <RestaurantInspectionPanel />
      <ExternalStatsStrip />
    </template>
  </div>
</template>

<style scoped>
.fsm-overlays {
	position: absolute;
	inset: 0;
	pointer-events: none;
	z-index: 10;
}
</style>
```

- [ ] **Step 3: Verify FE builds**

```bash
cd Taipei-City-Dashboard-FE && npm run build 2>&1 | tail -10
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/
git commit -m "feat(food-safety-monitor): add FoodSafetyOverlays shell + 7 stub panels

Conditional overlay container that mounts inside MapView when dashboard 504 is
active. Stubs in place for incremental wire-up in subsequent tasks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: Conditionally mount overlays in `MapView.vue`

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/views/MapView.vue`

- [ ] **Step 1: Add import**

Open `Taipei-City-Dashboard-FE/src/views/MapView.vue`. After the existing imports (around line 22, after `import ReportIssue`):

```diff
 import MapContainer from "../components/map/MapContainer.vue";
 import MoreInfo from "../components/dialogs/MoreInfo.vue";
 import ReportIssue from "../components/dialogs/ReportIssue.vue";
+import FoodSafetyOverlays from "../components/foodSafety/FoodSafetyOverlays.vue";
```

- [ ] **Step 2: Mount conditionally in template**

Find the `<MapContainer />` line near the end of the template (around line 575). Insert the overlay below it:

```diff
     <MapContainer />
+    <FoodSafetyOverlays
+      v-if="contentStore.currentDashboard.index === 'food_safety_monitor'"
+    />
     <MoreInfo />
     <ReportIssue />
```

- [ ] **Step 3: Manual verification — dashboard 504 visible + stubs render**

```bash
cd Taipei-City-Dashboard-FE && npm run dev
```

Open `http://localhost:8080`. Login. In the sidebar, find「食安監控系統」(dashboard 504). Click it.

Expected behavior:
- Sidebar shows 5 components (校內食安地圖、校外食安地圖、違規食品類別排行、稽查強度趨勢、風險矩陣).
- The two map components show toggle switches (off by default).
- The Rank chart renders as a horizontal BarChart (already working via existing `BarChart` dispatch).
- The 稽查強度趨勢 chart renders as a `ColumnLineChart`.
- The 風險矩陣 chart renders as our new `RiskMatrixChart` (4 colored scatter clouds).
- No overlay panels visible (because `activeLayer === null` initially).

If you don't see dashboard 504 in the sidebar list, recheck Task 3 verification (BE seed) and confirm `dashboard_groups` has rows for `(504, 2)` and `(504, 3)`.

- [ ] **Step 4: Toggle a map and confirm stubs appear**

In the dashboard 504 sidebar, toggle on「校內食安地圖」.

Expected:
- A circle layer for `fsm_schools` appears on the map (showing school points across 雙北).
- 4 stub overlay boxes appear: top-center「[stub] SchoolSearchBar」, bottom-left「[stub] LayerToggle」, top-right「[stub] SchoolAnalysisPanel」, bottom-center「[stub] RecentIncidentsStrip」.

> Stubs only appear if `activeLayer === 'school'` is set. Initially the toggle just calls the existing handler — `setActiveLayer` isn't wired in yet (Task 14 wires it). For now, manually flip activeLayer in browser dev console:
> ```js
> // browser console
> document.querySelector('.fsm-overlays')   // should exist as <div>
> ```
> If `.fsm-overlays` exists in DOM, mounting works. The stubs will become visible after Task 14 makes `setActiveLayer` fire on toggle.

- [ ] **Step 5: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/views/MapView.vue
git commit -m "feat(food-safety-monitor): mount FoodSafetyOverlays conditionally in MapView"
```

---

### Task 14: Wire mutex layer toggle to `foodSafetyStore`

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/views/MapView.vue`

- [ ] **Step 1: Import the store**

Add to existing `<script setup>` imports in `MapView.vue`:

```diff
 import { useContentStore } from "../store/contentStore";
 import { useDialogStore } from "../store/dialogStore";
 import { useMapStore } from "../store/mapStore";
+import { useFoodSafetyStore } from "../store/foodSafetyStore";
```

Add store instance below the existing `const mapStore = useMapStore();`:

```diff
 const mapStore = useMapStore();
+const foodSafetyStore = useFoodSafetyStore();
```

- [ ] **Step 2: Patch the existing `handleToggle` function**

Find `handleToggle` in `MapView.vue` (it's the existing function that currently does `mapStore.addToMapLayer` / `mapStore.turnOffMapLayer`). Wrap it to detect `fsm_school_map` / `fsm_restaurant_map` toggles and update foodSafetyStore.

Find:

```js
function handleToggle(value, map_config) {
```

Insert at the top of the function body (before any existing logic):

```diff
 function handleToggle(value, map_config) {
+	// Mutex toggle for dashboard 504 (food safety monitor). When user enables one
+	// of the two map components, disable the other in foodSafetyStore (panels
+	// re-render). The actual Mapbox layer add/remove still flows through the
+	// existing pipeline below; foodSafetyStore.setActiveLayer is purely state.
+	const fsmIndex = Array.isArray(map_config) ? map_config[0]?.index : map_config?.index;
+	if (fsmIndex === "fsm_schools" || fsmIndex === "fsm_supply_chain") {
+		foodSafetyStore.setActiveLayer(value ? "school" : null);
+	} else if (fsmIndex === "fsm_restaurants" || fsmIndex === "fsm_district_heat") {
+		foodSafetyStore.setActiveLayer(value ? "restaurant" : null);
+	}
+
```

> Note: `map_config` arrives as either an array (multi-layer component, e.g. fsm_school_map → [fsm_schools, fsm_supply_chain]) or single object. We grab the first index in either case.

- [ ] **Step 3: Verify mutex works in browser**

Run `npm run dev`, open dashboard 504.

- Toggle 校內食安地圖 ON → 4 校內 stub panels should appear (top-center, bottom-left, top-right, bottom-center).
- Toggle 校外食安地圖 ON → 校內 panels disappear, 3 校外 stub panels appear.
- Toggle 校外 OFF → all panels disappear (`activeLayer === null`).

- [ ] **Step 4: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/views/MapView.vue
git commit -m "feat(food-safety-monitor): wire mutex layer toggle to foodSafetyStore"
```

---

## Phase 5 — School map: 4 panels + ArcLayer interactions

### Task 15: Implement `SchoolSearchBar.vue`

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/SchoolSearchBar.vue`

- [ ] **Step 1: Replace stub with full component**

```vue
<!-- Top-center search bar that lets the user find a school by name. Uses
     foodSafetyStore.schoolSearchResults getter for filtered options.
     Selecting a result triggers selectSchool(school) which updates analysis
     focus, eases the map, and (if showSupplyChain on) draws supply arcs. -->
<script setup>
import { ref } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();
const focused = ref(false);

function pick(school) {
	fs.selectSchool(school);
	fs.schoolSearchQuery = school.properties.name;
	focused.value = false;
}
</script>

<template>
  <div class="fsm-panel fsm-search">
    <input
      v-model="fs.schoolSearchQuery"
      type="text"
      placeholder="搜尋學校名稱..."
      @focus="focused = true"
      @blur="setTimeout(() => focused = false, 150)"
    >
    <ul
      v-if="focused && fs.schoolSearchResults.length"
      class="fsm-search-dropdown"
    >
      <li
        v-for="s in fs.schoolSearchResults"
        :key="s.properties.id"
        @mousedown="pick(s)"
      >
        <span class="name">{{ s.properties.name }}</span>
        <span
          class="status"
          :class="`status-${s.properties.incident_status}`"
        >{{
          s.properties.incident_status === 'red' ? '事件' :
          s.properties.incident_status === 'yellow' ? '疑慮' : '正常'
        }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.fsm-panel { pointer-events: auto; }
.fsm-search {
	position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
	width: 320px; background: rgba(20,20,30,0.92);
	border-radius: 6px; padding: 6px 10px;
}
.fsm-search input {
	width: 100%; background: transparent; border: 1px solid #444;
	color: #fff; padding: 6px 10px; border-radius: 4px;
}
.fsm-search-dropdown {
	margin: 6px 0 0; padding: 0; list-style: none;
	background: rgba(20,20,30,0.95); border-radius: 4px;
	max-height: 240px; overflow-y: auto;
}
.fsm-search-dropdown li {
	display: flex; justify-content: space-between; padding: 6px 10px;
	cursor: pointer; color: #ddd;
}
.fsm-search-dropdown li:hover { background: rgba(60,60,80,0.6); }
.status-red    { color: #E53935; }
.status-yellow { color: #FFA000; }
.status-green  { color: #43A047; }
</style>
```

- [ ] **Step 2: Verify in browser**

`npm run dev` → open dashboard 504 → toggle 校內地圖 → type「板橋」in the search bar → dropdown shows matching schools. Click one → map eases to that school.

(ArcLayer drawing won't fire yet because `showSupplyChain` is false by default — Task 16 LayerToggle controls this.)

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/SchoolSearchBar.vue
git commit -m "feat(food-safety-monitor): implement SchoolSearchBar with autocomplete"
```

---

### Task 16: Implement `LayerToggle.vue` (校內 sub-toggles)

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/LayerToggle.vue`

- [ ] **Step 1: Replace stub**

```vue
<!-- Bottom-left sub-toggles for the school map. Two switches:
     - showSupplyChain: draw ArcLayer for selected school's suppliers.
     - showIncidentSchools: highlight schools with incident_status === 'red'. -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
</script>

<template>
  <div class="fsm-panel fsm-toggle">
    <h4>圖層</h4>
    <label>
      <input
        type="checkbox"
        :checked="fs.layerToggles.showSupplyChain"
        @change="fs.toggleSubLayer('showSupplyChain')"
      >
      顯示供應鏈連線
    </label>
    <label>
      <input
        type="checkbox"
        :checked="fs.layerToggles.showIncidentSchools"
        @change="fs.toggleSubLayer('showIncidentSchools')"
      >
      標示曾發生事件學校
    </label>
  </div>
</template>

<style scoped>
.fsm-toggle {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 16px;
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 10px 14px; min-width: 180px; color: #ddd;
}
.fsm-toggle h4 { margin: 0 0 6px; font-size: 13px; color: #aaa; }
.fsm-toggle label { display: flex; align-items: center; gap: 6px;
	font-size: 13px; padding: 4px 0; cursor: pointer; }
</style>
```

- [ ] **Step 2: Verify**

`npm run dev` → dashboard 504 → 校內地圖 ON → toggle「顯示供應鏈連線」.
- If you've previously selected a school via search, the supply chain arcs should now draw.
- Toggle OFF → arcs disappear.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/LayerToggle.vue
git commit -m "feat(food-safety-monitor): implement LayerToggle for supply chain + incident highlight"
```

---

### Task 17: Implement `SchoolAnalysisPanel.vue` (right side, 3-view)

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/SchoolAnalysisPanel.vue`

- [ ] **Step 1: Replace stub**

```vue
<!-- Right-side analysis panel. Shows a single covering view based on
     foodSafetyStore.analysisFocus.type:
       - 'school'   → school details + history + AI summary
       - 'supplier' → supplier details + 危害等級 + served schools list
       - 'incident' → incident card + casualties + AI summary + news links -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();

const f = computed(() => fs.analysisFocus);

// Helpers for school view
const schoolHistory = computed(() => {
	if (f.value?.type !== "school") return [];
	const id = f.value.payload.properties.id;
	return fs.incidents.filter((i) => i.school_id === id || i.affected_school_ids.includes(id));
});

// Helpers for supplier view
const supplierServedSchools = computed(() => {
	if (f.value?.type !== "supplier") return [];
	const ids = f.value.payload.properties.served_school_ids || [];
	return fs.schools.filter((s) => ids.includes(s.properties.id));
});

function pickSchool(school) { fs.selectSchool(school); }
</script>

<template>
  <div class="fsm-panel fsm-analysis">
    <div
      v-if="!f"
      class="fsm-empty"
    >
      請點選地圖上的學校或事件卡以檢視詳情
    </div>

    <!-- School view -->
    <div
      v-else-if="f.type === 'school'"
      class="fsm-view"
    >
      <h3>{{ f.payload.properties.name }}</h3>
      <p>{{ f.payload.properties.city }} · {{ f.payload.properties.district }} · {{
        f.payload.properties.type === 'elementary' ? '國小' : '國中'
      }}</p>
      <div class="badge" :class="`badge-${f.payload.properties.incident_status}`">
        {{ f.payload.properties.incident_status === 'red' ? 'Critical'
         : f.payload.properties.incident_status === 'yellow' ? 'Medium' : 'Low' }}
      </div>
      <h4>歷史食安事件 ({{ schoolHistory.length }})</h4>
      <ul class="history">
        <li
          v-for="i in schoolHistory"
          :key="i.id"
          @click="fs.selectIncident(i)"
        >
          <span class="date">{{ i.occurred_at }}</span>
          <span class="title">{{ i.title }}</span>
          <span class="severity" :class="`sev-${i.severity.toLowerCase()}`">{{ i.severity }}</span>
        </li>
      </ul>
      <h4>AI 摘要</h4>
      <p class="summary">
        {{ schoolHistory[0]?.ai_summary || '尚無相關 AI 摘要。' }}
      </p>
    </div>

    <!-- Supplier view -->
    <div
      v-else-if="f.type === 'supplier'"
      class="fsm-view"
    >
      <h3>{{ f.payload.properties.name }}</h3>
      <p>{{ f.payload.properties.address }}</p>
      <div class="badge" :class="`badge-${f.payload.properties.hazard_level.toLowerCase()}`">
        {{ f.payload.properties.hazard_level }}
      </div>
      <h4>稽查記錄</h4>
      <p>最近稽查：{{ f.payload.properties.last_inspection }} · {{ f.payload.properties.last_status }}</p>
      <h4>供應給以下學校 ({{ supplierServedSchools.length }})</h4>
      <ul class="served">
        <li
          v-for="s in supplierServedSchools"
          :key="s.properties.id"
          @click="pickSchool(s)"
        >
          {{ s.properties.name }}
        </li>
      </ul>
    </div>

    <!-- Incident view -->
    <div
      v-else-if="f.type === 'incident'"
      class="fsm-view"
    >
      <h3>{{ f.payload.title }}</h3>
      <p>{{ f.payload.occurred_at }} · {{ f.payload.school_name }}</p>
      <div class="badge" :class="`badge-${f.payload.severity.toLowerCase()}`">
        {{ f.payload.severity }}
      </div>
      <div class="casualties">
        <div><strong>{{ f.payload.deaths }}</strong> 死亡</div>
        <div><strong>{{ f.payload.injured }}</strong> 受傷</div>
        <div><strong>{{ f.payload.hospitalized }}</strong> 住院</div>
      </div>
      <h4>確認問題食物</h4>
      <p>{{ f.payload.confirmed_food }}</p>
      <h4>議事問題食物</h4>
      <p>{{ f.payload.suspected_food }}</p>
      <h4>AI 摘要</h4>
      <p class="summary">{{ f.payload.ai_summary }}</p>
      <h4>相關新聞</h4>
      <ul class="news">
        <li
          v-for="n in f.payload.news_links"
          :key="n.url"
        >
          <a :href="n.url" target="_blank" rel="noopener">{{ n.title }}</a>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.fsm-analysis {
	pointer-events: auto;
	position: absolute; top: 16px; right: 16px; width: 380px;
	max-height: calc(100vh - 200px); overflow-y: auto;
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 14px; color: #ddd;
}
.fsm-empty { color: #888; font-size: 13px; }
.fsm-view h3 { margin: 0 0 4px; font-size: 16px; color: #fff; }
.fsm-view h4 { margin: 12px 0 4px; font-size: 12px; color: #aaa; text-transform: uppercase; }
.fsm-view p { margin: 4px 0; font-size: 13px; }
.summary { font-style: italic; color: #bbb; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 11px; font-weight: 600; margin: 4px 0; }
.badge-red, .badge-critical { background: #E53935; color: #fff; }
.badge-yellow, .badge-high  { background: #FFA000; color: #fff; }
.badge-medium               { background: #1565C0; color: #fff; }
.badge-green, .badge-low    { background: #43A047; color: #fff; }
.history, .served, .news { list-style: none; padding: 0; margin: 0; }
.history li, .served li {
	padding: 6px 0; border-bottom: 1px solid #333; cursor: pointer;
	font-size: 12px; display: flex; gap: 8px; align-items: center;
}
.history li:hover, .served li:hover { background: rgba(60,60,80,0.4); }
.history .date { color: #888; flex-shrink: 0; }
.history .title { flex: 1; color: #ddd; }
.severity { font-weight: 600; font-size: 11px; }
.sev-critical { color: #E53935; }
.sev-high     { color: #FF6D00; }
.sev-medium   { color: #FFA000; }
.sev-low      { color: #43A047; }
.casualties { display: flex; gap: 14px; padding: 8px 0; }
.casualties strong { font-size: 18px; color: #fff; display: block; }
.news a { color: #4FC3F7; }
</style>
```

- [ ] **Step 2: Verify in browser**

`npm run dev` → dashboard 504 → 校內地圖 ON → search and pick a school. The right-side panel should show the school view with history events. If the school has incidents, the history list is populated. Click one → panel switches to incident view.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/SchoolAnalysisPanel.vue
git commit -m "feat(food-safety-monitor): implement SchoolAnalysisPanel with school/supplier/incident views"
```

---

### Task 18: Implement `RecentIncidentsStrip.vue`

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/RecentIncidentsStrip.vue`

- [ ] **Step 1: Replace stub**

```vue
<!-- Bottom horizontal strip of recent food-safety incidents. Default shows
     the 5 most recent; remaining items accessible via horizontal scroll
     (D2 in spec). Click a card → fs.selectIncident(...). -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
</script>

<template>
  <div class="fsm-panel fsm-strip">
    <div
      v-for="inc in fs.recentIncidents"
      :key="inc.id"
      class="fsm-card"
      :class="`sev-${inc.severity.toLowerCase()}`"
      @click="fs.selectIncident(inc)"
    >
      <div class="card-head">
        <span class="date">{{ inc.occurred_at }}</span>
        <span class="severity">{{ inc.severity }}</span>
      </div>
      <div class="title">{{ inc.title }}</div>
      <div class="school">{{ inc.school_name }}</div>
    </div>
  </div>
</template>

<style scoped>
.fsm-strip {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 50%;
	transform: translateX(-50%); width: 80%; min-width: 600px; max-width: 1100px;
	display: flex; gap: 10px; overflow-x: auto;
	background: rgba(20,20,30,0.85); border-radius: 6px;
	padding: 10px;
}
.fsm-card {
	flex: 0 0 200px; padding: 8px 10px; border-radius: 4px;
	background: rgba(40,40,55,0.95); border-left: 3px solid #43A047;
	cursor: pointer; transition: background 0.15s;
	color: #ddd;
}
.fsm-card:hover { background: rgba(60,60,80,0.95); }
.fsm-card.sev-critical { border-left-color: #E53935; }
.fsm-card.sev-high     { border-left-color: #FF6D00; }
.fsm-card.sev-medium   { border-left-color: #FFA000; }
.card-head { display: flex; justify-content: space-between; font-size: 11px;
             color: #888; }
.title { font-size: 12px; color: #fff; margin-top: 4px;
         display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
         overflow: hidden; }
.school { font-size: 11px; color: #aaa; margin-top: 4px; }
</style>
```

- [ ] **Step 2: Verify**

Dashboard 504 → 校內 ON → bottom strip shows incident cards. Click → right panel switches to incident view. Map fits bounds to affected schools, ArcLayer draws supplier→affected schools.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/RecentIncidentsStrip.vue
git commit -m "feat(food-safety-monitor): implement RecentIncidentsStrip horizontal cards"
```

---

### Task 19: Verify path 1 + path 2 end-to-end (校內)

**Files:** none (verification only).

- [ ] **Step 1: Path 1 — 家長視角（school → supplier → other schools）**

In dev server:
1. Dashboard 504, toggle 校內地圖 ON.
2. LayerToggle: turn ON「顯示供應鏈連線」.
3. SchoolSearchBar: pick a school with incident_status='red' (e.g. 信義國小).
4. **Expected**: Map eases to school. Right panel = school view. ArcLayer draws lines from school to its suppliers.
5. Click a supplier circle on the map.
6. **Expected**: Right panel switches to supplier view (with hazard_level badge + served schools list). ArcLayer redraws from supplier → all served schools.
7. Click a school in the served list.
8. **Expected**: Right panel switches back to school view; ArcLayer redraws.

- [ ] **Step 2: Path 2 — 新聞視角（incident → impact range）**

1. Dashboard 504, toggle 校內地圖 ON.
2. RecentIncidentsStrip: click any incident card.
3. **Expected**: Map fits bounds to affected schools. ArcLayer draws supplier→affected_school_ids in red. Right panel shows incident details (severity, casualties, AI summary, news links).
4. Click a different incident.
5. **Expected**: All previous arcs cleared, new arcs drawn, panel updates.

- [ ] **Step 3: Path 3 — Toggle off**

1. Toggle 校內食安地圖 OFF.
2. **Expected**: All overlays disappear. Map layers (`fsm_schools`, `fsm_supply_chain`) removed. `analysisFocus` cleared.

If any of the above fails, debug and fix in the relevant prior task. Commit any fixes with `fix(food-safety-monitor): ...` messages.

- [ ] **Step 4: No commit (verification only) unless fixes were needed**

---

## Phase 6 — Restaurant map: 3 panels + district heatmap

### Task 20: Implement `RestaurantFilterBar.vue`

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/RestaurantFilterBar.vue`

- [ ] **Step 1: Replace stub**

```vue
<!-- Top-center filter dropdowns for the restaurant map. Sets
     foodSafetyStore.restaurantFilters; the filter is applied via
     mapStore filter expression in Task 22. -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
const districts = ['all', '臺北市', '新北市',
	'信義區','大安區','中正區','中山區','士林區','北投區','內湖區','南港區','文山區','松山區','萬華區','大同區',
	'板橋區','三重區','中和區','永和區','新莊區','新店區','蘆洲區','土城區','汐止區','樹林區','淡水區','三峽區'];
</script>

<template>
  <div class="fsm-panel fsm-filter">
    <label>區域
      <select v-model="fs.restaurantFilters.district">
        <option v-for="d in districts" :key="d" :value="d">{{ d === 'all' ? '全部' : d }}</option>
      </select>
    </label>
    <label>違規程度
      <select v-model="fs.restaurantFilters.severity">
        <option value="all">全部</option>
        <option value="high">高 (高危險 / 新興)</option>
        <option value="medium">中 (改善中)</option>
        <option value="low">低 (優良)</option>
      </select>
    </label>
    <label>時間區間
      <select v-model="fs.restaurantFilters.timeRange">
        <option value="3m">近 3 個月</option>
        <option value="6m">近 6 個月</option>
        <option value="1y">近 1 年</option>
        <option value="3y">近 3 年</option>
      </select>
    </label>
  </div>
</template>

<style scoped>
.fsm-filter {
	pointer-events: auto;
	position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
	display: flex; gap: 10px; padding: 8px 14px;
	background: rgba(20,20,30,0.92); border-radius: 6px; color: #ccc;
}
.fsm-filter label { display: flex; flex-direction: column; font-size: 11px; gap: 2px; }
.fsm-filter select { background: rgba(40,40,55,0.95); border: 1px solid #444;
	color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
</style>
```

- [ ] **Step 2: Verify dropdowns appear when 校外地圖 toggled ON**

Dashboard 504 → 校外食安地圖 ON → top-center filter bar visible.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/RestaurantFilterBar.vue
git commit -m "feat(food-safety-monitor): implement RestaurantFilterBar dropdowns"
```

---

### Task 21: Implement `RestaurantInspectionPanel.vue`

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/RestaurantInspectionPanel.vue`

- [ ] **Step 1: Replace stub**

```vue
<!-- Right-side panel showing inspection history of selected restaurant.
     Reads from foodSafetyStore.selectedRestaurant + restaurantInspections cache. -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();

const restaurant = computed(() => fs.selectedRestaurant);
const restaurantId = computed(() => {
	const r = restaurant.value;
	if (!r) return null;
	return r.properties.id || r.properties.name;
});
const inspection = computed(() => {
	const id = restaurantId.value;
	if (!id) return null;
	return fs.restaurantInspections[id] || null;
});
</script>

<template>
  <div class="fsm-panel fsm-inspection">
    <div v-if="!restaurant" class="fsm-empty">
      點選地圖上的餐廳以檢視稽查歷史
    </div>
    <div v-else class="fsm-view">
      <h3>{{ restaurant.properties.name }}</h3>
      <p>{{ restaurant.properties.address || `${restaurant.properties.city} · ${restaurant.properties.district}` }}</p>
      <div class="badge" :class="`grade-${restaurant.properties.grade}`">
        {{ restaurant.properties.grade || '未評' }}
      </div>
      <h4>稽查歷史</h4>
      <ul v-if="inspection" class="history">
        <li
          v-for="(h, i) in inspection.history"
          :key="i"
          :class="`row-${h.status.toLowerCase()}`"
        >
          <span class="date">{{ h.date }}</span>
          <span class="status">{{ h.status }}</span>
          <span class="issue">{{ h.issue }}</span>
        </li>
      </ul>
      <p v-else class="hint">尚無此餐廳的稽查歷史 mock 資料。</p>
    </div>
  </div>
</template>

<style scoped>
.fsm-inspection {
	pointer-events: auto;
	position: absolute; top: 80px; right: 16px; width: 320px;
	max-height: calc(100vh - 280px); overflow-y: auto;
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 14px; color: #ddd;
}
.fsm-empty { color: #888; font-size: 13px; }
.fsm-view h3 { margin: 0; font-size: 16px; color: #fff; }
.fsm-view p  { margin: 4px 0; font-size: 12px; color: #bbb; }
.fsm-view h4 { margin: 12px 0 4px; font-size: 12px; color: #aaa; text-transform: uppercase; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 11px; font-weight: 600; margin: 4px 0; }
.grade-優      { background: #43A047; color: #fff; }
.grade-良      { background: #FFA000; color: #fff; }
.grade-需改善  { background: #E53935; color: #fff; }
.history { list-style: none; padding: 0; margin: 0; }
.history li { display: grid; grid-template-columns: 90px 50px 1fr; gap: 6px;
              padding: 6px 0; border-bottom: 1px solid #333; font-size: 12px; }
.row-pass .status { color: #43A047; font-weight: 600; }
.row-fail .status { color: #E53935; font-weight: 600; }
.hint { color: #888; font-size: 12px; }
</style>
```

- [ ] **Step 2: Verify**

Dashboard 504 → 校外 ON → click any restaurant point → right panel shows inspection history (or "尚無 mock 資料" if id not in the 20-restaurant inspection sample).

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/RestaurantInspectionPanel.vue
git commit -m "feat(food-safety-monitor): implement RestaurantInspectionPanel"
```

---

### Task 22: Implement `ExternalStatsStrip.vue` (4 stat cards + Top 5 mini DonutChart)

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/foodSafety/ExternalStatsStrip.vue`

- [ ] **Step 1: Replace stub**

```vue
<!-- Bottom strip with 4 stat cards (total / fail count / fail rate / high-risk
     district count) + a mini horizontal bar chart showing Top 5 violation
     categories. Reads externalStats getter + (Top 5 served from same data
     used in fsm_violation_rank if exposed; here kept as mini chart literal). -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
import VueApexCharts from "vue3-apexcharts";

const fs = useFoodSafetyStore();
const stats = computed(() => fs.externalStats);

// Top 5 mini chart — literal for restaurant overlay (independent from sidebar 1023);
// shows top 5 violation issues from restaurantInspections cache.
const top5 = computed(() => {
	const counter = {};
	Object.values(fs.restaurantInspections).forEach((r) => {
		(r.history || []).forEach((h) => {
			if (h.status === "FAIL" && h.issue !== "未發現問題") {
				counter[h.issue] = (counter[h.issue] || 0) + 1;
			}
		});
	});
	return Object.entries(counter)
		.sort((a, b) => b[1] - a[1])
		.slice(0, 5);
});

const top5Series = computed(() => [{
	name: "件數",
	data: top5.value.map(([_, v]) => v),
}]);
const top5Options = computed(() => ({
	chart: { toolbar: { show: false } },
	colors: ["#E53935"],
	plotOptions: { bar: { borderRadius: 2, horizontal: true, distributed: false } },
	dataLabels: { enabled: false },
	grid: { show: false },
	xaxis: {
		categories: top5.value.map(([k]) => k),
		labels: { style: { colors: "#aaa", fontSize: "10px" } },
		axisBorder: { show: false }, axisTicks: { show: false },
	},
	yaxis: { labels: { style: { colors: "#ccc", fontSize: "11px" } } },
	tooltip: { enabled: false },
	legend: { show: false },
}));
</script>

<template>
  <div class="fsm-panel fsm-stats">
    <div class="cards">
      <div class="card">
        <div class="value">{{ stats.total.toLocaleString() }}</div>
        <div class="label">已抽驗餐廳</div>
      </div>
      <div class="card">
        <div class="value">{{ stats.fail.toLocaleString() }}</div>
        <div class="label">違規件數</div>
      </div>
      <div class="card">
        <div class="value">{{ stats.failRate }}%</div>
        <div class="label">違規率</div>
      </div>
      <div class="card">
        <div class="value">{{ stats.highRiskDistricts }}</div>
        <div class="label">高風險區</div>
      </div>
    </div>
    <div class="chart-area">
      <h4>近一年違規 Top 5</h4>
      <VueApexCharts
        v-if="top5.length"
        type="bar"
        height="120"
        :options="top5Options"
        :series="top5Series"
      />
      <p v-else class="hint">尚無 mock 違規資料</p>
    </div>
  </div>
</template>

<style scoped>
.fsm-stats {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 50%;
	transform: translateX(-50%); width: 80%; min-width: 700px; max-width: 1100px;
	display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
	padding: 12px; background: rgba(20,20,30,0.92); border-radius: 6px;
}
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.card { padding: 10px; background: rgba(40,40,55,0.9); border-radius: 4px; text-align: center; }
.value { font-size: 22px; font-weight: 700; color: #fff; }
.label { font-size: 11px; color: #aaa; }
.chart-area h4 { margin: 0 0 4px; font-size: 11px; color: #aaa; }
.hint { color: #888; font-size: 12px; }
</style>
```

- [ ] **Step 2: Verify**

Dashboard 504 → 校外 ON → bottom strip shows 4 stat cards + mini bar chart.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/components/foodSafety/ExternalStatsStrip.vue
git commit -m "feat(food-safety-monitor): implement ExternalStatsStrip with 4 stat cards + Top 5 mini chart"
```

---

### Task 23: District heatmap z-index (insert before town label)

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js`

- [ ] **Step 1: Add a `_ensureDistrictBeforeTownLabel` helper**

The existing `mapStore.addMapLayer` already accepts the layer config but doesn't expose `beforeId`. We patch z-index after the layer is added by calling the underlying `mapStore.map.moveLayer(layerId, 'metrotaipei_town_label-symbol')`.

Open `Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js`. Add an action and call it from `setActiveLayer` when entering restaurant mode:

```diff
 		setActiveLayer(layer) {
 			const mapStore = useMapStore();
 			if (this.activeLayer === layer) {
 				this._removeLayerGroup(this.activeLayer, mapStore);
 				this.activeLayer = null;
 				this.analysisFocus = null;
 				this.selectedRestaurant = null;
 				return;
 			}
 			if (this.activeLayer) {
 				this._removeLayerGroup(this.activeLayer, mapStore);
 			}
 			this.activeLayer = layer;
+			if (layer === "restaurant") {
+				// After Mapbox/dashboard adds the district fill layer, raise the
+				// town label so labels stay visible on top of choropleth (R4).
+				setTimeout(() => this._raiseTownLabel(mapStore), 600);
+			}
 		},
+
+		_raiseTownLabel(mapStore) {
+			const m = mapStore.map;
+			if (!m) return;
+			try {
+				if (m.getLayer("metrotaipei_town_label-symbol")) {
+					m.moveLayer("metrotaipei_town_label-symbol");
+				}
+			} catch (_) { /* layer not present yet — no-op */ }
+		},
```

(The `setTimeout(600)` lets the dashboard pipeline finish adding the district_heat layer first; we then move town labels above it.)

- [ ] **Step 2: Verify**

Dashboard 504 → 校外 ON → district fills (red/yellow/green by density) appear; district names remain readable on top.

- [ ] **Step 3: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js
git commit -m "fix(food-safety-monitor): raise town labels above district heatmap fill"
```

---

## Phase 7 — Polish: city switch + final demo

### Task 24: City switch filter expression (no GeoJSON reload)

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js`

- [ ] **Step 1: Add a watcher that applies a Mapbox filter to fsm_schools / fsm_restaurants when active city changes**

We hook off `mapStore.map.setFilter(layerId, expr)`. Add an action in foodSafetyStore:

```diff
+		applyCityFilter(city) {
+			// city: 'metrotaipei' | 'taipei' | 'ntpc'
+			const mapStore = useMapStore();
+			const cityFilter =
+				city === "taipei" ? ["==", ["get", "city"], "臺北市"] :
+				city === "ntpc"   ? ["==", ["get", "city"], "新北市"] :
+				null;
+			["fsm_schools", "fsm_restaurants"].forEach((idx) => {
+				const layer = mapStore.currentLayers.find((l) => l.startsWith(`${idx}-`));
+				if (!layer || !mapStore.map?.getLayer(layer)) return;
+				if (cityFilter) mapStore.map.setFilter(layer, cityFilter);
+				else            mapStore.map.setFilter(layer, null);
+			});
+		},
```

- [ ] **Step 2: Wire up in `MapView.vue`**

Open `Taipei-City-Dashboard-FE/src/views/MapView.vue`. Find the `watch(() => route.query?.city, ...)` block (it already exists in MapContainer or MapView for city updates). Inside MapView's existing logic where city changes are observed, dispatch `applyCityFilter`:

If MapView doesn't have a city watcher, add one. Append after the existing `const foodSafetyStore = useFoodSafetyStore();` in `<script setup>`:

```diff
 const foodSafetyStore = useFoodSafetyStore();
+
+watch(
+	() => route.query?.city,
+	(newCity) => {
+		if (contentStore.currentDashboard.index === "food_safety_monitor") {
+			foodSafetyStore.applyCityFilter(newCity || "metrotaipei");
+		}
+	},
+);
```

If `watch`/`route` aren't already imported in MapView.vue, add to imports:

```diff
-import { computed, ref, watch } from "vue";
-import { useRoute } from "vue-router";
+import { computed, ref, watch } from "vue";
+import { useRoute } from "vue-router";
```

(They're already imported per existing MapView.vue scan; if not, add them.)

- [ ] **Step 3: Verify**

Dashboard 504 → 校內 ON → top tags show「臺北 / 雙北 / 新北」(via existing city tag mechanism). Click「臺北」→ map shows only 臺北市 schools. Click「新北」→ only 新北 schools. Click「雙北」→ all visible.

Repeat for 校外 mode with restaurants.

- [ ] **Step 4: Commit**

```bash
git add Taipei-City-Dashboard-FE/src/store/foodSafetyStore.js \
        Taipei-City-Dashboard-FE/src/views/MapView.vue
git commit -m "feat(food-safety-monitor): apply city filter expression to fsm_* layers on city switch"
```

---

### Task 25: End-to-end demo walkthrough (final verification)

**Files:** none (verification only).

Walk through the full feature_plan demo story line as defined in the spec §5 and feature_plan_food_safety.md §「完整 Demo 故事線」.

- [ ] **Step 1: 入學情境（家長視角）**

1. Open dashboard 504. Confirm:
   - sidebar shows 5 components in correct order (校內 / 校外 / Rank / 折線 / 風險矩陣).
   - Rank, 折線, 風險矩陣 all render data from BE query_charts.
2. Toggle 校內食安地圖 ON. Confirm:
   - 4 校內 panels appear.
   - Schools render as colored circles.

- [ ] **Step 2: 學校 → 供應鏈**

1. SchoolSearchBar: search「板橋」→ pick a result.
2. LayerToggle: enable 顯示供應鏈連線.
3. Confirm: ArcLayer draws from school to its suppliers.
4. Click a supplier on the map → panel switches to supplier view → arcs redraw supplier → all served schools.

- [ ] **Step 3: 事件展示**

1. RecentIncidentsStrip: click an incident card.
2. Confirm: Map fits affected schools, ArcLayer red, panel shows incident details.

- [ ] **Step 4: 校外切換**

1. Toggle 校內 OFF, toggle 校外食安地圖 ON.
2. Confirm: 校內 panels disappear, 校外 panels appear (filter bar, inspection panel placeholder, stats strip).
3. District choropleth (red/yellow/green) visible. Town labels readable above choropleth.

- [ ] **Step 5: 餐廳稽查史**

1. Click a restaurant point.
2. Confirm: Right panel shows grade badge, inspection history (or hint if id not in mock).

- [ ] **Step 6: 雙北切換**

1. Switch city tag to 臺北.
2. Confirm: Schools/restaurants filter to 臺北市 only.
3. Switch to 新北 → 新北市 only.
4. Switch back to 雙北 → all visible.

- [ ] **Step 7: 離開 dashboard 504**

1. Switch to dashboard 503 (or any other).
2. Confirm: All fsm_* layers removed from map. Overlay panels gone. No console errors.

- [ ] **Step 8: If everything passes, finalize with a summary commit (only if there are uncommitted file changes)**

```bash
git status
# if clean, no commit needed; otherwise:
git add -p   # review and stage
git commit -m "docs(food-safety-monitor): final demo walkthrough verified"
```

---

## Self-Review (filled in by author)

**Spec coverage:**
- §1 專案目標: covered by all phases.
- §2 總體架構: implemented across Phases 1-6.
- §3 檔案樹: every entry has a corresponding task (Tasks 1, 2, 4-12, 13, 14-22).
- §4 資料 schema:
  - 4.1 BE seed migration → Tasks 1-3.
  - 4.2 mockData files → Tasks 4-8.
  - 4.3 foodSafetyStore state → Task 9 (state matches spec exactly: activeLayer, layerToggles, analysisFocus, selectedRestaurant, schoolSearchQuery, restaurantFilters, mock data caches, loading flags).
- §5 互動流程: paths 1, 2, 3 verified in Tasks 19, 25.
- §6 風險與決策:
  - R1 layer-scoped click → Task 12 (`attachLayerClickHandler`).
  - R2 redrawSupplyArcs → Task 9.
  - R3 resetAll on unmount → Task 9 + Task 12.
  - R4 town label z-index → Task 23.
  - R5 risk matrix two_d shape → Task 2 SQL + Task 10 chart.
  - R6 covering analysisFocus → Task 9 + Task 17.
  - D1-D6 honored throughout (no tests, mobile unsupported, semi-real mock, parallel preload, top-5 strip with horizontal scroll, search by school only).
- §7 Out of Scope: explicitly skipped.

**Placeholder scan:** No "TBD" / "TODO" / "implement later" / "fill in details" remain. Mock data tasks have small representative samples and clear expansion guidance ("repeat for ~57 more schools").

**Type consistency:**
- `setActiveLayer(layer)` argument: `'school' | 'restaurant' | null` — used consistently in Task 9 store, Task 14 wrapper, Task 12 watch.
- `analysisFocus`: `{ type, payload }` — Task 9 sets, Task 17 reads.
- `selectedRestaurant`: feature object (not id) — Task 9 sets, Task 21 reads.
- `redrawSupplyArcs(filteredFeatures)`: `Array<Feature>` — Tasks 9, 19 use.
- `applyCityFilter(city)`: `'metrotaipei' | 'taipei' | 'ntpc'` — Task 24 only.
- Mock data file names match across Phase 2 tasks and Task 9 fetch URLs.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-02-food-safety-monitor.md`.**
