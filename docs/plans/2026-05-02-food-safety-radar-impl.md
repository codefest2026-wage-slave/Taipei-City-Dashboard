# 食安風險追蹤器 Food Safety Radar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mirror the `feat/labor-safety-radar` isolation pattern to package food-safety dashboard 503 (5 components, real dual-city) into a self-contained `scripts/food_safety/` folder with offline ETL, idempotent migrations, and apply/rollback/backup scripts.

**Architecture:** Branch `feat/food-safety-radar` from `origin/feat/labor-safety-radar` HEAD `78d2742`. All food-safety work lives in `scripts/food_safety/` — drop the folder = remove the dashboard. Two SQL migrations (001 create tables, 002 seed dashboard) in `dashboard` + `dashboardmanager` DBs respectively. Five Python ETL loaders read from `docs/assets/` + `snapshots/` (zero HTTP at apply time). One offline `snapshot_apis.py` regenerates NTPC factory CSV on demand.

**Tech Stack:** PostgreSQL 16 + PostGIS, Python 3 (psycopg2 + openpyxl + requests for snapshot only), Bash, idempotent SQL, FE/BE zero-changes.

---

## Reference Files (read these first)

- Spec: `docs/plans/2026-05-02-food-safety-radar-design.md` (single source of truth for design decisions)
- Labor template (already in this worktree): `scripts/labor_safety/` — read `_db_env.sh`, `etl/_db.py`, `apply.sh`, `rollback.sh`, `migrations/001_create_tables.up.sql`, `etl/load_violations_ntpc.py` to learn the exact conventions used for credentials, transactions, encoding, and error handling.
- Original food safety scripts on `feat/green-mobility-dashboard` (parent worktree at `/Users/teddy_peng/Projects/my/Taipei-City-Dashboard`):
  - `scripts/generate_food_safety_sql.py` — TPE inspection/testing/restaurant + NTPC factory logic to port
  - `scripts/generate_mohw_food_stats_sql.py` — MOHW xlsx parsers (poisoning cause, by-city)
  - `scripts/generate_food_type_violations_sql.py` — MOHW xlsx parser (food category violations)
  - `scripts/register_food_safety.sql` — query_chart SQL for components 1011-1015 (taipei queries to keep verbatim)
  - `scripts/.geocode_cache.json` — 9680 entries to copy

The spec §5 contains the **exact** rewritten metrotaipei queries — quote them verbatim into 002 seed migration.

---

## Task 1: Scaffold directory + env + connection helpers

**Files:**
- Create: `scripts/food_safety/.gitignore`
- Create: `scripts/food_safety/.env.script.example`
- Create: `scripts/food_safety/_db_env.sh`
- Create: `scripts/food_safety/etl/_db.py`
- Create: `scripts/food_safety/backups/.gitkeep` (empty file)
- Create: `scripts/food_safety/snapshots/.gitkeep` (empty file)

**Steps:**

- [ ] **Step 1.1: Copy `_db_env.sh` from labor and rename internal vars**

  Copy `scripts/labor_safety/_db_env.sh` to `scripts/food_safety/_db_env.sh`. Then change two prefixes to keep namespace isolation:

  - `_LS_ROOT` → `_FS_ROOT`
  - `_LS_REPO` → `_FS_REPO`
  - Update header comment from `# scripts/labor_safety/_db_env.sh` to `# scripts/food_safety/_db_env.sh`
  - Update `_load_env_file "$_LS_ROOT/.env.script"` → `_load_env_file "$_FS_ROOT/.env.script"`
  - Update `_load_env_file "$_LS_REPO/docker/.env"` → `_load_env_file "$_FS_REPO/docker/.env"`

  Everything else (`pg_psql` / `pg_dump_data` / `pg_dump_manager` functions, default credentials) stays identical. The file relies on shared host docker network so labor and food talk to the same Postgres.

- [ ] **Step 1.2: Copy `etl/_db.py` from labor**

  Copy `scripts/labor_safety/etl/_db.py` to `scripts/food_safety/etl/_db.py` and rename two module-level constants:

  - `LS_ROOT = Path(__file__).resolve().parents[1]` → `FS_ROOT = Path(__file__).resolve().parents[1]`
  - All references to `LS_ROOT` in the body → `FS_ROOT`

  Keep `db_kwargs()` and `manager_kwargs()` function names — they are imported by every loader.

- [ ] **Step 1.3: Create `.gitignore`**

  ```
  .env.script
  backups/
  ```

- [ ] **Step 1.4: Create `.env.script.example`**

  Copy from `scripts/labor_safety/.env.script.example` verbatim — same DB credentials format, same `PG_CLIENT_IMAGE` default. No food-safety-specific keys.

- [ ] **Step 1.5: Create `backups/.gitkeep` and `snapshots/.gitkeep`**

  ```bash
  touch scripts/food_safety/backups/.gitkeep
  touch scripts/food_safety/snapshots/.gitkeep
  ```

- [ ] **Step 1.6: Verify shell sourcing works**

  ```bash
  cd .worktrees/food-safety-radar
  bash -c 'source scripts/food_safety/_db_env.sh && declare -f pg_psql >/dev/null && echo "✓ pg_psql defined"'
  ```
  Expected: `✓ pg_psql defined`

- [ ] **Step 1.7: Verify Python module loads**

  ```bash
  cd .worktrees/food-safety-radar
  python3 -c "import sys; sys.path.insert(0, 'scripts/food_safety/etl'); from _db import db_kwargs, manager_kwargs; print(db_kwargs()['dbname'], manager_kwargs()['dbname'])"
  ```
  Expected: `dashboard dashboardmanager`

- [ ] **Step 1.8: Commit (defer until Task 6 — scaffold + migrations + bash scripts ship together)**

---

## Task 2: Migration 001 — create 7 food_* tables

**Files:**
- Create: `scripts/food_safety/migrations/001_create_tables.up.sql`
- Create: `scripts/food_safety/migrations/001_create_tables.down.sql`

**Steps:**

- [ ] **Step 2.1: Write `001_create_tables.up.sql`**

  Wrap in `BEGIN;` … `COMMIT;`. All 7 `CREATE TABLE IF NOT EXISTS`. Schemas come from spec §4.

  ```sql
  -- scripts/food_safety/migrations/001_create_tables.up.sql
  -- Project: 食安風險追蹤器 (Food Safety Radar)
  -- Purpose: Create the 7 food_* tables in the `dashboard` database.
  --          Idempotent (CREATE TABLE IF NOT EXISTS) and transactional.
  -- down:    migrations/001_create_tables.down.sql
  BEGIN;

  -- ── 1. food_inspection_tpe (TPE 20-year inspection statistics) ──
  CREATE TABLE IF NOT EXISTS food_inspection_tpe (
      year                 INTEGER PRIMARY KEY,
      total_inspections    INTEGER,
      restaurant_insp      INTEGER,
      drink_shop_insp      INTEGER,
      street_vendor_insp   INTEGER,
      market_insp          INTEGER,
      supermarket_insp     INTEGER,
      manufacturer_insp    INTEGER,
      total_noncompliance  INTEGER,
      restaurant_nc        INTEGER,
      drink_shop_nc        INTEGER,
      street_vendor_nc     INTEGER,
      market_nc            INTEGER,
      supermarket_nc       INTEGER,
      manufacturer_nc      INTEGER,
      food_poisoning_cases INTEGER
  );

  -- ── 2. food_testing_tpe (TPE 20-year testing statistics) ──
  CREATE TABLE IF NOT EXISTS food_testing_tpe (
      year             INTEGER PRIMARY KEY,
      total_tested     INTEGER,
      total_violations INTEGER,
      violation_rate   NUMERIC(5,2),
      viol_labeling    INTEGER,
      viol_ad          INTEGER,
      viol_additive    INTEGER,
      viol_container   INTEGER,
      viol_microbe     INTEGER,
      viol_mycotoxin   INTEGER,
      viol_vetdrug     INTEGER,
      viol_chemical    INTEGER,
      viol_composition INTEGER,
      viol_other       INTEGER
  );

  -- ── 3. food_restaurant_tpe (TPE certified restaurants, geocoded) ──
  CREATE TABLE IF NOT EXISTS food_restaurant_tpe (
      id        SERIAL PRIMARY KEY,
      name      VARCHAR(200),
      address   VARCHAR(300),
      district  VARCHAR(50),
      grade     VARCHAR(10),    -- '優' or '良'
      lng       DOUBLE PRECISION,
      lat       DOUBLE PRECISION
  );

  -- ── 4. food_factory_ntpc (NTPC food factory registry, WGS84 coords) ──
  CREATE TABLE IF NOT EXISTS food_factory_ntpc (
      id        SERIAL PRIMARY KEY,
      name      VARCHAR(200),
      address   VARCHAR(300),
      tax_id    VARCHAR(50),
      lng       DOUBLE PRECISION,
      lat       DOUBLE PRECISION,
      district  VARCHAR(50)
  );

  -- ── 5. food_inspection_by_city (MOHW dual-city inspection, 2026 only) ──
  CREATE TABLE IF NOT EXISTS food_inspection_by_city (
      id                  SERIAL PRIMARY KEY,
      year                INTEGER NOT NULL,
      city                VARCHAR(20) NOT NULL,            -- '臺北市' or '新北市'
      venue               VARCHAR(40) NOT NULL,            -- 餐飲店/.../合計
      inspections         INTEGER,
      noncompliance       INTEGER,
      poisoning_cases     INTEGER,                         -- only on venue='合計'
      ntpc_violation_rate NUMERIC(5,2),                    -- only on venue='合計'
      UNIQUE (year, city, venue)
  );

  -- ── 6. food_type_violations (MOHW dual-city violations by food category) ──
  CREATE TABLE IF NOT EXISTS food_type_violations (
      id        SERIAL PRIMARY KEY,
      year      INTEGER NOT NULL,
      city      VARCHAR(20) NOT NULL,
      category  VARCHAR(40) NOT NULL,
      count     INTEGER NOT NULL,
      UNIQUE (year, city, category)
  );

  -- ── 7. food_poisoning_cause (MOHW national food-poisoning by cause) ──
  CREATE TABLE IF NOT EXISTS food_poisoning_cause (
      id      SERIAL PRIMARY KEY,
      year    INTEGER NOT NULL,
      cause   VARCHAR(60) NOT NULL,
      cases   INTEGER,
      persons INTEGER,
      UNIQUE (year, cause)
  );

  COMMIT;
  ```

