# 雙北食品查核及檢驗稽查紀錄 — Standalone ETL

獨立 standalone ETL，不走 Airflow，把雙北 v2 CSV 灌進 `dashboard` DB 的 `food_safety_inspection_metrotaipei` 表。

> 與 Airflow DAG（`Taipei-City-Dashboard-DE/dags/proj_city_dashboard/food_safety_inspection_metrotaipei/`）互相獨立、可同時存在。`apply.sh` 適合一次性匯入，DAG 適合排程持續更新。

## Layout

```
scripts/food_safety_inspection_metrotaipei/
├── apply.sh / rollback.sh / backup_db.sh
├── _db_env.sh                  # 憑證解析 + pg_psql/pg_dump_to fns
├── .env.script.example         # cp 為 .env.script 後依環境改
├── migrations/
│   ├── 001_create_table.up.sql      # food_safety_inspection_metrotaipei
│   └── 001_create_table.down.sql
├── etl/
│   ├── _db.py
│   └── load_inspection.py      # 讀 data/*.csv，寫入單一表
└── backups/                    # gitignored — pg_dump output
```

資料來源 CSV 維持在 repo root 的 [data/](../../data/)：

- `食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場_v2.csv`
- `食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者_v2.csv`

## 一、設定 `.env.script`

```bash
cp scripts/food_safety_inspection_metrotaipei/.env.script.example \
   scripts/food_safety_inspection_metrotaipei/.env.script
```

挑一個 profile（local docker / cloud）打開，把另一段註解掉。重點：

| 環境 | `DB_DASHBOARD_HOST` | `PG_DOCKER_NETWORK` |
| --- | --- | --- |
| 本機 docker（`postgres-data` 沒對外 port）| `postgres-data`（內部 hostname）| `br_dashboard` |
| Cloud / 任何有公開 hostname 的 DB | 公開 host | `host` |

預設值（`docker/.env` 已填的 `DB_DASHBOARD_*`）會自動被讀進來，所以本機 docker 通常 `cp` 一份就能跑。

## 二、執行

```bash
# (建議) 先備份
./scripts/food_safety_inspection_metrotaipei/backup_db.sh

# 建表 + 灌資料
./scripts/food_safety_inspection_metrotaipei/apply.sh
```

`apply.sh` 會：
1. 跑 `migrations/001_create_table.up.sql` 建表（`CREATE TABLE IF NOT EXISTS`，可重跑）
2. 起一個 `python:3.11-slim` sidecar，掛 br_dashboard 網路 + 掛 repo 進去，跑 `etl/load_inspection.py`
3. 列出 `business_type` 分組 row count；若 0 列直接 fail

`load_inspection.py` 的 transform：
- 讀兩支 CSV，加 `business_type` 欄位，合併
- 中文欄位 → snake_case
- `業者地址` 把 `台北市` 正規成 `臺北市`，再切出 `city` / `district`
- `稽查日期` 民國 → 西元 (`110/11/2` → `2021-11-02`)
- `裁罰金額` numeric coerce
- `data_time` 用 `NOW()` 一次性蓋整批
- `TRUNCATE` → `INSERT` 在單一 transaction 內

## 三、重跑

`apply.sh` 是 idempotent — 直接再跑一次。`TRUNCATE` 會清掉舊資料再灌。

## 四、Rollback

```bash
./scripts/food_safety_inspection_metrotaipei/rollback.sh
```

`DROP TABLE IF EXISTS food_safety_inspection_metrotaipei CASCADE`。Idempotent。

## 五、從 backup 還原

```bash
source scripts/food_safety_inspection_metrotaipei/_db_env.sh
cat scripts/food_safety_inspection_metrotaipei/backups/<TS>/dashboard.sql \
  | docker run --rm -i --network="$PG_DOCKER_NETWORK" "$PG_CLIENT_IMAGE" \
      psql "$DB_URL_DASHBOARD"
```

## 六、跟 Airflow DAG 的關係

| 項目 | DAG（DE 模組）| Standalone scripts（這裡）|
| --- | --- | --- |
| 觸發 | Airflow scheduler / UI | `./apply.sh` 手動 |
| DB 憑證來源 | Airflow connection `postgres_default` | `.env.script` / `docker/.env` |
| CSV 位置 | DAG 資料夾內 co-located copy | repo root `data/` |
| 重跑語意 | `replace`（TRUNCATE + INSERT，pandas）| 同上（psycopg2 TRUNCATE + execute_values）|
| 目標表 | `food_safety_inspection_metrotaipei` | 一致 |
| 何時用 | 上線排程後持續更新 | 一次性匯入 / 開發環境 / 沒有 Airflow 時 |

兩者寫同一張表，用任一個都行；通常先用 `apply.sh` 灌進來開發測試，DAG 只是把同一段邏輯排程化。
