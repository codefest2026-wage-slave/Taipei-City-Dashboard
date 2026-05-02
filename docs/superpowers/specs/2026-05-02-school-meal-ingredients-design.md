# School Meal Ingredients ETL — Design

**Status:** Draft for user review
**Date:** 2026-05-02
**Branch:** `feat/school-meal-ingredients-etl` (based on `origin/feat/labor-safety-radar`)
**Pattern reference:** `scripts/labor_safety/` (mirrors layout, scripts, conventions)

## Goal

Two ETL pipelines:

1. **Snapshot ETL** — fetch all year/month CSV datasets for 臺北市 + 新北市 from
   the 校園食材登入平台 OpenAPI (`fatraceschool.k12ea.gov.tw/cateringservice/openapi/`).
2. **Dedupe ETL** — extract unique 食材名稱 values across the snapshot CSVs into a
   new dictionary table for downstream AI consumers.

## Non-goals

- No FE changes, no Airflow DAGs, no dashboard registration. Scripts only.
- `apply.sh` will NOT call `snapshot_apis.py` (matches labor-safety: snapshots are
  a manual refresh, ETL only reads committed CSVs).
- DB will NOT be written to during this delivery. User runs `apply.sh` themselves.

## Source API

Base: `https://fatraceschool.k12ea.gov.tw/cateringservice/openapi/`

| Endpoint | Purpose | Body |
|---|---|---|
| `POST /county/` | Sanity / list counties | `{accesscode}` |
| `POST /opendatadataset/` | List datasets for (year, month, county) | `{accesscode, year, month, county}` |
| `POST /opendatadownload/` | Get CSV download link | `{accesscode, year, month, county, grade, datasetname}` |

Auth: `accesscode` body field + `JSESSIONID` cookie. Both treated as ephemeral; loaded
from `.env.script` and overridable via env / CLI flag (see Resume strategy).

### Datasets in scope (per Q1 = C: all unique datasetnames)

The API returns **6 unique `datasetname`** values across multiple
`(county, grade)` variants per `(year, month)`:

| # | datasetname | Variants returned |
|---|---|---|
| 1 | 學校供餐團膳業者資料集 | 全國 only |
| 2 | 調味料及供應商資料集 | 全國 only |
| 3 | 午餐食材及供應商資料集 | city × grade  AND  全國 × grade |
| 4 | 午餐菜色資料集 | city × grade  AND  全國 × grade |
| 5 | 午餐菜色及食材資料集 | city × grade  AND  全國 × grade |
| 6 | 食材中文名稱資料集 | one-shot (`year=""`, `month=""`) |

For a `(year, month, queried-county)` query the API mixes these as `datasetList`
entries; the crawler categorises each entry by `(county, grade)` shape:

| Shape | county | grade | Action |
|---|---|---|---|
| city × grade | `臺北市` / `新北市` | `國中小` / `高中職` | Always download |
| 全國-only | `全國` | `""` | Download once per `(year, month)` (dedupe across the two city queries) |
| 全國 × grade | `全國` | `國中小` / `高中職` | **Skip** (Q3 = A: city × grade already covers the same data, avoid superset duplication) |
| one-shot | `""` | `""` | Download once globally (`食材中文名稱資料集`) |

## Time range (Q2 = A)

- Auto-probe from `2020/01` to current month (default `2026/05`).
- Configurable via `--year-from / --year-to / --month-from / --month-to` env / CLI.
- A `(year, month)` that returns empty `datasetList` → log "no data" and continue
  (do not abort).

## Project layout (mirrors `scripts/labor_safety/`)

```
scripts/school_meal_ingredients/
├── README.md
├── .env.script.example       # FATRACE_ACCESSCODE, FATRACE_COOKIE, DB_DASHBOARD_*
├── .gitignore                # .env.script, backups/
├── apply.sh                  # idempotent: migrations + ETL + verify
├── rollback.sh               # migrations down
├── backup_db.sh              # pg_dump dashboard before apply
├── _db_env.sh                # shared shell env (mirrors labor_safety)
├── etl/
│   ├── _db.py                # psycopg2 kwargs (mirrors labor_safety/etl/_db.py)
│   ├── snapshot_apis.py      # the API crawler (resumable, env-driven token)
│   └── load_ingredient_names.py   # CSV → dedup → school_meal_ingredient_names
├── snapshots/
│   ├── manifest.json              # downloaded keys (resume + skip)
│   ├── tpe_202410_國中小_午餐食材及供應商資料集.csv
│   ├── ntpc_202410_高中職_午餐菜色及食材資料集.csv
│   ├── nation_202410_學校供餐團膳業者資料集.csv
│   └── food_chinese_names.csv     # one-shot 食材中文名稱資料集
├── backups/                  # .gitkeep + pg_dump output (gitignored)
└── migrations/
    ├── 001_create_ingredient_names.up.sql
    └── 001_create_ingredient_names.down.sql
```