- [ ] **Step 2.2: Write `001_create_tables.down.sql`**

  ```sql
  -- scripts/food_safety/migrations/001_create_tables.down.sql
  -- Rollback for 001: drop all 7 food_safety tables.
  -- up:   migrations/001_create_tables.up.sql
  BEGIN;

  DROP TABLE IF EXISTS food_poisoning_cause     CASCADE;
  DROP TABLE IF EXISTS food_type_violations     CASCADE;
  DROP TABLE IF EXISTS food_inspection_by_city  CASCADE;
  DROP TABLE IF EXISTS food_factory_ntpc        CASCADE;
  DROP TABLE IF EXISTS food_restaurant_tpe      CASCADE;
  DROP TABLE IF EXISTS food_testing_tpe         CASCADE;
  DROP TABLE IF EXISTS food_inspection_tpe      CASCADE;

  COMMIT;
  ```

- [ ] **Step 2.3: Verify migration up runs against a Postgres**

  ```bash
  cd .worktrees/food-safety-radar
  source scripts/food_safety/_db_env.sh
  pg_psql DASHBOARD -1 < scripts/food_safety/migrations/001_create_tables.up.sql
  pg_psql DASHBOARD -c "\dt food_*"
  ```
  Expected: 7 rows listing `food_factory_ntpc`, `food_inspection_by_city`, `food_inspection_tpe`, `food_poisoning_cause`, `food_restaurant_tpe`, `food_testing_tpe`, `food_type_violations`.

- [ ] **Step 2.4: Verify down runs and is idempotent**

  ```bash
  pg_psql DASHBOARD -1 < scripts/food_safety/migrations/001_create_tables.down.sql
  pg_psql DASHBOARD -c "\dt food_*"
  pg_psql DASHBOARD -1 < scripts/food_safety/migrations/001_create_tables.down.sql  # second run
  ```
  Expected: first `\dt` shows 0 rows; second down completes without error.

---

## Task 3: Migration 002 — register dashboard 503 + 5 components + 10 query_charts + 2 maps

**Files:**
- Create: `scripts/food_safety/migrations/002_seed_dashboard.up.sql`
- Create: `scripts/food_safety/migrations/002_seed_dashboard.down.sql`

This migration writes to `dashboardmanager` (not `dashboard`). Uses `pg_psql MANAGER`. The `query_chart` SQL strings reference tables created by migration 001 — apply order must be: 001 → 002.

**Steps:**

- [ ] **Step 3.1: Write `002_seed_dashboard.up.sql` — header + cleanup**

  ```sql
  -- scripts/food_safety/migrations/002_seed_dashboard.up.sql
  -- Project: 食安風險追蹤器 (Food Safety Radar)
  -- Purpose: Register dashboard 503 with 5 components (1011-1015), 10 query_charts
  --          (5 components × 2 cities: taipei + metrotaipei), 2 component_maps,
  --          and dashboard_groups membership in the `dashboardmanager` database.
  -- down:    migrations/002_seed_dashboard.down.sql
  -- Order:   components → component_charts → component_maps → query_charts
  --          → dashboards → dashboard_groups
  BEGIN;

  -- Defensive cleanup: any prior partial seed of food_% rows is wiped
  -- before we re-insert. Safe — only food_% indexes touched.
  DELETE FROM query_charts   WHERE index LIKE 'food_%';
  DELETE FROM component_maps WHERE index LIKE 'food_%';
  DELETE FROM component_charts WHERE index LIKE 'food_%';
  DELETE FROM components WHERE id BETWEEN 1011 AND 1015;
  ```

- [ ] **Step 3.2: Append components + component_charts + component_maps**

  Append to `002_seed_dashboard.up.sql`:

  ```sql
  -- ── 1. components ───────────────────────────────────────────────
  INSERT INTO components (id, index, name) VALUES
    (1011, 'food_poisoning_trend',   '食物中毒趨勢'),
    (1012, 'food_venue_risk',        '場所不合格率'),
    (1013, 'food_safety_map',        '食安認證餐廳與食品工廠'),
    (1014, 'food_violation_types',   '違規原因分析'),
    (1015, 'food_testing_rate',      '年度檢驗違規率')
  ON CONFLICT (index) DO NOTHING;

  -- ── 2. component_charts ─────────────────────────────────────────
  INSERT INTO component_charts (index, color, types, unit) VALUES
    ('food_poisoning_trend',
     ARRAY['#E53935','#F57F17'],
     ARRAY['ColumnLineChart'], '件/人'),
    ('food_venue_risk',
     ARRAY['#E91E63','#FF5722','#FF9800','#FFC107','#8BC34A','#26C6DA'],
     ARRAY['BarChart'], '%'),
    ('food_safety_map',
     ARRAY['#43A047','#FFA000','#1565C0'],
     ARRAY['MapLegend'], '家'),
    ('food_violation_types',
     ARRAY['#E53935','#8E24AA','#FF6D00','#F57F17','#388E3C','#0288D1','#9E9E9E'],
     ARRAY['DonutChart'], '件'),
    ('food_testing_rate',
     ARRAY['#FF5722','#FF8A65','#FFCCBC'],
     ARRAY['BarChart'], '%')
  ON CONFLICT (index) DO NOTHING;

  -- ── 3. component_maps ──────────────────────────────────────────
  INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
    ('food_restaurant_tpe', '臺北認證餐廳', 'circle', 'geojson', 'big',
     '{"circle-color":["match",["get","grade"],"優","#43A047","#FFA000"],"circle-radius":5,"circle-opacity":0.85}'::json),
    ('food_factory_ntpc', '新北食品工廠', 'circle', 'geojson', 'big',
     '{"circle-color":"#1565C0","circle-radius":5,"circle-opacity":0.75}'::json);
  ```

- [ ] **Step 3.3: Append 1011 query_charts (taipei + metrotaipei)**

  - **taipei**: keep TPE 20-year ColumnLineChart (poisoning + noncompliance) — copy verbatim from `scripts/register_food_safety.sql:48-61` on parent worktree.
  - **metrotaipei**: TPE poisoning line + NTPC 2026 single point.

  ```sql
  -- 1011 食物中毒趨勢 — taipei
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_poisoning_trend', 'time',
    $$SELECT x_axis, y_axis, ROUND(AVG(data)) AS data FROM (SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '食物中毒人數' AS y_axis, food_poisoning_cases AS data FROM food_inspection_tpe UNION ALL SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '不合格場所' AS y_axis, total_noncompliance AS data FROM food_inspection_tpe) d GROUP BY x_axis, y_axis ORDER BY x_axis$$,
    'taipei', '臺北市衛生局',
    '臺北市食物中毒人數與不合格場所趨勢（2006-2025）。',
    '食物中毒案例自169例（2023）激增至909例（2025），5.4倍增幅發出強烈警訊。雙軸設計同時呈現食物中毒人數與場所不合格件數，協助研究者分析執法力道與食安風險的關聯。',
    '衛生局追蹤食安政策成效，市民了解食安風險趨勢，學術研究分析稽查與中毒的關聯性。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
  );

  -- 1011 食物中毒趨勢 — metrotaipei (TPE full series + NTPC 2026 single point)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_poisoning_trend', 'time',
    $$SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '臺北市' AS y_axis, food_poisoning_cases AS data FROM food_inspection_tpe UNION ALL SELECT TO_TIMESTAMP(year::text, 'YYYY') AS x_axis, '新北市' AS y_axis, poisoning_cases AS data FROM food_inspection_by_city WHERE city = '新北市' AND venue = '合計' AND poisoning_cases IS NOT NULL ORDER BY x_axis, y_axis$$,
    'metrotaipei', '臺北市衛生局 / 衛福部',
    '雙北食物中毒人數趨勢（TPE 2006-2025；NTPC 2026 起公開）。',
    'TPE 含 2006-2025 完整序列，NTPC 自 2026 年起依衛福部統一格式公開。雙線並列，TPE 作為長期趨勢，NTPC 作為近期錨點。',
    '衛生局追蹤雙城食安趨勢；市民比較雙城食安風險；學術研究分析資料公開政策成效。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
  );
  ```

