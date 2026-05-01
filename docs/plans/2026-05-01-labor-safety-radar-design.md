# 工作安全燈號 Labor Safety Radar — 獨立化設計文件

- **日期：** 2026-05-01
- **目標分支：** `feat/labor-safety-radar`（從 `9bcf8c6728b5802b07e30737384131a838c5f7ff` 切出）
- **背景：** 黑客松前夕，團隊內部討論「工作安全燈號」具評審競爭力。需要把目前混雜在 `feat/green-mobility-dashboard` 分支內的 labor safety 實作獨立成一個自包含、可重複執行、有 rollback 機制、不依賴外部 API 的乾淨分支。
- **基準 commit：** `9bcf8c6` 之後分支上才陸續加入 labor safety 與其他主題（food / disaster / recheck / employment / green mobility），需要把僅 labor 相關的部分抽出。

---

## 設計目標

1. **流程穩定可重現** — 任何人在任何網路狀態下，從 0 到 dashboard 502 可見，必須一路順跑。
2. **CSV ⇒ ETL ⇒ DB 全鏈路** — 禁止 ETL 階段呼叫外部 API；所有資料一律從 repo 內 CSV 讀。
3. **可 rollback** — 套用、回退、再套用，DB 狀態必須一致；不留半套狀態、不污染既有資料。
4. **PR 合併友善** — 別人重跑 apply/rollback 不會破壞別人的資料；TRUNCATE 範圍嚴格限制在 labor 自有的表。
5. **比賽 demo 零意外** — 即使主辦方場館網路斷線、API 改格式，本 dashboard 仍可正常 demo。
6. **遵守 CLAUDE.md 雙北原則** — 6 個 components 全部要有 taipei + metrotaipei 兩筆 query_charts。

---

## 1. 目錄結構

```
Taipei-City-Dashboard/
├── scripts/labor_safety/                    ← 所有 labor 相關集中在此
│   ├── README.md                            ← 流程圖 + 重跑指令
│   ├── migrations/
│   │   ├── 001_create_tables.up.sql         ← CREATE TABLE labor_violations_tpe …
│   │   ├── 001_create_tables.down.sql       ← DROP TABLE …
│   │   ├── 002_seed_dashboard.up.sql        ← INSERT components / charts / maps / dashboard 502
│   │   └── 002_seed_dashboard.down.sql      ← DELETE … WHERE index LIKE 'labor_%' / id BETWEEN 1005 AND 1010
│   ├── etl/
│   │   ├── snapshot_apis.py                 ← 一次性備料：4 API → CSV，跑完即離線
│   │   ├── load_violations_tpe.py           ← CSV → labor_violations_tpe
│   │   ├── load_violations_ntpc.py          ← CSV → labor_violations_ntpc
│   │   ├── load_disasters.py                ← CSV → labor_disasters_tpe / labor_disasters_ntpc
│   │   ├── load_stats_tpe.py                ← CSV → labor_disputes_industry_tpe / labor_market_health_tpe
│   │   └── generate_disaster_geojson.py     ← labor_disasters_* → FE/public/mapData/labor_disasters_*.geojson
│   ├── snapshots/                           ← API 快照 CSV，commit 進 repo
│   │   ├── tpe_occupational_safety_violations.csv
│   │   ├── tpe_major_disasters.csv
│   │   ├── ntpc_labor_violations.csv
│   │   ├── ntpc_gender_equality_violations.csv
│   │   ├── ntpc_occupational_safety_violations.csv
│   │   └── ntpc_major_disasters.csv
│   ├── apply.sh                             ← 一鍵套用：migrations → ETL → 印 row count
│   ├── rollback.sh                          ← 一鍵還原：down.sql + 清 GeoJSON
│   └── backup_db.sh                         ← pg_dump 兩個 DB 到 ./backups/<timestamp>/
├── docs/assets/                             ← 既有 4 個 TPE CSV 沿用原位置
│   ├── 違法名單總表-CSV檔1150105勞基.csv
│   ├── 臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv
│   ├── 勞資爭議統計依行業別區分(11503).csv
│   └── 臺北市勞工保險及就業服務按月別.csv
├── docs/plans/2026-05-01-labor-safety-radar-design.md   ← 本文件
└── Taipei-City-Dashboard-FE/src/dashboardComponent/
    ├── components/SearchableViolationTable.vue          ← 新增
    ├── DashboardComponent.vue                           ← patch（+import +case）
    └── utilities/chartTypes.ts                          ← patch（+1 entry）
```

**要點：**
- 4 個原本就是 CSV 的 TPE 資料留在 `docs/assets/`（不搬，避免動到既有路徑、其他主題之後也可能用）
- 4 個 API snapshot 放在 `scripts/labor_safety/snapshots/`（labor 自有，不污染 docs/assets）
- 整個 `scripts/labor_safety/` 資料夾刪掉就等於拔掉這個 dashboard

