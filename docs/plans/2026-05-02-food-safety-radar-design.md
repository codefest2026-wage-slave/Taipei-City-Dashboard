# 食安風險追蹤器 Food Safety Radar — 獨立化設計文件

- **日期：** 2026-05-02
- **目標分支：** `feat/food-safety-radar`（從 `origin/feat/labor-safety-radar` HEAD `78d2742` 切出）
- **背景：** 食安原本以 commit `fbd23a2` 散落於 `feat/green-mobility-dashboard` 分支，與 disaster / recheck / employment / green mobility 等多個主題混雜。為比賽 demo 穩定性、PR 合併友善與可重複佈署，比照 `feat/labor-safety-radar` 的獨立化模式，把食安實作整理成自包含、可 rollback、不依賴外部 API 的乾淨分支。
- **基準分支：** 直接以 `origin/feat/labor-safety-radar` 為 base — 食安完全與 labor 並列，互不干涉。

---

## 設計目標

1. **流程穩定可重現** — 任何人在任何網路狀態下，從 0 到 dashboard 503 可見，必須一路順跑。
2. **CSV ⇒ ETL ⇒ DB 全鏈路** — 禁止 ETL 階段呼叫外部 API；所有資料一律從 repo 內 CSV / xlsx 讀。
3. **可 rollback** — 套用、回退、再套用，DB 狀態必須一致；不留半套狀態、不污染既有資料。
4. **PR 合併友善** — TRUNCATE 範圍嚴格限制在 food_safety 自有的 7 張表；id / index 範圍嚴格鎖在 1011-1015 / `food_*`，不誤刪 labor 1005-1010 / 1019。
5. **比賽 demo 零意外** — 即使主辦方場館網路斷線、API 改格式，本 dashboard 仍可正常 demo。
6. **遵守 CLAUDE.md 雙北原則** — 5 個 components 全部要有 taipei + metrotaipei 兩筆 query_charts。

---

## 1. 目錄結構

```
Taipei-City-Dashboard/
├── scripts/food_safety/                    ← 整個資料夾刪掉就等於拔掉 dashboard 503
│   ├── README.md                           ← 流程圖 + 重跑指令
│   ├── apply.sh                            ← 一鍵套用：migrations → ETL → 印 row count
│   ├── rollback.sh                         ← 一鍵還原：down.sql + 清 GeoJSON
│   ├── backup_db.sh                        ← pg_dump 兩個 DB 到 ./backups/<timestamp>/
│   ├── _db_env.sh                          ← container/DB 環境變數抽出（複用 labor 同款）
│   ├── .env.script.example
│   ├── .gitignore                          ← backups/ 不 commit
│   ├── migrations/
│   │   ├── 001_create_tables.up.sql        ← 7 張 food_* 表
│   │   ├── 001_create_tables.down.sql
│   │   ├── 002_seed_dashboard.up.sql       ← components 1011-1015 + dashboard 503 + 10 query_charts + 2 maps
│   │   └── 002_seed_dashboard.down.sql
│   ├── etl/
│   │   ├── _db.py                          ← psycopg2 連線封裝（複用 labor 同款）
│   │   ├── .geocode_cache.json             ← 9680 entries 地理編碼快取（commit 進 repo）
│   │   ├── snapshot_apis.py                ← 一次性備料：NTPC factory API → CSV
│   │   ├── load_inspection_tpe.py          ← TPE 稽查/檢驗 CSV → food_inspection_tpe + food_testing_tpe
│   │   ├── load_restaurant_tpe.py          ← TPE 評核 CSV → food_restaurant_tpe（含 geocode + fallback）
│   │   ├── load_factory_ntpc.py            ← snapshots/ntpc_food_factory.csv → food_factory_ntpc
│   │   ├── load_mohw_dual_city.py          ← MOHW xlsx → food_inspection_by_city + food_type_violations
│   │   ├── load_mohw_poisoning.py          ← MOHW xlsx → food_poisoning_cause
│   │   └── generate_geojson.py             ← DB → FE/public/mapData/food_*.geojson
│   ├── snapshots/
│   │   └── ntpc_food_factory.csv           ← NTPC API 快照（~1232 rows）
│   └── backups/.gitkeep
├── docs/assets/                            ← 食安 6 個檔在本分支新增（base = labor 上不存在）
│   ├── 114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv
│   ├── 臺北市食品衛生管理稽查工作-年度統計.csv
│   ├── 臺北市食品衛生管理查驗工作-年度統計.csv
│   ├── 10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx     ← MOHW 雙北 by-city
│   ├── 10521-05-01食品中毒案件病因物質分類統計.xlsx
│   └── 10521-05-03食品中毒案件攝食場所分類統計.xlsx
└── docs/plans/2026-05-02-food-safety-radar-design.md   ← 本文件
```