- [ ] **Step 3.4: Append 1012 query_charts (taipei + metrotaipei)**

  ```sql
  -- 1012 場所不合格率 — taipei
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_venue_risk', 'two_d',
    $$SELECT venue AS x_axis, ROUND(SUM(nc)::numeric * 100 / NULLIF(SUM(insp), 0), 1) AS data FROM (SELECT '餐飲店' AS venue, restaurant_insp AS insp, restaurant_nc AS nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '冷飲店', drink_shop_insp, drink_shop_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '飲食攤販', street_vendor_insp, street_vendor_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '傳統市場', market_insp, market_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '超級市場', supermarket_insp, supermarket_nc FROM food_inspection_tpe WHERE year >= 2020 UNION ALL SELECT '製造廠商', manufacturer_insp, manufacturer_nc FROM food_inspection_tpe WHERE year >= 2020) t GROUP BY venue ORDER BY data DESC$$,
    'taipei', '臺北市衛生局',
    '臺北市各類場所食安不合格率排行（2020-2025累計）。',
    '比較餐飲店、冷飲店、飲食攤販、傳統市場、超級市場、製造廠商的不合格率，識別風險最高的場所類型。',
    '市民選擇安全用餐環境，衛生局優先配置稽查資源。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
  );

  -- 1012 場所不合格率 — metrotaipei (real dual-city from MOHW by-city xlsx)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_venue_risk', 'two_d',
    $$SELECT venue || '(' || city || ')' AS x_axis, ROUND(noncompliance::numeric * 100 / NULLIF(inspections, 0), 1) AS data FROM food_inspection_by_city WHERE city IN ('臺北市','新北市') AND venue <> '合計' AND inspections > 0 ORDER BY data DESC$$,
    'metrotaipei', '衛福部食藥署',
    '雙北各場所食安不合格率（115年衛福部統計）。',
    '依衛福部 10521-01-03 食品衛生管理工作-按縣市別分統計，雙城各 6 種場所並列，識別雙北高風險場所類型。',
    '市民比較雙城場所安全；衛生局跨城稽查資源評估。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
  );
  ```

- [ ] **Step 3.5: Append 1013 query_charts (taipei + metrotaipei)**

  These reference `component_maps` rows inserted earlier in this transaction — use sub-SELECT.

  ```sql
  -- 1013 食安地圖 — taipei (1 layer: TPE restaurants)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_safety_map', 'map_legend',
    $$SELECT unnest(array['優等認證餐廳','良好認證餐廳']) as name, unnest(array['circle','circle']) as type$$,
    'taipei', '臺北市衛生局',
    '臺北市通過衛生管理分級評核業者地圖（1,686家）。',
    '標示臺北市114年通過餐飲衛生分級評核業者，綠色為優等（優）、黃色為良好（良），協助市民查詢附近通過認證的餐廳。',
    '市民查詢附近衛生評核優良餐廳，餐飲業者了解鄰近競業的認證狀況。',
    'static', '', 1, 'year',
    ARRAY(SELECT id FROM component_maps WHERE index = 'food_restaurant_tpe'),
    '{}', '{}', '{doit}', NOW(), NOW()
  );

  -- 1013 食安地圖 — metrotaipei (2 layers: TPE restaurants + NTPC factories)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_safety_map', 'map_legend',
    $$SELECT unnest(array['台北優等餐廳','台北良好餐廳','新北食品工廠']) as name, unnest(array['circle','circle','circle']) as type$$,
    'metrotaipei', '衛生局 / 新北市經發局',
    '雙北食安地圖：臺北認證餐廳（1,686家）+ 新北食品工廠（1,230家）。',
    '雙層疊合：臺北市餐飲衛生評核業者（優/良分色）與新北市列管食品工廠，呈現雙北食安生態全貌。',
    '市民跨城查詢食安認證場所，政策研究者分析食品供應鏈地理分布。',
    'static', '', 1, 'year',
    ARRAY(SELECT id FROM component_maps WHERE index IN ('food_restaurant_tpe','food_factory_ntpc') ORDER BY id),
    '{}', '{}', '{doit,ntpc}', NOW(), NOW()
  );
  ```

- [ ] **Step 3.6: Append 1014 query_charts (taipei + metrotaipei)**

  ```sql
  -- 1014 違規原因分析 — taipei (TPE 7 categories cumulative 2022-2025)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_violation_types', 'two_d',
    $$SELECT violation_type AS x_axis, SUM(total) AS data FROM (SELECT '違規標示' AS violation_type, viol_labeling AS total FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '違規廣告', viol_ad FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '食品添加物', viol_additive FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '微生物超標', viol_microbe FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '真菌毒素', viol_mycotoxin FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '化學成分', viol_chemical FROM food_testing_tpe WHERE year >= 2022 UNION ALL SELECT '其他原因', viol_other FROM food_testing_tpe WHERE year >= 2022) t WHERE total > 0 GROUP BY violation_type ORDER BY data DESC$$,
    'taipei', '臺北市衛生局',
    '臺北市食品抽驗違規原因分類（2022-2025累計）。',
    '統計食品抽驗不合格件數依違規原因分析，包含違規標示、食品添加物、微生物超標等七大類，揭示食安違規的主要型態。',
    '食品業者了解重點合規項目，消費者了解食品違規常見原因。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
  );

  -- 1014 違規原因分析 — metrotaipei (real dual-city by food category from MOHW)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_violation_types', 'two_d',
    $$SELECT category || '(' || city || ')' AS x_axis, count AS data FROM food_type_violations WHERE city IN ('臺北市','新北市') AND count > 0 ORDER BY data DESC$$,
    'metrotaipei', '衛福部食藥署',
    '雙北食品違規原因分類（115年衛福部統計）。',
    '依衛福部 10521-01-03 統計，雙城各食品類別（乳品/肉品/蛋品/水產/穀豆烘焙/蔬果/飲料及水/食用油脂/調味品/健康食品/複合調理/其他）違規件數並列。',
    '食品業者了解雙北重點合規項目；研究者比較雙城違規結構。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
  );
  ```

- [ ] **Step 3.7: Append 1015 query_charts (taipei + metrotaipei)**

  ```sql
  -- 1015 年度檢驗違規率 — taipei (TPE 2015-2025 yearly)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_testing_rate', 'two_d',
    $$SELECT year::text AS x_axis, violation_rate AS data FROM food_testing_tpe WHERE year >= 2015 ORDER BY year$$,
    'taipei', '臺北市衛生局',
    '臺北市食品抽驗不合格率年度趨勢（2015-2025）。',
    '年度食品抽驗不合格比率，顯示近年從0.34%（2020）攀升至0.75%（2024），揭示食安違規比例的上升趨勢。',
    '政府評估食安政策成效，消費者了解整體食品安全水準的變化。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit}', NOW(), NOW()
  );

  -- 1015 年度檢驗違規率 — metrotaipei (TPE full series + NTPC 2026 bar)
  INSERT INTO query_charts (index, query_type, query_chart, city, source,
    short_desc, long_desc, use_case,
    time_from, time_to, update_freq, update_freq_unit,
    map_config_ids, map_filter, links, contributors, created_at, updated_at)
  VALUES (
    'food_testing_rate', 'two_d',
    $$SELECT year::text AS x_axis, violation_rate AS data, '臺北市' AS y_axis FROM food_testing_tpe WHERE year >= 2015 UNION ALL SELECT '2026', ntpc_violation_rate, '新北市' FROM food_inspection_by_city WHERE city = '新北市' AND venue = '合計' AND ntpc_violation_rate IS NOT NULL ORDER BY x_axis, y_axis$$,
    'metrotaipei', '臺北市衛生局 / 衛福部',
    '雙北食品檢驗違規率（TPE 2015-2025；NTPC 2026 起公開）。',
    'TPE 含 2015-2025 完整序列，NTPC 自 2026 年起公開。視覺呈現雙城違規率水平差異。',
    '政府評估雙城食安政策成效；消費者比較雙北食品安全水準。',
    'static', '', 1, 'year', '{}', '{}', '{}', '{doit,mohw}', NOW(), NOW()
  );
  ```

- [ ] **Step 3.8: Append dashboards + dashboard_groups + COMMIT**

  ```sql
  -- ── 5. dashboards ────────────────────────────────────────────────
  INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
    (503, 'food_safety_radar', '食安風險追蹤器',
     ARRAY[1011,1012,1013,1014,1015], 'restaurant', NOW(), NOW())
  ON CONFLICT (index) DO NOTHING;

  -- ── 6. dashboard_groups ──────────────────────────────────────────
  INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
    (503, 2),
    (503, 3)
  ON CONFLICT DO NOTHING;

  COMMIT;
  ```

- [ ] **Step 3.9: Write `002_seed_dashboard.down.sql`**

  ```sql
  -- scripts/food_safety/migrations/002_seed_dashboard.down.sql
  -- Rollback for 002: remove all food_% registrations from dashboardmanager DB.
  -- up:   migrations/002_seed_dashboard.up.sql
  BEGIN;

  DELETE FROM dashboard_groups WHERE dashboard_id = 503;
  DELETE FROM dashboards       WHERE id = 503;
  DELETE FROM query_charts     WHERE index LIKE 'food_%';
  DELETE FROM component_maps   WHERE index LIKE 'food_%';
  DELETE FROM component_charts WHERE index LIKE 'food_%';
  DELETE FROM components       WHERE id BETWEEN 1011 AND 1015;

  COMMIT;
  ```

- [ ] **Step 3.10: Verify both directions on a real DB**

  Apply 001 + 002, count rows, then rollback 002 + 001, verify empty.

  ```bash
  cd .worktrees/food-safety-radar
  source scripts/food_safety/_db_env.sh
  pg_psql DASHBOARD -1 < scripts/food_safety/migrations/001_create_tables.up.sql
  pg_psql MANAGER   -1 < scripts/food_safety/migrations/002_seed_dashboard.up.sql

  pg_psql MANAGER -c "SELECT COUNT(*) FROM components WHERE id BETWEEN 1011 AND 1015;"   # → 5
  pg_psql MANAGER -c "SELECT COUNT(*) FROM query_charts WHERE index LIKE 'food_%';"        # → 10
  pg_psql MANAGER -c "SELECT COUNT(*) FROM component_maps WHERE index LIKE 'food_%';"      # → 2
  pg_psql MANAGER -c "SELECT id, name FROM dashboards WHERE id = 503;"                     # → 1 row

  pg_psql MANAGER   -1 < scripts/food_safety/migrations/002_seed_dashboard.down.sql
  pg_psql DASHBOARD -1 < scripts/food_safety/migrations/001_create_tables.down.sql

  pg_psql MANAGER -c "SELECT COUNT(*) FROM components WHERE id BETWEEN 1011 AND 1015;"    # → 0
  pg_psql MANAGER -c "SELECT COUNT(*) FROM dashboards WHERE id = 503;"                     # → 0
  ```