CSV files are committed to git (Q5 = A) so the ETL is fully reproducible from
clone without hitting the live API.

## Snapshot crawler (`etl/snapshot_apis.py`)

### Inputs (in resolution priority)

| Source | Wins over |
|---|---|
| CLI flag (`--accesscode XXX`) | env / .env.script |
| `FATRACE_ACCESSCODE` env | .env.script |
| `.env.script` `FATRACE_ACCESSCODE` | (no default — hard fail if missing) |

Same pattern for `FATRACE_COOKIE` (JSESSIONID value or full cookie string).

CLI flags also accepted for time range:
`--year-from 2020 --month-from 1 --year-to 2026 --month-to 5`

### Filename convention

```
<county-code>_<YYYYMM>_<grade>_<datasetname>.csv
```

- `county-code`: `tpe` (臺北市) / `ntpc` (新北市) / `nation` (全國)
- `grade` omitted if blank → `nation_202410_學校供餐團膳業者資料集.csv`
- One special: `food_chinese_names.csv` for the 一次性 食材中文名稱資料集

### Manifest (`snapshots/manifest.json`)

```json
{
  "completed": [
    {"county": "臺北市", "year": "2024", "month": "10", "grade": "國中小",
     "datasetname": "午餐食材及供應商資料集", "filename": "tpe_202410_國中小_午餐食材及供應商資料集.csv",
     "downloaded_at": "2026-05-02T11:00:00", "rows": 1234}
  ],
  "empty_months": [
    {"county": "臺北市", "year": "2019", "month": "12"}
  ],
  "last_run_at": "2026-05-02T11:00:00"
}
```

Resume = filter out entries already in `completed` / `empty_months` before
issuing requests.

### Main loop (pseudocode)

```python
manifest = load_manifest()
seen_nation_keys = manifest.completed.filter(county=="全國").set_of_keys()
errors = []

for ym in months_in_range():
    for county in ["臺北市", "新北市"]:
        if (ym, county) in manifest.empty_months: continue
        try:
            datasetList = post_dataset(accesscode, ym, county)
        except TokenExpired:
            print("FATRACE_ACCESSCODE expired. Update .env.script and rerun.")
            graceful_exit(manifest)

        if not datasetList:
            manifest.empty_months.add((ym, county))
            save(manifest)
            continue

        for entry in datasetList:
            key = (entry.year, entry.month, entry.county, entry.grade, entry.datasetname)
            if key in manifest.completed: continue
            if not should_download(entry, queried_county=county, seen_nation_keys): continue

            try:
                link = post_download(accesscode, entry)
                csv_bytes = http_get(link)
                save_csv(filename(entry), csv_bytes)
                manifest.completed.add(key, rows=count_rows(csv_bytes))
                save(manifest)
            except TokenExpired:
                graceful_exit(manifest)
            except Exception as e:
                errors.append((key, str(e)))

            sleep(0.5)  # rate-limit politeness

    save(manifest)

print_summary(manifest, errors)
```

### `should_download` rules

| Entry | Decision |
|---|---|
| `entry.county == queried_county` AND `grade in {國中小, 高中職}` | Yes |
| `entry.county == "全國"` AND `grade == ""` AND key not in seen_nation_keys | Yes (city-loop downloads it once; subsequent city loops skip) |
| `entry.county == "全國"` AND `grade in {國中小, 高中職}` | **No** (Q3 = A) |
| `entry.year == "" AND entry.month == ""` (一次性) | Yes if not already in manifest |
| Otherwise | No |

### Failure modes

- **Token expired** (HTTP 401/403 OR JSON `message` containing `授權失敗 / token / 失效`):
  print actionable message, save manifest, exit 0 (so user can rerun cleanly).
- **Network error**: log to errors list, continue.
- **Empty CSV body**: log warning, do NOT add to manifest (will retry next run).
- **Per-month loop catches all exceptions** so one bad month doesn't kill the run.

## Migration (`migrations/001_create_ingredient_names.{up,down}.sql`)

Target DB: `dashboard` (matches labor-safety convention; tables for analytical
data go here, not `dashboardmanager`).

### `001_create_ingredient_names.up.sql`

```sql
BEGIN;

CREATE TABLE IF NOT EXISTS school_meal_ingredient_names (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) UNIQUE NOT NULL,
    occurrence      INTEGER       NOT NULL DEFAULT 0,
    first_seen_ym   VARCHAR(7),                       -- 'YYYY-MM'
    last_seen_ym    VARCHAR(7),                       -- 'YYYY-MM'
    source_counties TEXT[]                            -- e.g. {'臺北市','新北市'}
);

CREATE INDEX IF NOT EXISTS idx_school_meal_ingredient_names_name
    ON school_meal_ingredient_names (name);

COMMIT;
```