**要點：**
- 食安 6 個資產檔在 `origin/feat/labor-safety-radar` base 上**不存在**，本分支會把它們新增到 `docs/assets/`（從 `feat/green-mobility-dashboard` commit `fbd23a2` 帶過來）。
- 整個 `scripts/food_safety/` 資料夾刪掉就等於拔掉這個 dashboard，labor_safety 不受影響。
- **本次萃取 FE 變更為 0** — 不 cherry-pick `SearchableFoodSafetyTable.vue`（5 個註冊的 components 都不用它），不 patch FE 共享檔。

---

## 2. Migration、Rollback、備份機制

### 2.1 `backup_db.sh`（永遠先跑）

複用 labor 的 `_db_env.sh` 抽象（不再硬寫 `docker exec`）：

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/_db_env.sh"

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$ROOT/backups/$TS"
mkdir -p "$OUT"

pg_dump_data    > "$OUT/dashboard.sql"
pg_dump_manager > "$OUT/dashboardmanager.sql"

echo "✅ backup → $OUT"
ls -lh "$OUT"
```

`scripts/food_safety/backups/` 加進 `.gitignore`，**不 commit dump**。
README 教 restore：`docker exec -i postgres-data psql -U postgres -d dashboard < backups/<ts>/dashboard.sql`

### 2.2 `apply.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/_db_env.sh"

echo "▶ 1/3 migrations up …"
psql_data    -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.up.sql"
psql_manager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"

echo "▶ 2/3 ETL（離線）…"
python3 "$ROOT/etl/load_inspection_tpe.py"
python3 "$ROOT/etl/load_restaurant_tpe.py"
python3 "$ROOT/etl/load_factory_ntpc.py"
python3 "$ROOT/etl/load_mohw_dual_city.py"
python3 "$ROOT/etl/load_mohw_poisoning.py"
python3 "$ROOT/etl/generate_geojson.py"

echo "▶ 3/3 verify row counts …"
psql_data -c "
  SELECT 'food_inspection_tpe'      AS t, COUNT(*) FROM food_inspection_tpe
  UNION ALL SELECT 'food_testing_tpe',         COUNT(*) FROM food_testing_tpe
  UNION ALL SELECT 'food_restaurant_tpe',      COUNT(*) FROM food_restaurant_tpe
  UNION ALL SELECT 'food_factory_ntpc',        COUNT(*) FROM food_factory_ntpc
  UNION ALL SELECT 'food_inspection_by_city',  COUNT(*) FROM food_inspection_by_city
  UNION ALL SELECT 'food_type_violations',     COUNT(*) FROM food_type_violations
  UNION ALL SELECT 'food_poisoning_cause',     COUNT(*) FROM food_poisoning_cause;"
echo "✅ apply complete"
```

關鍵：
- `psql -v ON_ERROR_STOP=1 -1` → 任何錯誤整個交易 ROLLBACK，半套狀態不可能存在
- 三步驟順序：DDL → DML 註冊 → ETL 灌資料
- 結尾印 row count 強制肉眼驗證

### 2.3 `rollback.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$ROOT/_db_env.sh"

# 先拔註冊（避免 FE 還在 query 一個快被 drop 的表）
psql_manager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.down.sql"
# 再 DROP TABLE
psql_data    -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.down.sql"

# 清 GeoJSON
rm -f ../../Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson
rm -f ../../Taipei-City-Dashboard-FE/public/mapData/food_factory_ntpc.geojson

echo "✅ rollback complete"
```

### 2.4 Migration 檔內容守則（與 labor 完全一致）

- **每支 SQL 自己 BEGIN/COMMIT**（不只靠 `-1`，雙保險）
- `up.sql` 用 `CREATE TABLE IF NOT EXISTS` + `ON CONFLICT (index/id) DO NOTHING`，**重跑不會炸**
- `down.sql` 用 `DROP TABLE IF EXISTS … CASCADE` + `DELETE … WHERE id BETWEEN 1011 AND 1015 / index LIKE 'food_%'`，**沒套用過也不會炸**
- 兩個方向都 idempotent ⇒ PR 合進 develop 後別人重跑也安全
- ID 範圍嚴格：components `1011-1015` / dashboard `503` / index `food_*` — 跟 labor 1005-1010 / 1019 / 502 / `labor_*` 完全不重疊

### 2.5 從 0 重跑的標準流程

```bash
# 1. 備份
./scripts/food_safety/backup_db.sh