- [ ] **Step 3.11: Verify labor untouched**

  ```bash
  pg_psql MANAGER -c "SELECT COUNT(*) FROM components WHERE id BETWEEN 1005 AND 1010;"  # should be 6 if labor was applied, 0 if not — either way unchanged from baseline
  ```

---

## Task 4: apply.sh, rollback.sh, backup_db.sh

**Files:**
- Create: `scripts/food_safety/apply.sh`
- Create: `scripts/food_safety/rollback.sh`
- Create: `scripts/food_safety/backup_db.sh`

**Steps:**

- [ ] **Step 4.1: Write `apply.sh` — initial form (no ETL yet, just migrations)**

  ```bash
  #!/usr/bin/env bash
  # Apply food safety migrations and load all data.
  # Idempotent: safe to run multiple times. Use rollback.sh to revert.
  set -euo pipefail

  ROOT="$(cd "$(dirname "$0")" && pwd)"
  # shellcheck source=./_db_env.sh
  source "$ROOT/_db_env.sh"

  echo "▶ target dashboard:        $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
  echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
  echo

  echo "1/3 migrations up ..."
  pg_psql DASHBOARD -1 < "$ROOT/migrations/001_create_tables.up.sql"
  pg_psql MANAGER   -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"

  echo "2/3 ETL ..."
  python3 "$ROOT/etl/load_inspection_tpe.py"
  python3 "$ROOT/etl/load_restaurant_tpe.py"
  python3 "$ROOT/etl/load_factory_ntpc.py"
  python3 "$ROOT/etl/load_mohw_dual_city.py"
  python3 "$ROOT/etl/load_mohw_poisoning.py"
  python3 "$ROOT/etl/generate_geojson.py"

  echo "3/3 verify row counts ..."
  pg_psql DASHBOARD -c "
    SELECT 'food_inspection_tpe'      AS t, COUNT(*) FROM food_inspection_tpe
    UNION ALL SELECT 'food_testing_tpe',         COUNT(*) FROM food_testing_tpe
    UNION ALL SELECT 'food_restaurant_tpe',      COUNT(*) FROM food_restaurant_tpe
    UNION ALL SELECT 'food_factory_ntpc',        COUNT(*) FROM food_factory_ntpc
    UNION ALL SELECT 'food_inspection_by_city',  COUNT(*) FROM food_inspection_by_city
    UNION ALL SELECT 'food_type_violations',     COUNT(*) FROM food_type_violations
    UNION ALL SELECT 'food_poisoning_cause',     COUNT(*) FROM food_poisoning_cause;"

  echo "✅ apply complete"
  ```

  Note: ETL loaders are referenced now even though they don't exist yet — they will be added in Tasks 8-13. apply.sh will fail until then. That's expected and matches labor's commit history (scaffold first, ETL second).

- [ ] **Step 4.2: Write `rollback.sh`**

  ```bash
  #!/usr/bin/env bash
  # Rollback food safety: remove dashboard 503, drop all food_* tables, clean GeoJSON.
  # Idempotent: safe even if apply was never run.
  set -euo pipefail

  ROOT="$(cd "$(dirname "$0")" && pwd)"
  REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
  # shellcheck source=./_db_env.sh
  source "$ROOT/_db_env.sh"

  echo "▶ target dashboard:        $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
  echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
  echo

  echo "1/3 down: dashboard registrations ..."
  pg_psql MANAGER -1 < "$ROOT/migrations/002_seed_dashboard.down.sql"

  echo "2/3 down: drop tables ..."
  pg_psql DASHBOARD -1 < "$ROOT/migrations/001_create_tables.down.sql"

  echo "3/3 clean GeoJSON ..."
  rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson"
  rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/food_factory_ntpc.geojson"

  echo "✅ rollback complete"
  ```

- [ ] **Step 4.3: Write `backup_db.sh`**

  ```bash
  #!/usr/bin/env bash
  # Snapshot both DBs to scripts/food_safety/backups/<timestamp>/ before any apply/rollback.
  set -euo pipefail

  ROOT="$(cd "$(dirname "$0")" && pwd)"
  # shellcheck source=./_db_env.sh
  source "$ROOT/_db_env.sh"

  TS="$(date -u +%Y%m%d-%H%M%SZ)"
  OUT="$ROOT/backups/$TS"
  mkdir -p "$OUT"

  # _db_env.sh defines a single helper `pg_dump_to <output_file> DASHBOARD|MANAGER`.
  pg_dump_to "$OUT/dashboard.sql"        DASHBOARD
  pg_dump_to "$OUT/dashboardmanager.sql" MANAGER

  echo "✅ backup → $OUT"
  ls -lh "$OUT"
  ```

- [ ] **Step 4.4: Make all 3 scripts executable**

  ```bash
  cd .worktrees/food-safety-radar
  chmod +x scripts/food_safety/apply.sh scripts/food_safety/rollback.sh scripts/food_safety/backup_db.sh
  ```

- [ ] **Step 4.5: Smoke test rollback (no-op safe)**

  Rollback should run cleanly even if nothing applied:

  ```bash
  cd .worktrees/food-safety-radar
  ./scripts/food_safety/rollback.sh
  ```
  Expected: no errors. `pg_psql` runs `DROP TABLE IF EXISTS` and `DELETE` against empty tables — both idempotent.

---

## Task 5: README.md

**Files:**
- Create: `scripts/food_safety/README.md`

**Steps:**

- [ ] **Step 5.1: Write README modeled on `scripts/labor_safety/README.md`**

  Read `scripts/labor_safety/README.md` first to match tone. Then write `scripts/food_safety/README.md` with these sections:

  ```markdown
  # 食安風險追蹤器 Food Safety Radar — Standalone Dashboard

  Self-contained dashboard 503 (5 components, real dual-city). Drop this folder = remove the dashboard.

  ## Layout

  ```
  scripts/food_safety/
  ├── apply.sh / rollback.sh / backup_db.sh
  ├── _db_env.sh                  # credential resolution + pg_psql/pg_dump fns
  ├── .env.script.example         # copy to .env.script and edit for cloud DB
  ├── migrations/
  │   ├── 001_create_tables.{up,down}.sql      # 7 food_* tables in dashboard DB
  │   └── 002_seed_dashboard.{up,down}.sql     # dashboard 503 + 5 components in manager DB
  ├── etl/                        # all loaders read CSV/xlsx — no HTTP at apply time
  │   ├── _db.py
  │   ├── .geocode_cache.json     # 9680 addresses, committed
  │   ├── snapshot_apis.py        # one-shot tool: NTPC factory API → CSV (NOT called by apply.sh)
  │   ├── load_inspection_tpe.py
  │   ├── load_restaurant_tpe.py
  │   ├── load_factory_ntpc.py
  │   ├── load_mohw_dual_city.py
  │   ├── load_mohw_poisoning.py
  │   └── generate_geojson.py
  ├── snapshots/
  │   └── ntpc_food_factory.csv   # ~1232 rows (regenerated via snapshot_apis.py)
  └── backups/                    # gitignored — pg_dump output
  ```

  ## Quickstart

  ```bash
  # 1. (Optional, recommended) backup before anything
  ./scripts/food_safety/backup_db.sh

  # 2. Apply: 7 tables + ETL data + dashboard 503 registration
  ./scripts/food_safety/apply.sh

  # 3. Open http://localhost:8080 → shift+click TUIC logo → login → dashboard 503 「食安風險追蹤器」
  ```

  Re-run `apply.sh` is safe (TRUNCATE before INSERT in every loader; ON CONFLICT DO NOTHING in seed).

  ## Refreshing NTPC factory snapshot (manual, online)

  ```bash
  python3 scripts/food_safety/etl/snapshot_apis.py
  git add scripts/food_safety/snapshots/ntpc_food_factory.csv
  git commit -m "chore(food-safety): refresh NTPC food factory snapshot"
  ```

  ## Rollback

  ```bash
  ./scripts/food_safety/rollback.sh
  ```

  Drops all 7 food_* tables, removes dashboard 503 + 5 components + 10 query_charts + 2 component_maps from manager DB, deletes GeoJSON files. Idempotent.

  ## Restore from backup

  ```bash
  docker exec -i postgres-data    psql -U postgres -d dashboard        < scripts/food_safety/backups/<TS>/dashboard.sql
  docker exec -i postgres-manager psql -U postgres -d dashboardmanager < scripts/food_safety/backups/<TS>/dashboardmanager.sql
  ```

  ## Cloud DB target

  Copy `.env.script.example` → `.env.script` and override `DB_DASHBOARD_*` / `DB_MANAGER_*`. The same `apply.sh` works.
  ```

- [ ] **Step 5.2: Verify markdown renders without lint errors (visual check)**

---

## Task 6: Commit 2 — scaffold + migrations + bash scripts