---

## 2. Migration、Rollback、備份機制

### 2.1 `backup_db.sh`（永遠先跑）

```bash
#!/usr/bin/env bash
set -euo pipefail
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$(dirname "$0")/backups/$TS"
mkdir -p "$OUT"

docker exec postgres-data    pg_dump -U postgres -d dashboard        > "$OUT/dashboard.sql"
docker exec postgres-manager pg_dump -U postgres -d dashboardmanager > "$OUT/dashboardmanager.sql"

echo "✅ backup → $OUT"
ls -lh "$OUT"
```

- container / DB / user 名以實際 `docker/.env` 為準（執行時先 `docker ps` 確認再寫死）
- `scripts/labor_safety/backups/` 加進 `.gitignore`，**不 commit dump**
- README 教 restore：`docker exec -i postgres-data psql -U postgres -d dashboard < backups/<ts>/dashboard.sql`

### 2.2 `apply.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "▶ 1/3 migrations up …"
docker exec -i postgres-data    psql -U postgres -d dashboard        -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.up.sql"
docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"

echo "▶ 2/3 ETL …"
python3 "$ROOT/etl/load_violations_tpe.py"
python3 "$ROOT/etl/load_violations_ntpc.py"
python3 "$ROOT/etl/load_disasters.py"
python3 "$ROOT/etl/load_stats_tpe.py"
python3 "$ROOT/etl/generate_disaster_geojson.py"

echo "▶ 3/3 verify row counts …"
docker exec -i postgres-data psql -U postgres -d dashboard -c "
  SELECT 'labor_violations_tpe'        AS t, COUNT(*) FROM labor_violations_tpe
  UNION ALL SELECT 'labor_violations_ntpc',         COUNT(*) FROM labor_violations_ntpc
  UNION ALL SELECT 'labor_disasters_tpe',           COUNT(*) FROM labor_disasters_tpe
  UNION ALL SELECT 'labor_disasters_ntpc',          COUNT(*) FROM labor_disasters_ntpc
  UNION ALL SELECT 'labor_disputes_industry_tpe',   COUNT(*) FROM labor_disputes_industry_tpe
  UNION ALL SELECT 'labor_market_health_tpe',       COUNT(*) FROM labor_market_health_tpe;"
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

# 先拔註冊（避免 FE 還在 query 一個快被 drop 的表）
docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.down.sql"
# 再 DROP TABLE
docker exec -i postgres-data    psql -U postgres -d dashboard        -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.down.sql"

# 清 GeoJSON
rm -f ../../Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson
rm -f ../../Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson

echo "✅ rollback complete"
```

### 2.4 Migration 檔內容守則

- **每支 SQL 自己 BEGIN/COMMIT**（不只靠 `-1`，雙保險）
- `up.sql` 用 `CREATE TABLE IF NOT EXISTS` + `ON CONFLICT (index/id) DO NOTHING`，**重跑不會炸**
- `down.sql` 用 `DROP TABLE IF EXISTS … CASCADE` + `DELETE … WHERE id BETWEEN 1005 AND 1010`，**沒套用過也不會炸**
- 兩個方向都 idempotent ⇒ PR 合進 develop 後別人重跑也安全

### 2.5 從 0 重跑的標準流程

```bash
# 1. 備份
./scripts/labor_safety/backup_db.sh

# 2. 清 DB（整個 volume 炸掉）
docker compose -f docker/docker-compose-db.yaml down -v
docker compose -f docker/docker-compose-db.yaml up -d
sleep 10  # healthcheck

# 3. 跑 base init
docker compose -f docker/docker-compose-init.yaml up -d

# 4. 套 labor safety
./scripts/labor_safety/apply.sh