# 2. 清 DB（整個 volume 炸掉）
docker compose -f docker/docker-compose-db.yaml down -v
docker compose -f docker/docker-compose-db.yaml up -d
sleep 10  # healthcheck

# 3. 跑 base init
docker compose -f docker/docker-compose-init.yaml up -d

# 4. （可選）套 labor safety
./scripts/labor_safety/apply.sh

# 5. 套 food safety
./scripts/food_safety/apply.sh

# 6. 開 http://localhost:8080 → shift+logo 登入 → dashboard 503 → 5 張卡片皆有資料
```

---

## 3. ETL 與 API Snapshot

### 3.1 `snapshot_apis.py`（一次性備料工具）

```python
"""
從 data.ntpc 把 NTPC food factory API 抓下來，存成 CSV。
這支腳本「不」是 ETL 流程的一部分 — 是離線備料工具。
跑完 commit snapshots/*.csv 進 repo 之後，apply.sh 就只讀 CSV。
"""
SOURCES = [
    ("ntpc_food_factory.csv",
     "https://data.ntpc.gov.tw/api/datasets/c51d5111-c300-44c9-b4f1-4b28b9929ca2/json"),
]
# size=200, page=0..N 分頁，預期 ~1232 rows
# 結尾印 row count，與下表預期值對表
```

**預期 row count（驗收標準）：**

| Snapshot | 預期 ±5% |
|---|---|
| ntpc_food_factory.csv | ~1232 |

### 3.2 Loader 5 條鐵則（與 labor 一致）

```python
def main():
    rows = parse_source(SRC)                # 純檔案讀取，無網路
    cleaned = [transform(r) for r in rows]  # 日期 ROC→AD、欄位映射、缺值處理
    cleaned = [r for r in cleaned if r]     # drop None

    with conn() as c, c.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE food_xxx_table")
        psycopg2.extras.execute_values(cur, INSERT_SQL, cleaned)
        cur.execute("COMMIT")
    print(f"✅ {len(cleaned)} rows → food_xxx_table")