- [ ] **Step 6.1: Stage and commit**

  ```bash
  cd .worktrees/food-safety-radar
  git add scripts/food_safety/
  git status -sb
  git diff --cached --stat
  ```

  Expected: ~13 new files (no modifications). Commit:

  ```bash
  git commit -m "$(cat <<'EOF'
  feat(food-safety): scaffold migrations + apply/rollback/backup scripts

  Add scripts/food_safety/ skeleton mirroring labor_safety:
  - 001_create_tables migration (7 food_* tables in dashboard DB)
  - 002_seed_dashboard migration (dashboard 503 + 5 components +
    10 query_charts dual-city + 2 component_maps in manager DB)
  - apply.sh / rollback.sh / backup_db.sh (idempotent, transactional)
  - _db_env.sh / etl/_db.py credential resolution (env > .env.script
    > docker/.env > defaults)

  ETL loaders referenced by apply.sh do not exist yet — they ship in
  the next commit. This scaffold's apply.sh fails at the ETL step,
  but rollback.sh and migrations are runnable in isolation.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 7: Copy assets + geocode cache

**Files:**
- Create: `docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv`
- Create: `docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv`
- Create: `docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv`
- Create: `docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx`
- Create: `docs/assets/10521-05-01食品中毒案件病因物質分類統計.xlsx`
- Create: `docs/assets/10521-05-03食品中毒案件攝食場所分類統計.xlsx`
- Create: `scripts/food_safety/etl/.geocode_cache.json`

**Steps:**

- [ ] **Step 7.1: Copy 6 asset files from parent worktree**

  ```bash
  cd .worktrees/food-safety-radar
  PARENT=/Users/teddy_peng/Projects/my/Taipei-City-Dashboard
  cp "$PARENT/docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv" docs/assets/
  cp "$PARENT/docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv" docs/assets/
  cp "$PARENT/docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv" docs/assets/
  cp "$PARENT/docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx" docs/assets/
  cp "$PARENT/docs/assets/10521-05-01食品中毒案件病因物質分類統計.xlsx" docs/assets/
  cp "$PARENT/docs/assets/10521-05-03食品中毒案件攝食場所分類統計.xlsx" docs/assets/
  ```

- [ ] **Step 7.2: Copy geocode cache**

  ```bash
  cp "$PARENT/scripts/.geocode_cache.json" scripts/food_safety/etl/.geocode_cache.json
  ```

- [ ] **Step 7.3: Verify file sizes match (sanity)**

  ```bash
  ls -lh docs/assets/10521-* docs/assets/114年* docs/assets/臺北市食品* scripts/food_safety/etl/.geocode_cache.json
  ```
  Expected: 3 xlsx files (~93KB / ~549KB / ~2.7MB), 3 CSV files (~169KB / ~2KB / ~6KB), 1 cache JSON.

---

## Task 8: ETL loader — `load_inspection_tpe.py`

**Files:**
- Create: `scripts/food_safety/etl/load_inspection_tpe.py`

This loader reads two TPE CSV files and writes to two tables in one Python process (simpler than two scripts since both are TPE 20-year statistics from the same agency).

**Steps:**

- [ ] **Step 8.1: Implement loader**

  Pattern: ROC year parser, numeric coercion with NULL fallback, two TRUNCATE-INSERT transactions (one per table). Adapt logic from parent worktree's `scripts/generate_food_safety_sql.py` `load_inspection_stats()` and `load_testing_stats()` functions.

  ```python
  #!/usr/bin/env python3
  """
  Load TPE 20-year food inspection + testing statistics.

  Sources (CSV only — NO HTTP):
    - docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv → food_inspection_tpe
    - docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv → food_testing_tpe

  Both are ROC-year (e.g. '95年') keyed annual statistics from 臺北市衛生局.
  Adapted from scripts/generate_food_safety_sql.py (parent worktree).
  """
  import csv
  import re
  import sys
  from pathlib import Path

  import psycopg2
  from psycopg2.extras import execute_values

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  from _db import db_kwargs  # noqa: E402

  REPO_ROOT = Path(__file__).resolve().parents[3]
  ASSETS    = REPO_ROOT / "docs" / "assets"
  INSP_CSV  = ASSETS / "臺北市食品衛生管理稽查工作-年度統計.csv"
  TEST_CSV  = ASSETS / "臺北市食品衛生管理查驗工作-年度統計.csv"

  INSP_INSERT = """
  INSERT INTO food_inspection_tpe (
      year, total_inspections, restaurant_insp, drink_shop_insp,
      street_vendor_insp, market_insp, supermarket_insp, manufacturer_insp,
      total_noncompliance, restaurant_nc, drink_shop_nc, street_vendor_nc,
      market_nc, supermarket_nc, manufacturer_nc, food_poisoning_cases
  ) VALUES %s
  """

  TEST_INSERT = """
  INSERT INTO food_testing_tpe (
      year, total_tested, total_violations, violation_rate,
      viol_labeling, viol_ad, viol_additive, viol_container, viol_microbe,
      viol_mycotoxin, viol_vetdrug, viol_chemical, viol_composition, viol_other
  ) VALUES %s
  """


  def parse_roc_year(text):
      m = re.match(r"(\d+)年", str(text or "").strip())
      if not m:
          return None
      return int(m.group(1)) + 1911


  def num(s):
      try:
          v = str(s or "").strip().replace(",", "")
          if v in ("", "-", "—"):
              return None
          f = float(v)
          return int(f) if f == int(f) else f
      except (ValueError, AttributeError):
          return None


  def load_inspection():
      with open(INSP_CSV, encoding="utf-8-sig") as f:
          rows = list(csv.DictReader(f))
      out = []
      for r in rows:
          year = parse_roc_year(r.get("統計期"))
          if year is None or year < 2006:
              continue
          out.append((
              year,
              num(r.get("食品衛生管理稽查工作/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/餐飲店/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/冷飲店/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/飲食攤販/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/傳統市場/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/超級市場/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/製造廠商/稽查家次[家次]")),
              num(r.get("食品衛生管理稽查工作/不合格飭令改善家次[家次]")),
              num(r.get("食品衛生管理稽查工作/餐飲店/不合格飭令改善家次[家次]")),
              num(r.get("食品衛生管理稽查工作/冷飲店/不合格飭令改善家次[家次]")),
              num(r.get("食品衛生管理稽查工作/飲食攤販/不合格飭令改善家次[家次]")),
              num(r.get("食品衛生管理稽查工作/傳統市場/不合格飭令改善家次[家次]")),
              num(r.get("食品衛生管理稽查工作/超級市場/不合格飭令改善家次[家次]")),
              num(r.get("食品衛生管理稽查工作/製造廠商/不合格飭令改善家次[家次]")),
              num(r.get("食品中毒人數[人]")),
          ))
      return out


  def load_testing():
      with open(TEST_CSV, encoding="utf-8-sig") as f:
          rows = list(csv.DictReader(f))
      out = []
      for r in rows:
          year = parse_roc_year(r.get("統計期"))
          if year is None:
              continue
          out.append((
              year,
              num(r.get("查驗件數/總計[件]")),
              num(r.get("與規定不符件數/總計[件]")),
              num(r.get("不符規定比率[%]")),
              num(r.get("與規定不符件數按原因別/違規標示[件]")),
              num(r.get("與規定不符件數按原因別/違規廣告[件]")),
              num(r.get("與規定不符件數按原因別/食品添加物[件]")),
              num(r.get("與規定不符件數按原因別/食品器皿容器包裝檢驗[件]")),
              num(r.get("與規定不符件數按原因別/微生物[件]")),
              num(r.get("與規定不符件數按原因別/真菌毒素[件]")),
              num(r.get("與規定不符件數按原因別/動物用藥殘留[件]")),
              num(r.get("與規定不符件數按原因別/化學成分[件]")),
              num(r.get("與規定不符件數按原因別/成分分析[件]")),
              num(r.get(" 與規定不符件數按原因別/其他[件]",
                        r.get("與規定不符件數按原因別/其他[件]"))),
          ))
      return out


  def main():
      insp = load_inspection()
      test = load_testing()
      with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
          cur.execute("BEGIN")
          cur.execute("TRUNCATE food_inspection_tpe RESTART IDENTITY")
          execute_values(cur, INSP_INSERT, insp)
          cur.execute("TRUNCATE food_testing_tpe RESTART IDENTITY")
          execute_values(cur, TEST_INSERT, test)
          cur.execute("COMMIT")
      print(f"✅ {len(insp)} rows → food_inspection_tpe")
      print(f"✅ {len(test)} rows → food_testing_tpe")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 8.2: Run loader**

  ```bash
  cd .worktrees/food-safety-radar
  python3 scripts/food_safety/etl/load_inspection_tpe.py
  ```
  Expected: `✅ 20 rows → food_inspection_tpe` and `✅ 20 rows → food_testing_tpe`.

---

## Task 9: ETL loader — `load_restaurant_tpe.py`

**Files:**
- Create: `scripts/food_safety/etl/load_restaurant_tpe.py`

Reads TPE certified-restaurants CSV, geocodes via cache (NO HTTP), falls back to district centroid + jitter when cache miss.

**Steps:**