# 5. 開 http://localhost:8080 → shift+logo 登入 → dashboard 502 → 6 張卡片皆有資料
```

---

## 3. ETL 與 API Snapshot

### 3.1 `snapshot_apis.py`（一次性備料工具）

```python
"""
從 data.taipei / data.ntpc 把 4 個（共 6 個 endpoint）API 抓下來，存成 CSV。
這支腳本「不」是 ETL 流程的一部分 — 是離線備料工具。
跑完 commit snapshots/*.csv 進 repo 之後，apply.sh 就只讀 CSV。
"""
SOURCES = [
    ("tpe_occupational_safety_violations.csv",
     "https://data.taipei/api/dataset/.../resource/90d05db5-d46f-4900-a450-b284b0f20fb9/json"),
    ("tpe_major_disasters.csv",
     "https://data.taipei/api/dataset/.../resource/ab4ddbe2-90f5-49a6-a7ad-45e5b6d14871/json"),
    ("ntpc_labor_violations.csv",
     "https://data.ntpc.gov.tw/api/datasets/a3408b16-7b28-4fa5-9834-d147aae909bf/json"),
    ("ntpc_gender_equality_violations.csv",
     "https://data.ntpc.gov.tw/api/datasets/d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4/json"),
    ("ntpc_occupational_safety_violations.csv",
     "https://data.ntpc.gov.tw/api/datasets/8ec84245-450b-45df-9bc5-510ab6e02e73/json"),
    ("ntpc_major_disasters.csv",
     "https://data.ntpc.gov.tw/api/datasets/80743c0e-b7e7-4d4a-825b-df354a542f65/json"),
]
# 對每個 source：分頁抓全部 → DictWriter 輸出到 snapshots/
# 結尾印 row count，與下表預期值對表
```

**預期 row count（驗收標準）：**

| Snapshot | 預期 ±5% |
|---|---|
| tpe_occupational_safety_violations.csv | 數千 |
| tpe_major_disasters.csv | 數百 |
| ntpc_labor_violations.csv | ~14,155 |
| ntpc_gender_equality_violations.csv | ~47 |
| ntpc_occupational_safety_violations.csv | ~4,148 |
| ntpc_major_disasters.csv | ~206 |

### 3.2 Loader 5 條鐵則

```python
def main():
    rows = parse_csv(SRC_CSV)               # 純檔案讀取，無網路
    cleaned = [transform(r) for r in rows]  # 日期 ROC→AD、欄位映射、缺值處理
    cleaned = [r for r in cleaned if r]     # drop None

    with conn() as c, c.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE labor_xxx_table")
        psycopg2.extras.execute_values(cur, INSERT_SQL, cleaned)
        cur.execute("COMMIT")
    print(f"✅ {len(cleaned)} rows → labor_xxx_table")
```

1. **TRUNCATE before INSERT** — 不堆疊、可重跑
2. **整個寫入包一個 transaction** — 中途失敗 ROLLBACK，不會半套
3. **沒有任何 HTTP 呼叫** — 一律從 `docs/assets/` 或 `snapshots/` 讀
4. **寫入後印 row count** — apply.sh 結尾才能交叉驗證
5. **transform 失敗（壞資料）只記 log 不 abort** — 個別 row 丟掉，整體仍能完成

### 3.3 Loader → 資料表對應

| Loader | 讀 | 寫到表 |
|---|---|---|
| `load_violations_tpe.py` | `docs/assets/違法名單總表-CSV檔1150105勞基.csv`（UTF-8 BOM）+ 性平法 CSV（Big5）+ `snapshots/tpe_occupational_safety_violations.csv` | `labor_violations_tpe` |
| `load_violations_ntpc.py` | `snapshots/ntpc_labor_violations.csv` + `ntpc_gender_equality_violations.csv` + `ntpc_occupational_safety_violations.csv` | `labor_violations_ntpc` |
| `load_disasters.py` | `snapshots/tpe_major_disasters.csv` + `ntpc_major_disasters.csv` | `labor_disasters_tpe`、`labor_disasters_ntpc` |
| `load_stats_tpe.py` | `docs/assets/勞資爭議統計依行業別區分(11503).csv`（Big5）+ `docs/assets/臺北市勞工保險及就業服務按月別.csv` | `labor_disputes_industry_tpe`、`labor_market_health_tpe` |
| `generate_disaster_geojson.py` | DB: `labor_disasters_tpe`、`labor_disasters_ntpc` | `FE/public/mapData/labor_disasters_*.geojson` |

GeoJSON 產生器讀 DB 而非 CSV，所以放 apply.sh 最後一步。

### 3.4 雙北原則處理

依 CLAUDE.md「最高原則」：**6 個 components 全部都要有 taipei + metrotaipei 兩筆 query_charts。**

- 即使 `labor_disputes_industry_tpe`、`labor_market_health_tpe` 目前只有 TPE 統計資料，metrotaipei 版本也要存在（用同一張 TPE 表查詢，short_desc 明確標註「目前僅含臺北市」）。比照 food_safety 處理。
- 任一邊抓不到資料 → loader 結尾 row count 為 0 → apply.sh 偵測為 0 直接 fail，逼使用者察覺。

---

## 4. FE / BE 變更與驗證

### 4.1 Backend
**零變更。** labor safety 的 6 個 query_charts 都走既有 `/api/v1/component/<id>/chart` 端點，由 `query_charts.query_chart` 欄位內的 SQL 動態執行。無新 controller / route / model。

### 4.2 Frontend（3 個檔案，最小變更）

**新增：** `Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue`
（直接從當前 working tree 拷貝，不修改邏輯）

**Patch：** `DashboardComponent.vue`
```diff
+ import SearchableViolationTable from "./components/SearchableViolationTable.vue";
  …
  case "MapLegend": …