```

1. **TRUNCATE before INSERT** — 不堆疊、可重跑
2. **整個寫入包一個 transaction** — 中途失敗 ROLLBACK，不會半套
3. **沒有任何 HTTP 呼叫** — 一律從 `docs/assets/` 或 `snapshots/` 讀；地址地理編碼一律走 `etl/.geocode_cache.json`，cache miss 時 fallback district centroid（不打 ArcGIS）
4. **寫入後印 row count** — apply.sh 結尾才能交叉驗證
5. **transform 失敗（壞資料）只記 log 不 abort** — 個別 row 丟掉，整體仍能完成

### 3.3 Loader → 資料表對應

| Loader | 讀 | 寫到表 |
|---|---|---|
| `load_inspection_tpe.py` | `docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv` + `docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv` | `food_inspection_tpe`、`food_testing_tpe` |
| `load_restaurant_tpe.py` | `docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv` + `etl/.geocode_cache.json` | `food_restaurant_tpe` |
| `load_factory_ntpc.py` | `snapshots/ntpc_food_factory.csv` | `food_factory_ntpc` |
| `load_mohw_dual_city.py` | `docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx` | `food_inspection_by_city`、`food_type_violations` |
| `load_mohw_poisoning.py` | `docs/assets/10521-05-01食品中毒案件病因物質分類統計.xlsx` | `food_poisoning_cause` |
| `generate_geojson.py` | DB: `food_restaurant_tpe`、`food_factory_ntpc` | `FE/public/mapData/food_restaurant_tpe.geojson`、`food_factory_ntpc.geojson` |

GeoJSON 產生器讀 DB 而非 CSV，所以放 apply.sh 最後一步。

### 3.4 雙北資料缺口的 Fallback 策略

依 CLAUDE.md「最高原則」：5 個 components 全有 taipei + metrotaipei 兩筆 query_charts。

- 任一邊抓不到資料 → loader 結尾 row count 為 0 → apply.sh 偵測為 0 直接 fail
- MOHW xlsx 城市欄位可能有「臺北市」「新北市」差異或全形/半形問題 → loader 內 `normalize_city()` 統一
- TPE 評核 CSV 的地址 geocode hit rate 約 94%（983/1047 unique addresses）；剩下 6% 用行政區 centroid + jitter fallback（保留現有 `geocode_or_fallback` 邏輯）

---

## 4. Schema 設計（7 張表，dashboard DB）

| Table | 來源 | 用於 component |
|---|---|---|
| `food_inspection_tpe` | TPE CSV 20 年稽查統計 | 1011 (taipei), 1012 (taipei) |
| `food_testing_tpe` | TPE CSV 20 年檢驗統計 | 1014 (taipei), 1015 (taipei) |
| `food_restaurant_tpe` | TPE 評核 CSV + geocode | 1013 |
| `food_factory_ntpc` | snapshots/ntpc_food_factory.csv | 1013 |
| `food_inspection_by_city` ⭐新 | MOHW 10521-01-03 xlsx | 1011 / 1012 / 1015 metrotaipei |
| `food_type_violations` ⭐新 | MOHW 10521-01-03 xlsx | 1014 metrotaipei |
| `food_poisoning_cause` ⭐新 | MOHW 10521-05-01 xlsx | 備援，1011 metrotaipei 補點 |

**前 4 張**沿用 commit `fbd23a2` 內 `generate_food_safety_sql.py` 既有 schema（已驗證 dashboard 503 可正常顯示），**後 3 張**為本次新增以支撐真雙北 query 改寫：

```sql
CREATE TABLE IF NOT EXISTS food_inspection_by_city (
  id SERIAL PRIMARY KEY,
  year INTEGER NOT NULL,
  city VARCHAR(20) NOT NULL,            -- '臺北市' / '新北市'
  venue VARCHAR(40) NOT NULL,           -- 餐飲店/冷飲店/飲食攤販/傳統市場/超級市場/製造廠商/合計
  inspections INTEGER,                  -- 稽查家次
  noncompliance INTEGER,                -- 不合格家次
  poisoning_cases INTEGER,              -- 該年度食物中毒人數（僅 venue='合計' row 填）
  ntpc_violation_rate NUMERIC(5,2),     -- 不符規定比率（僅 venue='合計' row 填）
  UNIQUE (year, city, venue)
);

CREATE TABLE IF NOT EXISTS food_type_violations (
  id SERIAL PRIMARY KEY,
  year INTEGER NOT NULL,
  city VARCHAR(20) NOT NULL,
  category VARCHAR(40) NOT NULL,        -- 乳品類/肉品類/.../其他
  count INTEGER NOT NULL,
  UNIQUE (year, city, category)
);