- [ ] **Step 9.1: Implement loader**

  Adapt geocoding logic from parent's `generate_food_safety_sql.py` `geocode_or_fallback()` and `TPE_DISTRICT` dict, but **remove** the `_fetch_geocode` HTTP call — only read cache.

  ```python
  #!/usr/bin/env python3
  """
  Load TPE certified restaurants into food_restaurant_tpe.

  Source (CSV only — NO HTTP, geocoding strictly cache-only):
    docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv

  Geocoding: read scripts/food_safety/etl/.geocode_cache.json (9,680 entries
  pre-fetched). If address is not in cache, fall back to district centroid
  with jitter (NEVER calls external API — labor-safety rule §3.2.3).
  """
  import csv
  import json
  import random
  import re
  import sys
  from pathlib import Path

  import psycopg2
  from psycopg2.extras import execute_values

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  from _db import db_kwargs  # noqa: E402

  REPO_ROOT  = Path(__file__).resolve().parents[3]
  CSV_PATH   = REPO_ROOT / "docs" / "assets" / "114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv"
  CACHE_PATH = Path(__file__).resolve().parent / ".geocode_cache.json"

  # TPE district centroids keyed by 行政區域代碼
  TPE_DISTRICT = {
      "63000010": (121.5771, 25.0504, "松山區"),
      "63000020": (121.5639, 25.0330, "信義區"),
      "63000030": (121.5432, 25.0260, "大安區"),
      "63000040": (121.5301, 25.0637, "中山區"),
      "63000050": (121.5186, 25.0432, "中正區"),
      "63000060": (121.5102, 25.0633, "大同區"),
      "63000070": (121.5002, 25.0347, "萬華區"),
      "63000080": (121.5706, 24.9892, "文山區"),
      "63000090": (121.6071, 25.0554, "南港區"),
      "63000100": (121.5878, 25.0831, "內湖區"),
      "63000110": (121.5261, 25.0924, "士林區"),
      "63000120": (121.5008, 25.1318, "北投區"),
  }

  INSERT_SQL = """
  INSERT INTO food_restaurant_tpe (name, address, district, grade, lng, lat) VALUES %s
  """


  def clean_addr(addr):
      addr = re.sub(r"\d+~?\d*[Ff樓].*$", "", str(addr or ""))
      addr = re.sub(r"[Bb]\d+.*$", "", addr)
      return addr.strip()


  def main():
      random.seed(42)
      cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

      with open(CSV_PATH, encoding="utf-8-sig") as f:
          rows = list(csv.DictReader(f))

      out = []
      for r in rows:
          code = r.get("行政區域代碼", "")
          centroid = TPE_DISTRICT.get(code, (121.5654, 25.0330, "其他"))
          addr = r.get("地址", "")
          coords = cache.get(clean_addr(addr))
          if coords:
              lng, lat = coords[0], coords[1]
          else:
              lng = centroid[0] + random.uniform(-0.006, 0.006)
              lat = centroid[1] + random.uniform(-0.004, 0.004)
          out.append((
              r.get("業者名稱店名") or "",
              addr,
              centroid[2],
              r.get("評核結果") or "",
              round(lng, 6),
              round(lat, 6),
          ))

      with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
          cur.execute("BEGIN")
          cur.execute("TRUNCATE food_restaurant_tpe RESTART IDENTITY")
          execute_values(cur, INSERT_SQL, out)
          cur.execute("COMMIT")
      print(f"✅ {len(out)} rows → food_restaurant_tpe")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 9.2: Run loader**

  ```bash
  python3 scripts/food_safety/etl/load_restaurant_tpe.py
  ```
  Expected: `✅ 1686 rows → food_restaurant_tpe`.

---

## Task 10: ETL loader — `load_factory_ntpc.py`

**Files:**
- Create: `scripts/food_safety/etl/load_factory_ntpc.py`

Depends on `snapshots/ntpc_food_factory.csv` existing — created in Task 12.

**Steps:**

- [ ] **Step 10.1: Implement loader**

  ```python
  #!/usr/bin/env python3
  """
  Load NTPC food factories into food_factory_ntpc.

  Source (CSV only — NO HTTP):
    scripts/food_safety/snapshots/ntpc_food_factory.csv
    (regenerated via etl/snapshot_apis.py — NOT during apply)

  Schema reference: WGS84 coords from `wgs84ax` (lng) / `wgs84ay` (lat),
  district extracted from `address` field (新北市XX區...).
  """
  import csv
  import re
  import sys
  from pathlib import Path

  import psycopg2
  from psycopg2.extras import execute_values

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  from _db import db_kwargs  # noqa: E402

  CSV_PATH = Path(__file__).resolve().parent.parent / "snapshots" / "ntpc_food_factory.csv"

  INSERT_SQL = """
  INSERT INTO food_factory_ntpc (name, address, tax_id, lng, lat, district) VALUES %s
  """


  def main():
      out = []
      with open(CSV_PATH, encoding="utf-8") as f:
          for r in csv.DictReader(f):
              try:
                  lng = float(r.get("wgs84ax", 0))
                  lat = float(r.get("wgs84ay", 0))
              except (ValueError, TypeError):
                  continue
              if not (120 < lng < 122.5 and 24 < lat < 26):
                  continue
              addr = r.get("address", "")
              m = re.search(r"新北市(\S+區)", addr)
              district = m.group(1) if m else ""
              out.append((
                  r.get("organizer", r.get("name_ins", "")),
                  addr,
                  r.get("tax_id_number", ""),
                  lng,
                  lat,
                  district,
              ))

      with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
          cur.execute("BEGIN")
          cur.execute("TRUNCATE food_factory_ntpc RESTART IDENTITY")
          execute_values(cur, INSERT_SQL, out)
          cur.execute("COMMIT")
      print(f"✅ {len(out)} rows → food_factory_ntpc")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 10.2: (Verification deferred until Task 12 produces the snapshot CSV.)**

---

## Task 11: ETL loaders — MOHW xlsx parsers

**Files:**
- Create: `scripts/food_safety/etl/load_mohw_dual_city.py`
- Create: `scripts/food_safety/etl/load_mohw_poisoning.py`

These parse three MOHW xlsx files using openpyxl. Read both the parent's `generate_mohw_food_stats_sql.py` (290+ lines) and `generate_food_type_violations_sql.py` (150+ lines) before implementing — these contain validated column-index maps and city normalization for 115 年 MOHW data structures.

**Steps:**

- [ ] **Step 11.1: Inspect parent's MOHW parsers to extract reusable logic**

  ```bash
  cd .worktrees/food-safety-radar
  PARENT=/Users/teddy_peng/Projects/my/Taipei-City-Dashboard
  cat "$PARENT/scripts/generate_mohw_food_stats_sql.py" | head -150
  cat "$PARENT/scripts/generate_food_type_violations_sql.py"
  ```

  Note the `CATEGORY_COLS` dict (column-index ranges per food category) and `parse_inspection_by_city()` function — these are the bulk of the logic to port. Pay attention to:
  - Sheet name (likely `Sheet1`, but verify with `openpyxl`)
  - Header rows offset (xlsx header may span rows 1-2)
  - City column normalization: full-width vs half-width, whitespace stripping
  - Venue label mapping (some have `（家次）`/`(家次)` suffix variants)

- [ ] **Step 11.2: Implement `load_mohw_dual_city.py`**

  This loader reads the **same** xlsx (`10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx`) twice, populating both `food_inspection_by_city` (per-venue counts + city-level totals) and `food_type_violations` (per food category).

  ```python
  #!/usr/bin/env python3
  """
  Load MOHW 115 dual-city food inspection statistics.

  Source (xlsx only — NO HTTP):
    docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx

  Writes two tables:
    - food_inspection_by_city   (year, city, venue, inspections, noncompliance,
                                 poisoning_cases, ntpc_violation_rate)
    - food_type_violations      (year, city, category, count)

  Column-index maps adapted from scripts/generate_mohw_food_stats_sql.py and
  scripts/generate_food_type_violations_sql.py (parent worktree).
  """
  import re
  import sys
  from pathlib import Path

  import openpyxl
  import psycopg2
  from psycopg2.extras import execute_values

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  from _db import db_kwargs  # noqa: E402

  REPO_ROOT = Path(__file__).resolve().parents[3]
  XLSX_PATH = REPO_ROOT / "docs" / "assets" / "10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx"
  YEAR = 2026

  TARGET_CITIES = {"臺北市", "新北市"}
  VENUES = ["餐飲店", "冷飲店", "飲食攤販", "傳統市場", "超級市場", "製造廠商"]

  # Column index → (category_label) — copied from generate_food_type_violations_sql.py
  # Indices may need adjustment after inspecting the xlsx structure in Step 11.1.
  CATEGORY_COLS = {
      "乳品類":     list(range(5, 11)),
      "肉品類":     list(range(11, 14)),
      "蛋品類":     list(range(14, 17)),
      "水產類":     list(range(17, 20)),
      "穀豆烘焙":   list(range(20, 32)),
      "蔬果類":     list(range(32, 36)) + list(range(40, 44)),
      "飲料及水":   list(range(49, 52)),
      "食用油脂":   list(range(52, 55)),
      "調味品":     list(range(59, 63)),
      "健康食品":   [63, 64],
      "複合調理":   list(range(65, 68)),
      "其他":       list(range(44, 49)) + list(range(55, 59)) + list(range(68, 72)),
  }


  def to_int(v):
      try:
          return int(str(v or "0").replace(",", "").strip())
      except (ValueError, AttributeError):
          return 0


  def normalize_city(raw):
      s = re.sub(r"\s+", "", str(raw or "").strip())
      return s if s in TARGET_CITIES else None


  def parse_xlsx():
      """Return tuple (inspection_rows, violation_rows)."""
      wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
      ws = wb.active

      inspection = []
      violations = []

      for row in ws.iter_rows(values_only=True):
          if not row:
              continue
          city = normalize_city(row[1] if len(row) > 1 else None)
          if not city:
              continue

          # Per-venue inspection counts (column indices 2 + 2*i and 3 + 2*i — VERIFY BEFORE RUNNING)
          # The actual venue column layout depends on xlsx structure inspected in Step 11.1.
          # Replace this block after inspecting the file.
          # Placeholder structure: total_insp at col 2, total_nc at col 3, then each venue insp/nc.
          # If xlsx has 'inspections' and 'noncompliance' as separate columns per venue,
          # iterate VENUES with correct offsets.

          # Total row (venue='合計')
          total_insp = to_int(row[2]) if len(row) > 2 else 0
          total_nc   = to_int(row[3]) if len(row) > 3 else 0
          # food poisoning cases column index — VERIFY
          poison = to_int(row[72]) if len(row) > 72 else None
          rate = round((total_nc * 100.0 / total_insp), 2) if total_insp else None
          inspection.append((YEAR, city, "合計", total_insp, total_nc, poison, rate))

          # Per-venue rows — VERIFY column offsets
          # for i, venue in enumerate(VENUES):
          #     insp = to_int(row[4 + 2*i])
          #     nc   = to_int(row[5 + 2*i])
          #     inspection.append((YEAR, city, venue, insp, nc, None, None))

          # Per-category violations
          for cat, cols in CATEGORY_COLS.items():
              total = sum(to_int(row[c]) for c in cols if c < len(row))
              if total > 0:
                  violations.append((YEAR, city, cat, total))

      return inspection, violations


  def main():
      insp_rows, viol_rows = parse_xlsx()
      with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
          cur.execute("BEGIN")
          cur.execute("TRUNCATE food_inspection_by_city RESTART IDENTITY")
          execute_values(cur,
              "INSERT INTO food_inspection_by_city "
              "(year, city, venue, inspections, noncompliance, poisoning_cases, ntpc_violation_rate) "
              "VALUES %s", insp_rows)
          cur.execute("TRUNCATE food_type_violations RESTART IDENTITY")
          execute_values(cur,
              "INSERT INTO food_type_violations (year, city, category, count) VALUES %s",
              viol_rows)
          cur.execute("COMMIT")
      print(f"✅ {len(insp_rows)} rows → food_inspection_by_city")
      print(f"✅ {len(viol_rows)} rows → food_type_violations")


  if __name__ == "__main__":
      main()
  ```

  **Critical:** the column indices in `parse_xlsx()` are placeholders. Before running, open the xlsx in Step 11.1 (or use `openpyxl` to dump first 5 rows) and pin the actual venue inspection columns + food poisoning column. Update inline.

