# School Meal Ingredients — 校園食材登入平台 ETL

Crawl 校園食材登入平台 OpenAPI for 雙北 全年月 CSV datasets, then dedupe
食材名稱 into a dictionary table for downstream AI consumers.

Mirrors the layout and conventions of `scripts/labor_safety/`.

## Quick start

> Run all commands from the repo root.

```bash
# 0. Copy and edit env file
cp scripts/school_meal_ingredients/.env.script.example \
   scripts/school_meal_ingredients/.env.script
$EDITOR scripts/school_meal_ingredients/.env.script
# Set FATRACE_ACCESSCODE, FATRACE_COOKIE, DB_DASHBOARD_*

# 1. (Optional) Refresh CSV snapshots from the live API
#    Long-running. Use --year-from/--year-to to limit scope.
python3 scripts/school_meal_ingredients/etl/snapshot_apis.py

# 2. Backup before applying (idempotent migration, but be safe)
./scripts/school_meal_ingredients/backup_db.sh

# 3. Apply: migrations + raw loader + dedupe loader + verify
./scripts/school_meal_ingredients/apply.sh

# 4. Rollback (drops the table)
./scripts/school_meal_ingredients/rollback.sh
```

## Layout

```
scripts/school_meal_ingredients/
├── README.md                    # this file
├── .env.script.example          # FATRACE_* + DB_DASHBOARD_* template
├── .gitignore                   # backups/, .env.script, __pycache__
├── apply.sh                     # idempotent: migrations + ETL + verify
├── rollback.sh                  # drop table
├── backup_db.sh                 # pg_dump dashboard
├── _db_env.sh                   # shell env (sourced by *.sh)
├── etl/
│   ├── _db.py                   # psycopg2 kwargs + FATRACE creds resolver
│   ├── snapshot_apis.py         # resumable API crawler (manual run)
│   ├── load_raw_records.py      # CSV → 6 typed raw tables (apply.sh step 2/4)
│   └── load_ingredient_names.py # CSV → dedupe → DB (apply.sh step 3/4)
├── snapshots/                   # committed CSVs + manifest.json
└── migrations/
    ├── 001_create_ingredient_names.up.sql
    ├── 001_create_ingredient_names.down.sql
    ├── 002_create_raw_tables.up.sql
    └── 002_create_raw_tables.down.sql
```

## Data flow

```
                 (manual)
fatraceschool API ─────► snapshot_apis.py ─► snapshots/*.csv + manifest.json
                                                       │
                                          (apply.sh)   │
                                              ┌────────┴────────┐
                                              ▼                 ▼
                                  load_raw_records.py   load_ingredient_names.py
                                              │                 │
                                              ▼                 ▼
                                  dashboard.school_meal_     dashboard.school_meal_
                                  {food_dictionary,          ingredient_names
                                   caterers,
                                   seasoning_records_nation,
                                   ingredient_records,
                                   dish_records,
                                   dish_ingredient_records}
```

`apply.sh` reads only committed CSVs; it does **not** call the live API.
Run `snapshot_apis.py` separately when you want to refresh the snapshots.

## Datasets in scope

The platform exposes 6 unique `datasetname` values; we download:

| Dataset | County / grade | Source of 食材名稱? |
|---|---|---|
| 學校供餐團膳業者資料集 | 全國 | no |
| 調味料及供應商資料集 | 全國 | maybe |
| 午餐食材及供應商資料集 | 臺北市 / 新北市 × 國中小 / 高中職 | **yes** |
| 午餐菜色資料集 | 臺北市 / 新北市 × 國中小 / 高中職 | no |
| 午餐菜色及食材資料集 | 臺北市 / 新北市 × 國中小 / 高中職 | **yes** |
| 食材中文名稱資料集 | one-shot | yes (standard names) |

The `全國 × 國中小/高中職` variants are **skipped** to avoid superset
duplication of the city-specific data.

## Raw record tables (apply.sh step 2/4)

`load_raw_records.py` lands every CSV's rows into a typed table. Re-running
the loader TRUNCATEs each target before INSERT, so apply.sh stays idempotent.

| Table | Source CSV | Provenance columns? |
|---|---|---|
| `school_meal_food_dictionary` | `food_chinese_names.csv` | no — one-shot dictionary |
| `school_meal_caterers` | `nation_*_學校供餐團膳業者*.csv` | no — country-wide list |
| `school_meal_seasoning_records_nation` | `nation_*_調味料及供應商*.csv` | no — entries carry their own start/end dates |
| `school_meal_ingredient_records` | `(tpe\|ntpc)_*_*_午餐食材及供應商*.csv` | yes — `year_queried, month_queried, county_queried, grade_queried` |
| `school_meal_dish_records` | `(tpe\|ntpc)_*_*_午餐菜色資料集.csv` | yes — same 4 |
| `school_meal_dish_ingredient_records` | `(tpe\|ntpc)_*_*_午餐菜色及食材*.csv` | yes — same 4 |

The dedupe table `school_meal_ingredient_names` (apply.sh step 3/4) is
unchanged — still derived from the same CSV scan with column-detection +
fallback.

## Snapshot crawler — token expiry

`accesscode` and `JSESSIONID` expire per session. When the API rejects
the token, `snapshot_apis.py`:

1. Saves `manifest.json` with what's been completed.
2. Prints `⚠️  FATRACE token expired …` to stderr.
3. Exits **0** (so a wrapper script can rerun cleanly).

Refresh `FATRACE_ACCESSCODE` / `FATRACE_COOKIE` and rerun — it picks up
where it left off.

## Time range

Default: `2020/01` → current month. Override:

```bash
python3 .../snapshot_apis.py --year-from 2024 --month-from 1 \
                             --year-to 2024 --month-to 12
```

Months that return empty `datasetList` are recorded so subsequent runs
skip them.

## Dual-city compliance

Per project CLAUDE.md, the loader **aborts** unless both 臺北市 AND 新北市
appear in the aggregated `source_counties`. This catches accidental
single-city snapshots before they reach the DB.

## Restore from backup

```bash
source scripts/school_meal_ingredients/_db_env.sh
cat scripts/school_meal_ingredients/backups/<TS>/dashboard.sql \
  | docker run --rm -i --network=host "$PG_CLIENT_IMAGE" psql "$DB_URL_DASHBOARD"
```