CREATE TABLE IF NOT EXISTS food_poisoning_cause (
  id SERIAL PRIMARY KEY,
  year INTEGER NOT NULL,
  cause VARCHAR(60) NOT NULL,           -- 細菌性/化學性/病毒性/天然毒/不明
  cases INTEGER, persons INTEGER,
  UNIQUE (year, cause)
);
```

---

## 5. Dual-City Query 改寫策略

按 approach「不對稱混搭」：時序圖（1011/1015）保留 TPE 厚度 + NTPC 點補；截面圖（1012/1014）真雙北並列；地圖（1013）已雙城。

| Component | 類型 | taipei query | metrotaipei query |
|---|---|---|---|
| **1011** 食物中毒趨勢 | ColumnLineChart, time | TPE 2006-2025 雙線（人數 + 不合格場所） | TPE 全期線 + NTPC 2026 一點：`SELECT TO_TIMESTAMP(year::text,'YYYY') x, '臺北市' y, food_poisoning_cases data FROM food_inspection_tpe UNION ALL SELECT TO_TIMESTAMP('2026','YYYY'), '新北市', poisoning_cases FROM food_inspection_by_city WHERE city='新北市' AND venue='合計'` |
| **1012** 場所不合格率 | BarChart, two_d | TPE 2020-2025 累計 6 venues | 真雙北：`SELECT venue \|\| '(' \|\| city \|\| ')' x, ROUND(noncompliance*100.0/inspections,1) data FROM food_inspection_by_city WHERE city IN ('臺北市','新北市') AND venue!='合計' ORDER BY data DESC` |
| **1013** 食安地圖 | MapLegend, map_legend | 1 layer (TPE 餐廳) | 2 layers (TPE 餐廳 + NTPC 工廠) — 沿用 fbd23a2 既有設計 |
| **1014** 違規原因分析 | DonutChart, two_d | TPE 2022-2025 累計 7 類 | 真雙北：`SELECT category \|\| '(' \|\| city \|\| ')' x, count data FROM food_type_violations WHERE city IN ('臺北市','新北市') ORDER BY data DESC` |
| **1015** 年度檢驗違規率 | BarChart, two_d | TPE 2015-2025 年度 | TPE 全期 + NTPC 2026 一柱：`SELECT year::text x, '臺北市' y, violation_rate data FROM food_testing_tpe WHERE year >= 2015 UNION ALL SELECT '2026', '新北市', ntpc_violation_rate FROM food_inspection_by_city WHERE city='新北市' AND venue='合計' ORDER BY x, y` |

**註：** 1011/1015 metrotaipei 視覺上「TPE 線長 NTPC 一點」是接受的 tradeoff（資料事實如此 — MOHW 雙北 by-city 統計只有 115 年公開）— `long_desc` 明確標註「TPE 含 2006-2025 完整序列；NTPC 自 2026 年起公開」。

---

## 6. FE / BE 變更與驗證

### 6.1 Backend
**零變更。** 5 個 query_charts 都走既有 `/api/v1/component/<id>/chart` 端點，由 `query_charts.query_chart` 內 SQL 動態執行。無新 controller / route / model。

### 6.2 Frontend
**零變更。** 5 個 dashboard 註冊的 component types 為 `ColumnLineChart / BarChart / MapLegend / DonutChart / BarChart`，全部已存在 base 上。**不 cherry-pick** `SearchableFoodSafetyTable.vue`（沒有 component 用它，違反「Surgical Changes」原則；未來真要做違規快查表再單獨開 PR）。

### 6.3 驗證 Checklist

| # | 項目 | 怎麼驗 |
|---|------|--------|
| 1 | 7 張 food 表都有資料 | apply.sh 結尾的 row count，每張 > 0 |
| 2 | dashboard 503 註冊成功 | `psql -c "SELECT * FROM dashboards WHERE id=503"` 回 1 row |
| 3 | 10 筆 query_charts 註冊（5 components × 2 city） | `SELECT COUNT(*) FROM query_charts WHERE index LIKE 'food_%'` = 10 |
| 4 | GeoJSON 兩個檔產生 | `ls FE/public/mapData/food_*.geojson` |
| 5 | FE build 通過（雖然 FE 變更 = 0 仍要驗證 base 沒壞） | `cd FE && npm run build` 無 error |
| 6 | 瀏覽器看到 dashboard | 登入 → 食安風險追蹤器 → 5 張卡片皆有資料；metrotaipei 1012/1014 真雙北、1011/1015 看得到 NTPC 點 |
| 7 | rollback 後 DB 乾淨 | `rollback.sh` → dashboard 503 不存在、7 張表都 drop、labor 1005-1010/1019/502 完好 |
| 8 | 重跑 apply 仍成功 | rollback → apply → 結果與第一次一致（idempotent 證明） |
| 9 | labor dashboard 502 不受影響 | apply 前後都能看 dashboard 502 全部 6 cards |

### 6.4 交付清單

```
新增（scripts/food_safety/）：
  README.md                           apply.sh / rollback.sh / backup_db.sh
  _db_env.sh / .env.script.example / .gitignore / backups/.gitkeep
  migrations/001_create_tables.up.sql / .down.sql       (7 張表)
  migrations/002_seed_dashboard.up.sql / .down.sql      (5 components + 10 query_charts + 2 maps + dashboard 503)
  etl/_db.py / .geocode_cache.json
  etl/snapshot_apis.py
  etl/load_inspection_tpe.py
  etl/load_restaurant_tpe.py
  etl/load_factory_ntpc.py
  etl/load_mohw_dual_city.py
  etl/load_mohw_poisoning.py
  etl/generate_geojson.py
  snapshots/ntpc_food_factory.csv     (~1232 rows)

新增（docs/assets/）：    ← base = labor-safety-radar 上沒有，本次帶進來
  114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv
  臺北市食品衛生管理稽查工作-年度統計.csv
  臺北市食品衛生管理查驗工作-年度統計.csv
  10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx
  10521-05-01食品中毒案件病因物質分類統計.xlsx
  10521-05-03食品中毒案件攝食場所分類統計.xlsx

新增（docs/plans/）：
  2026-05-02-food-safety-radar-design.md     ← 本 spec

不變更：
  Backend / Frontend / labor_safety 任何檔