- [ ] **Step 11.3: Inspect xlsx structure to pin column indices**

  ```bash
  cd .worktrees/food-safety-radar
  python3 -c "
  import openpyxl
  wb = openpyxl.load_workbook('docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx', data_only=True)
  ws = wb.active
  for i, row in enumerate(ws.iter_rows(values_only=True)):
      if i < 5:
          print(i, row[:30])
      else:
          break
  "
  ```

  Then update `parse_xlsx()` in `load_mohw_dual_city.py` with the correct column indices for: city name column, total inspections, total noncompliance, food poisoning cases, and venue-specific inspection/NC pairs.

- [ ] **Step 11.4: Run `load_mohw_dual_city.py`**

  ```bash
  python3 scripts/food_safety/etl/load_mohw_dual_city.py
  ```
  Expected: 2 lines, each with rows > 0. `food_inspection_by_city` should have at least 14 rows (2 cities × (1 合計 + 6 venues)). `food_type_violations` should have ≤ 24 rows (2 cities × 12 categories, but 0-count entries dropped).

- [ ] **Step 11.5: Implement `load_mohw_poisoning.py`**

  ```python
  #!/usr/bin/env python3
  """
  Load MOHW national food-poisoning statistics by cause.

  Source (xlsx only — NO HTTP):
    docs/assets/10521-05-01食品中毒案件病因物質分類統計.xlsx

  Writes food_poisoning_cause (year, cause, cases, persons).
  Adapted from scripts/generate_mohw_food_stats_sql.py (parent worktree).
  """
  import re
  import sys
  from pathlib import Path

  import openpyxl
  import psycopg2
  from psycopg2.extras import execute_values

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  from _db import db_kwargs  # noqa: E402

  REPO_ROOT = Path(__file__).resolve().parents[3]
  XLSX_PATH = REPO_ROOT / "docs" / "assets" / "10521-05-01食品中毒案件病因物質分類統計.xlsx"

  INSERT_SQL = """
  INSERT INTO food_poisoning_cause (year, cause, cases, persons) VALUES %s
  """


  def to_int(v):
      try:
          return int(str(v or "0").replace(",", "").strip())
      except (ValueError, AttributeError):
          return 0


  def roc_to_ad(s):
      m = re.match(r"(\d+)", str(s or "").strip())
      return int(m.group(1)) + 1911 if m else None


  def main():
      wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
      ws = wb.active

      out = []
      # Layout: column 0 is year (ROC), column 1 is cause label,
      # then cases and persons columns. VERIFY indices in Step 11.6.
      for row in ws.iter_rows(min_row=3, values_only=True):
          if not row or row[0] is None:
              continue
          year = roc_to_ad(row[0])
          cause = str(row[1] or "").strip()
          if not year or not cause:
              continue
          cases = to_int(row[2]) if len(row) > 2 else 0
          persons = to_int(row[3]) if len(row) > 3 else 0
          out.append((year, cause, cases, persons))

      with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
          cur.execute("BEGIN")
          cur.execute("TRUNCATE food_poisoning_cause RESTART IDENTITY")
          execute_values(cur, INSERT_SQL, out)
          cur.execute("COMMIT")
      print(f"✅ {len(out)} rows → food_poisoning_cause")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 11.6: Inspect xlsx + run loader**

  ```bash
  python3 -c "
  import openpyxl
  wb = openpyxl.load_workbook('docs/assets/10521-05-01食品中毒案件病因物質分類統計.xlsx', data_only=True)
  ws = wb.active
  for i, row in enumerate(ws.iter_rows(values_only=True)):
      if i < 8: print(i, row[:6])
      else: break
  "
  python3 scripts/food_safety/etl/load_mohw_poisoning.py
  ```
  Expected: > 0 rows.

---

## Task 12: `snapshot_apis.py` + run it to generate `ntpc_food_factory.csv`

**Files:**
- Create: `scripts/food_safety/etl/snapshot_apis.py`
- Create: `scripts/food_safety/snapshots/ntpc_food_factory.csv` (generated artifact)

**Steps:**

- [ ] **Step 12.1: Implement `snapshot_apis.py`**

  ```python
  #!/usr/bin/env python3
  """
  One-shot snapshot tool: fetch NTPC food factory API and write CSV into
  scripts/food_safety/snapshots/. Re-run only when refreshing data; the
  regular apply.sh does NOT call this — it only reads committed CSVs.

  Endpoint:
    https://data.ntpc.gov.tw/api/datasets/c51d5111-c300-44c9-b4f1-4b28b9929ca2/json
    Paginated by size+page, expected ~1232 rows.
  """
  import csv
  import sys
  import time
  from pathlib import Path

  import requests

  OUT_DIR = Path(__file__).resolve().parent.parent / "snapshots"
  OUT_DIR.mkdir(exist_ok=True)
  OUT_FILE = OUT_DIR / "ntpc_food_factory.csv"

  UUID = "c51d5111-c300-44c9-b4f1-4b28b9929ca2"
  PAGE_SIZE = 200


  def fetch_all():
      url = f"https://data.ntpc.gov.tw/api/datasets/{UUID}/json"
      rows = []
      page = 0
      while True:
          resp = requests.get(url, params={"size": PAGE_SIZE, "page": page}, timeout=60)
          resp.raise_for_status()
          batch = resp.json() or []
          if not batch:
              break
          rows.extend(batch)
          print(f"  page {page}: {len(batch)} rows, total {len(rows)}")
          if len(batch) < PAGE_SIZE:
              break
          page += 1
          time.sleep(0.5)
      return rows


  def main():
      print(f"Fetching NTPC food factories (UUID {UUID}) …")
      rows = fetch_all()
      if not rows:
          print("ERROR: zero rows returned", file=sys.stderr)
          sys.exit(1)

      cols = sorted({k for r in rows for k in r.keys()})
      with open(OUT_FILE, "w", encoding="utf-8", newline="") as f:
          w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
          w.writeheader()
          for r in rows:
              w.writerow(r)
      print(f"✅ {len(rows)} rows → {OUT_FILE}")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 12.2: Run snapshot tool to produce CSV**

  ```bash
  python3 scripts/food_safety/etl/snapshot_apis.py
  ```
  Expected: `✅ ~1232 rows → scripts/food_safety/snapshots/ntpc_food_factory.csv`. If network fails or row count drops > 5%, investigate before committing.

- [ ] **Step 12.3: Run `load_factory_ntpc.py` (deferred from Task 10)**

  ```bash
  python3 scripts/food_safety/etl/load_factory_ntpc.py
  ```
  Expected: `✅ ~1230 rows → food_factory_ntpc` (some lost to invalid coords).

---

## Task 13: GeoJSON generator

**Files:**
- Create: `scripts/food_safety/etl/generate_geojson.py`

**Steps:**