### `001_create_ingredient_names.down.sql`

```sql
BEGIN;
DROP TABLE IF EXISTS school_meal_ingredient_names;
COMMIT;
```

## Dedupe loader (`etl/load_ingredient_names.py`)

### Inputs

- All `snapshots/*.csv` in the script directory.
- `_db.py::db_kwargs()` for connection.

### Column detection

Each CSV may use slightly different headers. The loader:

1. Reads `csv.DictReader`. Fieldnames lower-cased & stripped for matching.
2. Tries exact match for `食材名稱`. If found → use it.
3. Else fallback: try `品名`, `食材`, `菜色`. **If a fallback matches, print
   warning** with filename + chosen column, so we can audit.
4. If none match, **skip the file** (some datasets — e.g. 學校供餐團膳業者 / 午餐菜色
   without 食材 column — legitimately have no ingredient-name column). Log skip
   reason.

### Aggregation

```python
agg = {}  # name -> {occurrence, first_ym, last_ym, counties_set}
for path in snapshots/*.csv:
    year, month, county = parse_filename(path)
    ym = f"{year}-{month:02}" if year else None
    col = detect_ingredient_column(path)
    if col is None: continue

    with open(path) as f:
        for row in csv.DictReader(f):
            name = (row.get(col) or "").strip()
            if not name: continue
            a = agg.setdefault(name, {"count": 0, "first": ym, "last": ym, "counties": set()})
            a["count"] += 1
            if ym:
                a["first"] = min(a["first"] or ym, ym)
                a["last"]  = max(a["last"]  or ym, ym)
            if county and county != "全國":
                a["counties"].add(county)

# Required: dual-city — ABORT if either 臺北市 or 新北市 is absent across all entries
all_counties = set().union(*(v["counties"] for v in agg.values()))
if "臺北市" not in all_counties or "新北市" not in all_counties:
    print("❌ dual-city requirement not met — missing one or both cities", file=sys.stderr)
    sys.exit(1)
```

### Write

Transactional `TRUNCATE … RESTART IDENTITY` + `execute_values` INSERT. Print:

- Total unique names
- Top 20 by occurrence
- Counties coverage
- File-skip summary

## `apply.sh` flow

```
1/3 migrations up    → psql 001_create_ingredient_names.up.sql
2/3 ETL              → python3 etl/load_ingredient_names.py
3/3 verify row count → SELECT COUNT(*) FROM school_meal_ingredient_names
```

`snapshot_apis.py` is **separate** (run manually when refreshing snapshots).

## `rollback.sh`

`psql -1 < migrations/001_create_ingredient_names.down.sql`

## `backup_db.sh`

Same docker-run-postgres pattern as labor-safety; dumps `dashboard` only (no
manager-DB changes here).

## Dual-city compliance

Project rule (CLAUDE.md): "必須是雙北組件 … 任一邊沒有即不符合規則".

Enforcement points:

1. Snapshot crawler: queries both 臺北市 + 新北市.
2. Dedupe loader: aborts if final aggregate `source_counties` lacks either city.
3. README documents this hard constraint.

## Testing strategy

No automated tests in scope (the labor-safety reference also has none — these are
operational ETL scripts, not application code). Verification = `apply.sh`'s
final `SELECT COUNT(*)` and the loader's printed summary.

Manual smoke test plan (for the user, after they take delivery):

1. `python3 etl/snapshot_apis.py --year-from 2024 --month-from 10 --year-to 2024 --month-to 10`
   → expect a handful of CSVs in `snapshots/`.
2. `./apply.sh` → migration applies + loader prints unique-count summary +
   verify reports row count.
3. `./rollback.sh` → table dropped.

## Out-of-scope / future work

- Airflow DAG wrapper for periodic refresh.
- Dashboard registration (would require `migrations/00X_register_*.up.sql` and FE component — explicitly not part of this scope).
- Vector embedding of ingredient names — handed off to the AI team.

## Open questions left for implementation phase

1. Exact 食材名稱 column header in `午餐食材及供應商資料集` and `午餐菜色及食材資料集`.
   Resolved during first probe; documented in implementation plan or skipped via
   warning fallback in the loader.
2. Whether `accesscode` rotates per-call or per-session — assume per-session
   until first 401 says otherwise.

## Acceptance criteria (delivered to user)

- [ ] All files under `scripts/school_meal_ingredients/` present and matching
      this spec.
- [ ] `apply.sh` runs without error against a fresh `dashboard` DB (verified by
      user, not by Claude).
- [ ] `school_meal_ingredient_names` populated with > 0 rows; both 臺北市 and
      新北市 represented in `source_counties`.
- [ ] `snapshot_apis.py` resumable (manifest survives interrupt + token rotation).
- [ ] No DB writes performed during code authoring — user invokes `apply.sh`.