```

### 6.5 Commits 切法

1. `docs(food-safety): add isolation design spec`
2. `feat(food-safety): scaffold migrations + apply/rollback/backup scripts`
3. `feat(food-safety): add ETL loaders + NTPC factory snapshot + MOHW xlsx parsers + assets`
4. `feat(food-safety): register dashboard 503 with 5 components (real dual-city)`

每個 commit 自身可 build。Commit 4 完成後 dashboard 503 完整可見；spec 先進去（commit 1）讓 PR 描述穩固。

---

## 開放議題 / 風險

| 風險 | 緩解 |
|---|---|
| MOHW xlsx 城市欄位 / venue label 對齊（全形/半形/空白）| `normalize_city()` / `normalize_venue()` 在 loader 統一；對不齊則 row 丟掉並 log，apply.sh 看 row count > 0 |
| MOHW 10521-01-03 xlsx 結構複雜（既有 `generate_food_type_violations_sql.py` 內 `CATEGORY_COLS` 已映射欄位範圍）| 直接複用該欄位映射邏輯，不重新摸索 |
| NTPC factory API 改格式 | 已 snapshot 化 → ETL 不再依賴；下次真要更新時重跑 `snapshot_apis.py` |
| ArcGIS Geocoder 改格式 / 限速 | `.geocode_cache.json` 已 commit；apply 階段純讀 cache，cache miss 走 district centroid fallback |
| FE build 在新分支因 base 不同找不到 dependency | base = labor-safety-radar，labor 分支 FE build 已通過驗證；本次 FE 變更 = 0，理論上必通過 |
| 食安資料檔（CSV/xlsx）大小（最大 2.7 MB） | 沿用 commit fbd23a2 既有大小，可接受；不另作 LFS |

### 實作期發現的資料缺口（query 對照修正）

實作 T11 後確認 MOHW 10521-01-03 xlsx 結構與初始假設不符：

1. **無 by-city × by-venue 細分**：xlsx 僅提供 city-level 合計（venue='合計' 一筆 / 城市 / 年），不包含餐飲店/冷飲店/...等 6 種場所的 by-city breakdown。
2. **無 by-city poisoning_cases**：xlsx 列出 by-city 不合格家次與不符規定比率，但「食物中毒人數」僅在 TPE 自有 CSV，新北無 by-city 公開。
3. **跨年度資料**：xlsx 是多年（2007-2025）多 sheet，非單一 115 年。

對應 query 改寫：
- **1011 metrotaipei** 從「TPE poisoning + NTPC poisoning」改為「TPE 不合格場所 + NTPC 不合格場所 + TPE 食物中毒人數」三條線；NTPC 不合格場所數來自 `food_inspection_by_city` (2010-2025)。
- **1012 metrotaipei** 從「by-venue × by-city」改為「by-year × by-city 合計 NC 件數」，雙城近 8 年並列。
- **1014 metrotaipei** 加上 `GROUP BY category, city` 與 `year >= 2020` 累計。
- **1015 metrotaipei** 從硬碼 '2026' 單點改為 2018-2025 雙城序列。

`food_poisoning_cause` 仍 populated 但暫未 wired（per 設計 §4 fallback 用途）。

### 第二輪調整：雙北 BarChart/DonutChart 視覺合併

`two_d` 為單一 series，雙北資料若同 series 顯示則「臺北 2025 / 新北 2025 / 臺北 2024 ...」交替成 16 條獨立 bar，視覺切碎。改採：

| Component | 改動 | 原因 |
|---|---|---|
| 1012 場所不合格率 → 場所不合格件數 | unit `%` → `件`；query_type → `three_d`（metrotaipei）；taipei 改顯示 NC 件數 | three_d 為 `int` 才能維持精度 + 由 BarChart `stacked:true` 自然分組 |
| 1015 年度檢驗違規率 → 年度檢驗違規件數 | 同上 | 同上 |
| 1014 違規原因分析 metrotaipei | 取消 city 在 x_axis suffix；改 `GROUP BY category` 雙城合併為單一 donut | DonutChart 不支援 multi-series；user 偏好「相同類型一起顯示」 |

語義轉換：1012/1015 從 rate(%) 改為 count(件)。Component 名稱跟著從「不合格率/違規率」改為「不合格件數/違規件數」以名實一致。三個 component 改完後雙北資料在視覺上同年度 stacked，相同類型不再切分。
| labor 與 food 同 base 分支整合進 develop 時的衝突 | 兩者 components / dashboard / migrations / scripts 完全不重疊；docs/assets/ 各加各的檔，不衝突 |