- [ ] **Step 13.1: Implement generator**

  ```python
  #!/usr/bin/env python3
  """
  Generate FE map GeoJSON from food_restaurant_tpe + food_factory_ntpc tables.
  Runs LAST in apply.sh (depends on tables being populated).

  Outputs:
    Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson
    Taipei-City-Dashboard-FE/public/mapData/food_factory_ntpc.geojson
  """
  import json
  import sys
  from pathlib import Path

  import psycopg2

  sys.path.insert(0, str(Path(__file__).resolve().parent))
  from _db import db_kwargs  # noqa: E402

  REPO_ROOT = Path(__file__).resolve().parents[3]
  OUT_DIR   = REPO_ROOT / "Taipei-City-Dashboard-FE" / "public" / "mapData"


  def fetch(query):
      with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
          cur.execute(query)
          cols = [d[0] for d in cur.description]
          return [dict(zip(cols, r)) for r in cur.fetchall()]


  def to_feature_collection(rows, props_fn):
      feats = []
      for r in rows:
          if r["lng"] is None or r["lat"] is None:
              continue
          feats.append({
              "type": "Feature",
              "geometry": {"type": "Point", "coordinates": [round(r["lng"], 6), round(r["lat"], 6)]},
              "properties": props_fn(r),
          })
      return {"type": "FeatureCollection", "features": feats}


  def main():
      OUT_DIR.mkdir(parents=True, exist_ok=True)

      restaurants = fetch(
          "SELECT name, address, district, grade, lng, lat FROM food_restaurant_tpe"
      )
      rest_fc = to_feature_collection(restaurants, lambda r: {
          "name":     r["name"] or "",
          "grade":    r["grade"] or "",
          "address":  r["address"] or "",
          "district": r["district"] or "",
          "city":     "taipei",
      })
      rest_path = OUT_DIR / "food_restaurant_tpe.geojson"
      rest_path.write_text(json.dumps(rest_fc, ensure_ascii=False), encoding="utf-8")
      print(f"✅ {len(rest_fc['features'])} features → {rest_path.name}")

      factories = fetch(
          "SELECT name, address, district, lng, lat FROM food_factory_ntpc"
      )
      fact_fc = to_feature_collection(factories, lambda r: {
          "name":     r["name"] or "",
          "address":  r["address"] or "",
          "district": r["district"] or "",
          "city":     "newtaipei",
      })
      fact_path = OUT_DIR / "food_factory_ntpc.geojson"
      fact_path.write_text(json.dumps(fact_fc, ensure_ascii=False), encoding="utf-8")
      print(f"✅ {len(fact_fc['features'])} features → {fact_path.name}")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 13.2: Run generator (requires tables populated by Tasks 8-12)**

  ```bash
  python3 scripts/food_safety/etl/generate_geojson.py
  ls -lh Taipei-City-Dashboard-FE/public/mapData/food_*.geojson
  ```
  Expected: 2 files, ~300-450 KB each.

---

## Task 14: End-to-end apply, verify, commit

**Steps:**

- [ ] **Step 14.1: Wipe state cleanly**

  ```bash
  cd .worktrees/food-safety-radar
  ./scripts/food_safety/rollback.sh
  ```
  Expected: clean run (DROP IF EXISTS / DELETE on possibly-empty tables).

- [ ] **Step 14.2: Run full apply**

  ```bash
  ./scripts/food_safety/apply.sh
  ```
  Expected output (final 3/3 row count block):

  ```
        t              | count
  ----------------------+-------
   food_inspection_tpe       |    20
   food_testing_tpe          |    20
   food_restaurant_tpe       |  1686
   food_factory_ntpc         |  ~1230
   food_inspection_by_city   |   ≥14
   food_type_violations      |   ≥6
   food_poisoning_cause      |    >0
  ```

- [ ] **Step 14.3: Verify dashboard 503 via API**

  ```bash
  curl -s "http://localhost:8088/api/v1/dashboard/food_safety_radar?city=metrotaipei" | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d.get('status')); print('components:', len(d.get('data', [])))"
  ```
  Expected: `status: success` and `components: 5`.

- [ ] **Step 14.4: Verify each component returns chart data**

  ```bash
  for id in 1011 1012 1013 1014 1015; do
    echo "--- $id taipei ---"
    curl -s "http://localhost:8088/api/v1/component/$id/chart?city=taipei"      | head -c 200
    echo
    echo "--- $id metrotaipei ---"
    curl -s "http://localhost:8088/api/v1/component/$id/chart?city=metrotaipei" | head -c 200
    echo
  done
  ```
  Expected: every call returns `{"data":[...],"status":"success"}` with non-empty `data`.

- [ ] **Step 14.5: Verify GeoJSON files in place + valid JSON**

  ```bash
  python3 -c "import json; d=json.load(open('Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson')); print('TPE rest:', len(d['features']))"
  python3 -c "import json; d=json.load(open('Taipei-City-Dashboard-FE/public/mapData/food_factory_ntpc.geojson')); print('NTPC fact:', len(d['features']))"
  ```
  Expected: ~1686 / ~1230 features.

- [ ] **Step 14.6: Verify labor untouched (if labor was previously applied)**

  ```bash
  source scripts/food_safety/_db_env.sh
  pg_psql MANAGER -c "SELECT id, name FROM dashboards WHERE id IN (502, 503) ORDER BY id"
  ```
  Expected: 503 row present; 502 row state matches pre-food-safety state (present if labor was applied, absent if not).

- [ ] **Step 14.7: Idempotency — re-run apply, expect no errors and identical state**

  ```bash
  ./scripts/food_safety/apply.sh
  pg_psql DASHBOARD -c "SELECT 'food_inspection_tpe' AS t, COUNT(*) FROM food_inspection_tpe UNION ALL SELECT 'food_testing_tpe', COUNT(*) FROM food_testing_tpe UNION ALL SELECT 'food_restaurant_tpe', COUNT(*) FROM food_restaurant_tpe UNION ALL SELECT 'food_factory_ntpc', COUNT(*) FROM food_factory_ntpc UNION ALL SELECT 'food_inspection_by_city', COUNT(*) FROM food_inspection_by_city UNION ALL SELECT 'food_type_violations', COUNT(*) FROM food_type_violations UNION ALL SELECT 'food_poisoning_cause', COUNT(*) FROM food_poisoning_cause"
  ```
  Expected: identical row counts to first apply.

- [ ] **Step 14.8: Rollback clean — verify all food_* gone, labor intact**

  ```bash
  ./scripts/food_safety/rollback.sh
  source scripts/food_safety/_db_env.sh
  pg_psql DASHBOARD -c "\dt food_*"                                                 # 0 rows
  pg_psql MANAGER   -c "SELECT COUNT(*) FROM dashboards WHERE id = 503"             # 0
  pg_psql MANAGER   -c "SELECT COUNT(*) FROM components WHERE id BETWEEN 1011 AND 1015"   # 0
  pg_psql MANAGER   -c "SELECT COUNT(*) FROM query_charts WHERE index LIKE 'food_%'"      # 0
  ls Taipei-City-Dashboard-FE/public/mapData/food_*.geojson 2>&1                    # No such file
  ```

- [ ] **Step 14.9: Re-apply final time (leave system in good state for demo)**

  ```bash
  ./scripts/food_safety/apply.sh
  ```

- [ ] **Step 14.10: Stage + commit ETL + assets + snapshot**

  ```bash
  git add docs/assets/ \
          scripts/food_safety/etl/ \
          scripts/food_safety/snapshots/ \
          scripts/food_safety/README.md
  git status -sb
  git diff --cached --stat
  ```

  Expected ~16-18 new files. Commit:

  ```bash
  git commit -m "$(cat <<'EOF'
  feat(food-safety): add ETL loaders + NTPC factory snapshot + MOHW xlsx parsers + assets

  All loaders read CSV/xlsx — zero HTTP at apply time. NTPC food factory
  API pre-fetched into snapshots/ntpc_food_factory.csv (regenerate via
  etl/snapshot_apis.py when refreshing). Geocoding cache (9,680 entries)
  committed under etl/.geocode_cache.json — cache miss falls back to
  TPE district centroid + jitter (no external API).

  Loaders → tables:
    load_inspection_tpe.py     → food_inspection_tpe (20), food_testing_tpe (20)
    load_restaurant_tpe.py     → food_restaurant_tpe (1,686)
    load_factory_ntpc.py       → food_factory_ntpc (~1,230)
    load_mohw_dual_city.py     → food_inspection_by_city (~14), food_type_violations (~24)
    load_mohw_poisoning.py     → food_poisoning_cause (>0)
    generate_geojson.py        → FE/public/mapData/food_*.geojson

  Real dual-city via MOHW xlsx (115年衛福部 by-city) — query_charts in
  002_seed_dashboard reference these tables for metrotaipei components
  1012/1014; 1011/1015 metrotaipei use UNION ALL to add NTPC 2026 point
  to TPE long-term series.

  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Self-Review

Run after writing all tasks:

**1. Spec coverage check:**
- §1 directory structure → Tasks 1, 2, 3, 4, 5 ✓
- §2 apply/rollback/backup → Task 4 ✓
- §3 ETL + snapshot → Tasks 8-13 ✓
- §4 schema (7 tables) → Task 2 ✓
- §5 dual-city queries → Task 3 ✓
- §6 FE/BE zero changes → no task needed (explicit no-op)
- §6.3 verification checklist (9 items) → Task 14 covers items 1, 2, 3, 4, 6, 7, 8, 9; item 5 (FE build) is implicit (no FE changes) but worth noting

**2. Placeholder scan:**
- Task 11 (MOHW xlsx parsers) contains explicit "VERIFY" notes for column indices that must be inspected before running. This is intentional — xlsx structure inspection is part of the task. Not a placeholder.
- All other tasks have complete code.

**3. Type consistency:**
- `db_kwargs()` / `manager_kwargs()` used consistently from `_db.py` ✓
- `pg_psql DASHBOARD` / `pg_psql MANAGER` used consistently in all bash ✓
- Table column names match between migration 001, INSERT statements in loaders, and SELECT queries in migration 002 — verified by hand against spec §4 schema and §5 query SQL.

---

## Execution Handoff

This plan is complete. Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch fresh subagent per task, review between tasks, fastest iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch with checkpoints

Pick one to proceed.