+ case "SearchableViolationTable":
+     return svg ? MapLegendSvg : SearchableViolationTable;
```

**Patch：** `utilities/chartTypes.ts`
```diff
+ SearchableViolationTable: "雙北違規快查表",
```

**為何用 patch 而非整檔覆蓋：** 從 `9bcf8c6` 切出去的版本，這兩個共享檔還沒被 food_safety / disaster / recheck 等其他主題改過。直接覆蓋會把當前分支「已合進去的別主題 import」也帶過去，違反「獨立」原則。

### 4.3 驗證 Checklist

| # | 項目 | 怎麼驗 |
|---|------|--------|
| 1 | 6 張 labor 表都有資料 | apply.sh 結尾的 row count，每張 > 0 |
| 2 | dashboard 502 註冊成功 | `psql -c "SELECT * FROM dashboards WHERE id=502"` 回 1 row |
| 3 | 12 筆 query_charts 註冊（6 components × 2 city） | `SELECT COUNT(*) FROM query_charts WHERE index LIKE 'labor_%'` = 12 |
| 4 | GeoJSON 兩個檔產生 | `ls FE/public/mapData/labor_disasters_*.geojson` |
| 5 | FE build 通過 | `cd FE && npm run build` 無 error |
| 6 | 瀏覽器看到 dashboard | 登入 → 工作安全燈號 → 6 張卡片皆有資料 |
| 7 | rollback 後 DB 乾淨 | `rollback.sh` → dashboard 502 不存在、6 張表都 drop |
| 8 | 重跑 apply 仍成功 | rollback → apply → 結果與第一次一致（idempotent 證明） |

### 4.4 交付清單

```
新增：
  scripts/labor_safety/README.md
  scripts/labor_safety/apply.sh
  scripts/labor_safety/rollback.sh
  scripts/labor_safety/backup_db.sh
  scripts/labor_safety/migrations/001_create_tables.up.sql
  scripts/labor_safety/migrations/001_create_tables.down.sql
  scripts/labor_safety/migrations/002_seed_dashboard.up.sql
  scripts/labor_safety/migrations/002_seed_dashboard.down.sql
  scripts/labor_safety/etl/snapshot_apis.py
  scripts/labor_safety/etl/load_violations_tpe.py
  scripts/labor_safety/etl/load_violations_ntpc.py
  scripts/labor_safety/etl/load_disasters.py
  scripts/labor_safety/etl/load_stats_tpe.py
  scripts/labor_safety/etl/generate_disaster_geojson.py
  scripts/labor_safety/snapshots/*.csv  (6 個)
  Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue
  docs/plans/2026-05-01-labor-safety-radar-design.md (本文件)

修改：
  Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue (+~3 lines)
  Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts (+1 line)
  .gitignore (+ scripts/labor_safety/backups/)

從原 docs/assets/ 沿用（不動）：
  違法名單總表-CSV檔1150105勞基.csv
  臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv
  勞資爭議統計依行業別區分(11503).csv
  臺北市勞工保險及就業服務按月別.csv
```

### 4.5 Commits 切法（B 方案）

1. `feat(labor-safety): scaffold migrations + apply/rollback/backup scripts`
2. `feat(labor-safety): add ETL loaders + API snapshots`
3. `feat(labor-safety): register dashboard 502 with 6 components (dual-city)`
4. `feat(labor-safety): add SearchableViolationTable + FE wiring`

每個 commit 自身可 build / 部分可跑（commit 1 後 apply 會 fail 但目錄結構就位；commit 3 後 DB 完整；commit 4 後 FE 完整）。

---

## 開放議題 / 風險

| 風險 | 緩解 |
|---|---|
| TPE 職安法 API row count 估「數千」太模糊 | 跑 snapshot 時實際數出來，寫進 README 當基準 |
| `data.taipei` API URL 結構（dataset id vs resource id）不統一 | snapshot_apis.py 開發時先以 `curl` 確認每個 endpoint 的實際回應結構 |
| Big5 編碼處理（性平法、勞資爭議） | loader 內統一 `encoding="big5"` 並強制 `errors="replace"` 防個別字元爆炸 |
| docker container / DB / user 名假設 | 寫 backup_db.sh 前先 `docker ps` 與 `cat docker/.env` 對齊真實值 |
| FE build 在新分支可能因 base 太舊找不到 dependency | 先確認 `9bcf8c6` 對應的 `package.json` 與 `package-lock.json` 可正常 `npm install` |
