# 工作安全燈號 Labor Safety Radar — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract the existing 工作安全燈號 implementation (currently mixed into `feat/green-mobility-dashboard` branch) into a self-contained, reproducible, idempotent, rollback-safe deliverable on a new branch `feat/labor-safety-radar` based on commit `9bcf8c6728b5802b07e30737384131a838c5f7ff`.

**Architecture:** All labor-safety code lives under `scripts/labor_safety/`. SQL is split into paired `.up.sql` / `.down.sql` migrations. ETL reads only from CSV (no live API calls); 4 API datasets are pre-snapshotted into committed CSVs. Three thin shell wrappers (`backup_db.sh`, `apply.sh`, `rollback.sh`) sequence the workflow with `psql -v ON_ERROR_STOP=1 -1` for transactional safety. Dashboard is registered via SQL only (no BE code change). FE adds one new Vue component plus two surgical patches to shared files.

**Tech Stack:** Python 3 (ETL), PostgreSQL via Docker (`postgres-data` + `postgres-manager` containers), bash, Vue 3 + Vite (FE only — `SearchableViolationTable.vue` plus 2-line patches).

**Source files to port from main worktree (`/Users/junhong/Project/Taipei-City-Dashboard/`):**
- `scripts/labor_safety_create_tables.sql` → split into 001 up/down
- `scripts/register_labor_safety.sql` → split into 002 up/down
- `scripts/load_labor_violations_tpe.py` → adapt → `etl/load_violations_tpe.py`
- `scripts/load_labor_violations_ntpc.py` → adapt → `etl/load_violations_ntpc.py`
- `scripts/load_labor_disasters.py` → adapt → `etl/load_disasters.py`
- `scripts/load_labor_stats_tpe.py` → adapt → `etl/load_stats_tpe.py`
- `scripts/generate_labor_disaster_geojson.py` → adapt → `etl/generate_disaster_geojson.py`
- `Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue` → copy verbatim

**Working directory for ALL tasks:** `/Users/junhong/Project/Taipei-City-Dashboard/.worktrees/feat-labor-safety-radar/`

**Reference dataset registry & field mappings:** see `docs/plans/2026-05-01-labor-safety-radar-design.md` (already in this worktree as untracked file).

---

## Phase 0 — Preflight

### Task 0.1: Confirm worktree state

**Step 1:** `cd` into worktree and verify HEAD.

```bash
cd /Users/junhong/Project/Taipei-City-Dashboard/.worktrees/feat-labor-safety-radar
git rev-parse HEAD
git status --short
```

Expected:
- `HEAD` == `9bcf8c6728b5802b07e30737384131a838c5f7ff` (or shorter prefix)
- Untracked: `docs/plans/2026-05-01-labor-safety-radar-design.md` (the carried-over design doc)
- Otherwise clean

If anything else is untracked or modified, STOP and investigate.

### Task 0.2: Inspect docker / DB names

**Step 1:** Check running containers.

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep postgres
```

Expected output contains `postgres-data` and `postgres-manager`.

**Step 2:** Read DB credentials from `docker/.env` (in main repo, shared via worktree).

```bash
grep -E '^(DB_DASHBOARD|DB_MANAGER)_(DBNAME|USER)' /Users/junhong/Project/Taipei-City-Dashboard/docker/.env
```

Expected: 4 lines like `DB_DASHBOARD_DBNAME=dashboard`, `DB_DASHBOARD_USER=postgres`, `DB_MANAGER_DBNAME=dashboardmanager`, `DB_MANAGER_USER=postgres`. Record the actual values — they go into the shell scripts in Phase 1.

### Task 0.3: Pre-implementation backup (USER MUST DO BEFORE STARTING)

**Step 1:** Manual backup before any DB work.

```bash
mkdir -p /tmp/labor-safety-pre-impl-backup
docker exec postgres-data    pg_dump -U postgres -d dashboard        > /tmp/labor-safety-pre-impl-backup/dashboard.sql
docker exec postgres-manager pg_dump -U postgres -d dashboardmanager > /tmp/labor-safety-pre-impl-backup/dashboardmanager.sql
ls -lh /tmp/labor-safety-pre-impl-backup/
```

Expected: two non-empty `.sql` files. This is the safety net for "意外露資料". Do not delete until full verification (Phase 5) passes.

---

## Phase 1 — Scaffold Infrastructure (Commit 1)

### Task 1.1: Add `*.sh` exception to `.gitignore`

**Files:** Modify `.gitignore`

**Step 1:** Confirm current ignore rule.

```bash
grep -n '\*\.sh' .gitignore
```

Expected: line 29 `*.sh` exists.

**Step 2:** Append exception line. After the existing `!Taipei-City-Dashboard-DE/docker/prod/gitsync.sh` line, add:

```
!scripts/labor_safety/*.sh
```

**Step 3:** Verify.

```bash
git check-ignore -v scripts/labor_safety/apply.sh 2>&1 || echo "NOT IGNORED ✅"
```

Expected: prints `NOT IGNORED ✅` (the `git check-ignore` returns non-zero when the file is *not* ignored, which is what we want).

### Task 1.2: Create directory skeleton

**Step 1:** Make directories.

```bash
mkdir -p scripts/labor_safety/{migrations,etl,snapshots,backups}
touch scripts/labor_safety/backups/.gitkeep
```

**Step 2:** Add `backups/` to local labor_safety gitignore.

Create `scripts/labor_safety/.gitignore`:

```
backups/
!backups/.gitkeep
```

(Reason: shell scripts dump pg_dump there; never commit dumps.)

### Task 1.3: Create `migrations/001_create_tables.up.sql`

**Files:** Create `scripts/labor_safety/migrations/001_create_tables.up.sql`

Port from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/labor_safety_create_tables.sql` with these adaptations:
- Wrap entire script in `BEGIN; … COMMIT;`
- Replace each `DROP TABLE IF EXISTS xxx;` + `CREATE TABLE xxx (` with `CREATE TABLE IF NOT EXISTS xxx (` (idempotent: re-run on existing tables is no-op; first DROP belongs in `down.sql`)
- Keep the 6 tables: `labor_violations_tpe`, `labor_violations_ntpc`, `labor_disasters_tpe`, `labor_disasters_ntpc`, `labor_disputes_industry_tpe`, `labor_insurance_monthly_tpe`
- Header comment: file path + purpose + "down: migrations/001_create_tables.down.sql"

**Verify:** Read the original file as authoritative source for column definitions:

```bash
cat /Users/junhong/Project/Taipei-City-Dashboard/scripts/labor_safety_create_tables.sql
```

Copy column DDL for each table verbatim into the new file, only changing the wrapping per above.

### Task 1.4: Create `migrations/001_create_tables.down.sql`

**Files:** Create `scripts/labor_safety/migrations/001_create_tables.down.sql`

Content:

```sql
-- scripts/labor_safety/migrations/001_create_tables.down.sql
-- Rollback for 001: drop all 6 labor_safety tables.
-- up:   migrations/001_create_tables.up.sql
BEGIN;

DROP TABLE IF EXISTS labor_insurance_monthly_tpe   CASCADE;
DROP TABLE IF EXISTS labor_disputes_industry_tpe   CASCADE;
DROP TABLE IF EXISTS labor_disasters_ntpc          CASCADE;
DROP TABLE IF EXISTS labor_disasters_tpe           CASCADE;
DROP TABLE IF EXISTS labor_violations_ntpc         CASCADE;
DROP TABLE IF EXISTS labor_violations_tpe          CASCADE;

COMMIT;
```

**Verify:** All 6 tables are listed; order is reverse of up; all use `IF EXISTS` (idempotent).

### Task 1.5: Create `migrations/002_seed_dashboard.up.sql`

**Files:** Create `scripts/labor_safety/migrations/002_seed_dashboard.up.sql`

Port from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/register_labor_safety.sql` with these adaptations:
- Wrap in `BEGIN; … COMMIT;`
- Keep the existing top-level `DELETE FROM query_charts WHERE index LIKE 'labor_%';` etc. as a defensive cleanup (still safe — only labor_% indexes touched)
- Confirm it inserts: 6 components (1005-1010), 6 component_charts rows, 2 component_maps rows (`labor_disasters_tpe`, `labor_disasters_ntpc`), 12 query_charts rows (6 components × 2 cities), 1 dashboard row (502), and dashboard_groups entries
- Validate the 12 query_charts rows are present — read `register_labor_safety.sql` lines 36-200 to confirm dual-city coverage for all 6 components

**Verify after writing:**
```bash
grep -c "INSERT INTO query_charts" scripts/labor_safety/migrations/002_seed_dashboard.up.sql
```
Expected: `12`.

### Task 1.6: Create `migrations/002_seed_dashboard.down.sql`

**Files:** Create `scripts/labor_safety/migrations/002_seed_dashboard.down.sql`

```sql
-- scripts/labor_safety/migrations/002_seed_dashboard.down.sql
-- Rollback for 002: remove dashboard 502 and all labor_% registrations.
BEGIN;

DELETE FROM dashboard_groups WHERE dashboard_id = 502;
DELETE FROM dashboards       WHERE id           = 502;
DELETE FROM query_charts     WHERE index LIKE 'labor_%';
DELETE FROM component_maps   WHERE index LIKE 'labor_disaster%';
DELETE FROM component_charts WHERE index LIKE 'labor_%';
DELETE FROM components       WHERE id BETWEEN 1005 AND 1010;

COMMIT;
```

**Note on order:** delete from junction (`dashboard_groups`) → parent (`dashboards`) → leaf registration tables → `components` last (FK target).

### Task 1.7: Create `backup_db.sh`

**Files:** Create `scripts/labor_safety/backup_db.sh`

```bash
#!/usr/bin/env bash
# Backup both dashboard databases before any apply/rollback.
# Output: scripts/labor_safety/backups/<UTC-timestamp>/{dashboard,dashboardmanager}.sql
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="$ROOT/backups/$TS"
mkdir -p "$OUT"

# Confirm containers are up
for c in postgres-data postgres-manager; do
  if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "❌ container '$c' is not running. Start docker compose first." >&2
    exit 1
  fi
done

echo "▶ Dumping dashboard …"
docker exec postgres-data    pg_dump -U postgres -d dashboard        > "$OUT/dashboard.sql"
echo "▶ Dumping dashboardmanager …"
docker exec postgres-manager pg_dump -U postgres -d dashboardmanager > "$OUT/dashboardmanager.sql"

echo
echo "✅ backup → $OUT"
ls -lh "$OUT"
echo
echo "Restore example:"
echo "  docker exec -i postgres-data    psql -U postgres -d dashboard        < $OUT/dashboard.sql"
echo "  docker exec -i postgres-manager psql -U postgres -d dashboardmanager < $OUT/dashboardmanager.sql"
```

**Step 2:** Make executable.

```bash
chmod +x scripts/labor_safety/backup_db.sh
```

**Step 3:** Smoke test.

```bash
./scripts/labor_safety/backup_db.sh
```

Expected: prints `✅ backup → …`, `ls -lh` shows two non-empty files. Verify by `head -5 scripts/labor_safety/backups/*/dashboard.sql` shows a real `pg_dump` header.

### Task 1.8: Create `apply.sh` (skeleton — fully wired in Phase 2 & 3)

**Files:** Create `scripts/labor_safety/apply.sh`

```bash
#!/usr/bin/env bash
# Apply labor safety migrations and load all data.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "▶ 1/3 migrations up …"
docker exec -i postgres-data    psql -U postgres -d dashboard        -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.up.sql"
# 002 seeded in Phase 3 — uncomment when ready:
# docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"

echo "▶ 2/3 ETL …"
# Loaders added in Phase 2 — placeholders:
# python3 "$ROOT/etl/load_violations_tpe.py"
# python3 "$ROOT/etl/load_violations_ntpc.py"
# python3 "$ROOT/etl/load_disasters.py"
# python3 "$ROOT/etl/load_stats_tpe.py"
# python3 "$ROOT/etl/generate_disaster_geojson.py"

echo "▶ 3/3 verify row counts …"
docker exec -i postgres-data psql -U postgres -d dashboard -c "
  SELECT 'labor_violations_tpe'        AS t, COUNT(*) FROM labor_violations_tpe
  UNION ALL SELECT 'labor_violations_ntpc',         COUNT(*) FROM labor_violations_ntpc
  UNION ALL SELECT 'labor_disasters_tpe',           COUNT(*) FROM labor_disasters_tpe
  UNION ALL SELECT 'labor_disasters_ntpc',          COUNT(*) FROM labor_disasters_ntpc
  UNION ALL SELECT 'labor_disputes_industry_tpe',   COUNT(*) FROM labor_disputes_industry_tpe
  UNION ALL SELECT 'labor_insurance_monthly_tpe',   COUNT(*) FROM labor_insurance_monthly_tpe;"

echo "✅ apply complete"
```

```bash
chmod +x scripts/labor_safety/apply.sh
```

**Smoke test:**
```bash
./scripts/labor_safety/apply.sh
```

Expected: 6 tables created (`COUNT(*)` = 0 for each), no errors.

**Manual rollback for the smoke test (we don't have rollback.sh fully yet, so run by hand):**

```bash
docker exec -i postgres-data psql -U postgres -d dashboard -v ON_ERROR_STOP=1 -1 < scripts/labor_safety/migrations/001_create_tables.down.sql
```

Expected: succeeds (drops the 6 tables).

### Task 1.9: Create `rollback.sh`

**Files:** Create `scripts/labor_safety/rollback.sh`

```bash
#!/usr/bin/env bash
# Rollback labor safety: remove dashboard 502, drop all 6 tables, clean GeoJSON.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"

echo "▶ 1/3 down: dashboard registrations …"
docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.down.sql"

echo "▶ 2/3 down: drop tables …"
docker exec -i postgres-data psql -U postgres -d dashboard -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.down.sql"

echo "▶ 3/3 clean GeoJSON …"
rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson"
rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson"

echo "✅ rollback complete"
```

```bash
chmod +x scripts/labor_safety/rollback.sh
```

**Smoke test:**
```bash
./scripts/labor_safety/rollback.sh
```

Expected: succeeds (002.down on empty manager DB → no-op; 001.down on already-dropped tables → no-op via `IF EXISTS`).

### Task 1.10: Create `scripts/labor_safety/README.md`

**Files:** Create `scripts/labor_safety/README.md`

Content (concise, ~60 lines):

```markdown
# Labor Safety Radar — 工作安全燈號

Self-contained dashboard implementation. All data flows from CSV → ETL → DB.

## Quick start

```bash
# 1. Always backup first
./scripts/labor_safety/backup_db.sh

# 2. Apply (idempotent)
./scripts/labor_safety/apply.sh

# 3. To revert
./scripts/labor_safety/rollback.sh
```

## Layout

- `migrations/` — paired up/down SQL, transactional via `psql -v ON_ERROR_STOP=1 -1`
- `etl/` — Python loaders, all read CSV (no live API)
- `snapshots/` — committed CSVs from data.taipei / data.ntpc APIs (regenerate via `etl/snapshot_apis.py` when refreshing)
- `backups/` — pg_dump output (gitignored)

## Data sources

| Table | Source CSV | Fetcher |
|---|---|---|
| labor_violations_tpe | docs/assets/違法名單總表-CSV檔1150105勞基.csv + 性平法 + snapshots/tpe_occupational_safety_violations.csv | etl/load_violations_tpe.py |
| labor_violations_ntpc | snapshots/ntpc_*.csv (3 files) | etl/load_violations_ntpc.py |
| labor_disasters_tpe / labor_disasters_ntpc | snapshots/*_major_disasters.csv | etl/load_disasters.py |
| labor_disputes_industry_tpe / labor_insurance_monthly_tpe | docs/assets/勞資爭議*.csv + 勞工保險*.csv | etl/load_stats_tpe.py |

## Refresh API snapshots

Run only when you want to update committed CSVs (do not run during normal apply):

```bash
python3 scripts/labor_safety/etl/snapshot_apis.py
git diff scripts/labor_safety/snapshots/   # review changes
git add scripts/labor_safety/snapshots/ && git commit
```

## Restore from backup

```bash
docker exec -i postgres-data    psql -U postgres -d dashboard        < scripts/labor_safety/backups/<TS>/dashboard.sql
docker exec -i postgres-manager psql -U postgres -d dashboardmanager < scripts/labor_safety/backups/<TS>/dashboardmanager.sql
```
```

### Task 1.11: Commit 1

```bash
git add .gitignore scripts/labor_safety/
git status   # confirm only new/modified files relevant to scaffold
git commit -m "$(cat <<'EOF'
feat(labor-safety): scaffold migrations + apply/rollback/backup scripts

Establish the layout under scripts/labor_safety/ with paired up/down
SQL migrations (001 DDL only at this point — 002 seeded in commit 3),
shell wrappers for backup/apply/rollback using psql -v ON_ERROR_STOP=1
-1 for transactional safety, and a README. Loaders and dashboard
registration are added in subsequent commits; this commit produces a
runnable apply.sh that creates the 6 empty tables and a runnable
rollback.sh that drops them.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

**Verify:** `git log --oneline -2` shows exactly one new commit on top of `9bcf8c67`.

---

## Phase 2 — ETL & API Snapshots (Commit 2)

### Task 2.1: Create `etl/snapshot_apis.py`

**Files:** Create `scripts/labor_safety/etl/snapshot_apis.py`

Adapt the API-fetch portions of these existing files for one-shot snapshot generation:
- `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_violations_tpe.py` (TPE 職安法 RID `90d05db5-d46f-4900-a450-b284b0f20fb9`)
- `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_violations_ntpc.py` (NTPC 3 datasets: `a3408b16…`, `d7b245c0…`, `8ec84245…`)
- `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_disasters.py` (TPE RID `ab4ddbe2-90f5-49a6-a7ad-45e5b6d14871`, NTPC UUID `80743c0e-b7e7-4d4a-825b-df354a542f65`)

Structure:

```python
#!/usr/bin/env python3
"""
One-shot snapshot tool: fetch 6 API endpoints and write CSV files
into snapshots/. Re-run this only when you want to refresh data;
the regular apply.sh does NOT call this — it only reads the
committed CSV outputs.

Usage:
    python3 scripts/labor_safety/etl/snapshot_apis.py [--only NAME]
"""
import csv
import sys
from pathlib import Path
import requests  # already a project dep

OUT_DIR = Path(__file__).resolve().parent.parent / "snapshots"

# Each entry: (output filename, endpoint URL pattern, paginator-fn-name)
SOURCES = [
    {
        "filename": "tpe_occupational_safety_violations.csv",
        "fetch":    fetch_data_taipei_rid,
        "rid":      "90d05db5-d46f-4900-a450-b284b0f20fb9",
        "expect":   (1000, 20000),  # row range, hard fail outside
    },
    # ... five more entries — copy from source files referenced above
]

def fetch_data_taipei_rid(rid):
    """Yield dicts from data.taipei v1 API with pagination."""
    # Copy the paginator from load_labor_violations_tpe.py
    ...

def fetch_data_ntpc(uuid):
    """Yield dicts from data.ntpc API with pagination."""
    # Copy the paginator from load_labor_violations_ntpc.py
    ...

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for src in SOURCES:
        rows = list(src["fetch"](...))
        out = OUT_DIR / src["filename"]
        if not rows:
            print(f"❌ {src['filename']}: 0 rows from API — abort"); sys.exit(1)
        lo, hi = src["expect"]
        if not (lo <= len(rows) <= hi):
            print(f"⚠️  {src['filename']}: {len(rows)} rows out of expected [{lo},{hi}] — review before commit")
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"✅ {src['filename']}: {len(rows):,} rows")

if __name__ == "__main__":
    main()
```

**Step 2:** Read the existing source files to copy paginator logic verbatim:

```bash
sed -n '1,80p' /Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_violations_tpe.py
sed -n '1,80p' /Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_violations_ntpc.py
sed -n '1,80p' /Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_disasters.py
```

Use these as authoritative source for fetch logic.

### Task 2.2: Run snapshot generation

**Step 1:** Execute.

```bash
cd /Users/junhong/Project/Taipei-City-Dashboard/.worktrees/feat-labor-safety-radar
python3 scripts/labor_safety/etl/snapshot_apis.py
```

Expected: 6 lines of `✅ filename: N,NNN rows`. Total run time < 2 minutes.

**Step 2:** Validate row counts.

```bash
wc -l scripts/labor_safety/snapshots/*.csv
```

Expected (±5%):
- `ntpc_labor_violations.csv`: ~14,156 (+1 header)
- `ntpc_occupational_safety_violations.csv`: ~4,149
- `ntpc_gender_equality_violations.csv`: ~48
- `ntpc_major_disasters.csv`: ~207
- `tpe_occupational_safety_violations.csv`: thousands
- `tpe_major_disasters.csv`: hundreds

**Step 3:** Spot-check one file.

```bash
head -3 scripts/labor_safety/snapshots/ntpc_labor_violations.csv
```

Expected: header line + 2 data rows with comma-separated values.

### Task 2.3: Create `etl/load_violations_tpe.py`

**Files:** Create `scripts/labor_safety/etl/load_violations_tpe.py`

Adapt from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_violations_tpe.py` with these changes:
- Strip ALL HTTP fetch code (no `requests`, no API URLs)
- Replace TPE 職安法 fetch with reading `scripts/labor_safety/snapshots/tpe_occupational_safety_violations.csv`
- Keep CSV reads for 勞基法 (`docs/assets/違法名單總表-CSV檔1150105勞基.csv`, UTF-8 BOM) and 性平法 (`docs/assets/臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv`, Big5)
- Use `psycopg2.connect()` reading from `docker/.env` env vars
- Write pattern (apply Loader 5 條鐵則 from design doc):

```python
def main():
    rows = []
    rows += load_labor_basic_csv(...)
    rows += load_gender_equality_csv(...)
    rows += load_occupational_safety_snapshot(...)

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE labor_violations_tpe RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, rows, page_size=500)
        cur.execute("COMMIT")
    print(f"✅ {len(rows):,} rows → labor_violations_tpe")
```

`db_kwargs()` reads from `docker/.env` via `python-dotenv` or simple file parser; connect to `localhost:5432` (the `postgres-data` container port) — confirm port mapping with `docker port postgres-data`.

**Verify:**
```bash
python3 scripts/labor_safety/etl/load_violations_tpe.py
docker exec postgres-data psql -U postgres -d dashboard -c "SELECT COUNT(*) FROM labor_violations_tpe"
```
Expected: count > 15,000 (sum of 勞基 ~15k + 性平 ~231 + 職安 ~few thousand).

### Task 2.4: Create `etl/load_violations_ntpc.py`

**Files:** Create `scripts/labor_safety/etl/load_violations_ntpc.py`

Same pattern as 2.3 but reads 3 NTPC snapshot CSVs (`ntpc_labor_violations.csv`, `ntpc_gender_equality_violations.csv`, `ntpc_occupational_safety_violations.csv`) and writes to `labor_violations_ntpc`. Adapt from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_violations_ntpc.py` (strip all `requests` calls, read CSV instead).

**Verify:**
```bash
python3 scripts/labor_safety/etl/load_violations_ntpc.py
docker exec postgres-data psql -U postgres -d dashboard -c "SELECT COUNT(*), law_category FROM labor_violations_ntpc GROUP BY law_category ORDER BY 1 DESC"
```
Expected: 3 rows by law_category, total > 18,000.

### Task 2.5: Create `etl/load_disasters.py`

**Files:** Create `scripts/labor_safety/etl/load_disasters.py`

Reads `snapshots/tpe_major_disasters.csv` and `snapshots/ntpc_major_disasters.csv`; writes to `labor_disasters_tpe` and `labor_disasters_ntpc` (separate tables — TPE has lng/lat, NTPC has district). Adapt from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_disasters.py`.

**Verify:**
```bash
python3 scripts/labor_safety/etl/load_disasters.py
docker exec postgres-data psql -U postgres -d dashboard -c "
  SELECT 'tpe' AS c, COUNT(*) FROM labor_disasters_tpe
  UNION ALL SELECT 'ntpc', COUNT(*) FROM labor_disasters_ntpc"
```
Expected: TPE ~hundreds, NTPC ~206.

### Task 2.6: Create `etl/load_stats_tpe.py`

**Files:** Create `scripts/labor_safety/etl/load_stats_tpe.py`

Reads `docs/assets/勞資爭議統計依行業別區分(11503).csv` (Big5) and `docs/assets/臺北市勞工保險及就業服務按月別.csv`. Writes to `labor_disputes_industry_tpe` and `labor_insurance_monthly_tpe`. Adapt from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/load_labor_stats_tpe.py`.

**Verify:**
```bash
python3 scripts/labor_safety/etl/load_stats_tpe.py
docker exec postgres-data psql -U postgres -d dashboard -c "
  SELECT 'disputes' AS t, COUNT(*) FROM labor_disputes_industry_tpe
  UNION ALL SELECT 'insurance', COUNT(*) FROM labor_insurance_monthly_tpe"
```
Expected: disputes ~133, insurance ~338.

### Task 2.7: Create `etl/generate_disaster_geojson.py`

**Files:** Create `scripts/labor_safety/etl/generate_disaster_geojson.py`

Reads from `labor_disasters_tpe` and `labor_disasters_ntpc` tables; writes:
- `Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson` (point GeoJSON with `severity` property: "fatal" if deaths > 0 else "injured")
- `Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson` (district-level aggregated points with `incidents` property — needs district centroid lookup table; copy from `/Users/junhong/Project/Taipei-City-Dashboard/scripts/generate_labor_disaster_geojson.py`)

**Verify:**
```bash
python3 scripts/labor_safety/etl/generate_disaster_geojson.py
ls -lh Taipei-City-Dashboard-FE/public/mapData/labor_disasters_*.geojson
python3 -c "import json; d=json.load(open('Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson')); print(len(d['features']), 'features')"
```
Expected: both files exist, non-empty, valid JSON.

### Task 2.8: Wire loaders into `apply.sh`

**Files:** Modify `scripts/labor_safety/apply.sh`

Uncomment the 5 ETL lines in section 2/3. Leave 002 migration commented (still Phase 3).

**Verify (clean run):**
```bash
./scripts/labor_safety/rollback.sh    # clean state
./scripts/labor_safety/apply.sh
```

Expected: no errors, final row counts:
- labor_violations_tpe > 15,000
- labor_violations_ntpc > 18,000
- labor_disasters_tpe > 100
- labor_disasters_ntpc ~ 206
- labor_disputes_industry_tpe ~ 133
- labor_insurance_monthly_tpe ~ 338

### Task 2.9: Commit 2

```bash
git add scripts/labor_safety/etl/ scripts/labor_safety/snapshots/ scripts/labor_safety/apply.sh
git status  # confirm
git commit -m "$(cat <<'EOF'
feat(labor-safety): add ETL loaders + API snapshots

Six API endpoints from data.taipei / data.ntpc are pre-fetched into
committed CSVs under snapshots/ (regenerated via etl/snapshot_apis.py
on demand, NOT during apply). Five loaders read only from those
snapshots plus four pre-existing CSVs in docs/assets/, transform
fields per design doc, and write each table inside a single
TRUNCATE-then-INSERT transaction. apply.sh now runs all five loaders
plus the GeoJSON generator after migration 001.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 — Dashboard Registration (Commit 3)

### Task 3.1: Verify 002 up/down already in place

These were created in Tasks 1.5 and 1.6. Re-read them:

```bash
cat scripts/labor_safety/migrations/002_seed_dashboard.up.sql | head -20
grep -c "INSERT INTO query_charts" scripts/labor_safety/migrations/002_seed_dashboard.up.sql
```

Expected: 12 query_charts inserts.

### Task 3.2: Wire 002 into `apply.sh`

**Files:** Modify `scripts/labor_safety/apply.sh`

Uncomment the line:
```bash
docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"
```

Position: in section 1/3, immediately after the 001 line.

### Task 3.3: End-to-end smoke test

```bash
./scripts/labor_safety/rollback.sh
./scripts/labor_safety/apply.sh
```

Expected: no errors. Verify dashboard registration:

```bash
docker exec postgres-manager psql -U postgres -d dashboardmanager -c "SELECT id, name, components FROM dashboards WHERE id = 502"
docker exec postgres-manager psql -U postgres -d dashboardmanager -c "SELECT COUNT(*) FROM query_charts WHERE index LIKE 'labor_%'"
docker exec postgres-manager psql -U postgres -d dashboardmanager -c "SELECT index, city FROM query_charts WHERE index LIKE 'labor_%' ORDER BY index, city"
```

Expected:
- 1 dashboard row, components array `{1005,1006,1007,1008,1009,1010}`
- query_charts count = 12
- 6 distinct indexes × 2 cities (taipei, metrotaipei)

### Task 3.4: Commit 3

```bash
git add scripts/labor_safety/apply.sh
# 002 SQL files were committed in commit 1, so this commit only modifies apply.sh
git status   # confirm only apply.sh modified
git commit -m "$(cat <<'EOF'
feat(labor-safety): register dashboard 502 with 6 components (dual-city)

Activate migration 002 in apply.sh to register the 工作安全燈號
dashboard with 6 components (1005-1010), 12 query_charts (each component
has both taipei and metrotaipei rows per CLAUDE.md dual-city rule), and
2 component_maps for the disaster GeoJSON layers. The 002 SQL files
themselves shipped with the scaffold in commit 1; this commit wires them
into the apply pipeline.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4 — Frontend (Commit 4)

### Task 4.1: Add `SearchableViolationTable.vue`

**Files:** Create `Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue`

Copy verbatim from main worktree:

```bash
cp /Users/junhong/Project/Taipei-City-Dashboard/Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue \
   Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue
```

**Verify:**
```bash
wc -l Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue
head -5 Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue
```

### Task 4.2: Patch `DashboardComponent.vue`

**Files:** Modify `Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue`

**Step 1:** Read both files to compare imports and switch cases.

```bash
diff <(grep -E "^import|case " Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue) \
     <(grep -E "^import|case " /Users/junhong/Project/Taipei-City-Dashboard/Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue) | head -30
```

The main-worktree version has the `SearchableViolationTable` import and a `case "SearchableViolationTable":` branch returning either `MapLegendSvg` (for the small icon) or `SearchableViolationTable` (for the full component). Apply ONLY those two additions to the worktree's file using Edit tool. Do NOT copy the whole file (other imports may differ).

Concrete edits (use Edit tool, find unique context lines):

1. Add import alphabetically with siblings:
   ```
   import SearchableViolationTable from "./components/SearchableViolationTable.vue";
   ```

2. Add case branch in the chart-type switch (immediately before `default:` or after `case "MapLegend":`):
   ```js
   case "SearchableViolationTable":
       return svg ? MapLegendSvg : SearchableViolationTable;
   ```

**Verify:**
```bash
grep -n "SearchableViolationTable" Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue
```
Expected: 3 lines (1 import + 2 in the case body).

### Task 4.3: Patch `chartTypes.ts`

**Files:** Modify `Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts`

Add one line to the chart-type-to-label map:

```ts
SearchableViolationTable: "雙北違規快查表",
```

**Verify:**
```bash
grep "SearchableViolationTable" Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts
```
Expected: 1 line.

### Task 4.4: Run FE build to confirm no compile errors

**Step 1:** Install (only first time on this worktree).

```bash
cd Taipei-City-Dashboard-FE && npm install
```

Expected: success, takes 1-3 minutes.

**Step 2:** Lint + build.

```bash
npm run build
```

Expected: completes without error. Watch for any TS error involving `SearchableViolationTable`.

**Step 3:** Manual smoke (optional but recommended).

Start local dev server in main worktree (already running per docker compose). Browse `http://localhost:8080`, login (Shift+TUIC logo), find dashboard 502 「工作安全燈號」, verify all 6 cards render data.

### Task 4.5: Commit 4

```bash
cd /Users/junhong/Project/Taipei-City-Dashboard/.worktrees/feat-labor-safety-radar
git add Taipei-City-Dashboard-FE/src/dashboardComponent/components/SearchableViolationTable.vue \
        Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue \
        Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.ts
# Confirm only these 3 files staged:
git status
git commit -m "$(cat <<'EOF'
feat(labor-safety): add SearchableViolationTable + FE wiring

New custom Vue component renders the dual-city violation lookup table
backed by the labor_violation_search query_chart. Two surgical patches
register the component in DashboardComponent.vue (import + switch case)
and chartTypes.ts (display label).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5 — End-to-End Verification

### Task 5.1: Full DB-wipe rehearsal

This is the demo dress rehearsal. Treat output as the source of truth, not the plan.

**Step 1:** Pre-rehearsal backup (separate from Task 0.3 — captures state right before the wipe).

```bash
./scripts/labor_safety/backup_db.sh
```

Note the timestamp from the output.

**Step 2:** Wipe DB volumes.

```bash
docker compose -f /Users/junhong/Project/Taipei-City-Dashboard/docker/docker-compose-db.yaml down -v
docker compose -f /Users/junhong/Project/Taipei-City-Dashboard/docker/docker-compose-db.yaml up -d
sleep 15  # wait for healthcheck
```

**Step 3:** Re-run base init.

```bash
docker compose -f /Users/junhong/Project/Taipei-City-Dashboard/docker/docker-compose-init.yaml up -d
# wait for completion — check logs:
docker logs init-fe --tail 20
docker logs init-be --tail 20
```

**Step 4:** Apply labor safety from scratch.

```bash
./scripts/labor_safety/apply.sh
```

Expected: success, all 6 row counts > 0.

### Task 5.2: Verification checklist (8 items from design doc)

Run each:

```bash
# 1. 6 tables non-empty
docker exec postgres-data psql -U postgres -d dashboard -c "SELECT 'v_tpe', COUNT(*) FROM labor_violations_tpe UNION ALL SELECT 'v_ntpc', COUNT(*) FROM labor_violations_ntpc UNION ALL SELECT 'd_tpe', COUNT(*) FROM labor_disasters_tpe UNION ALL SELECT 'd_ntpc', COUNT(*) FROM labor_disasters_ntpc UNION ALL SELECT 'disputes', COUNT(*) FROM labor_disputes_industry_tpe UNION ALL SELECT 'insurance', COUNT(*) FROM labor_insurance_monthly_tpe"

# 2. dashboard 502 registered
docker exec postgres-manager psql -U postgres -d dashboardmanager -c "SELECT * FROM dashboards WHERE id=502"

# 3. 12 query_charts
docker exec postgres-manager psql -U postgres -d dashboardmanager -c "SELECT COUNT(*) FROM query_charts WHERE index LIKE 'labor_%'"

# 4. GeoJSON
ls -lh Taipei-City-Dashboard-FE/public/mapData/labor_disasters_*.geojson

# 5. FE build
(cd Taipei-City-Dashboard-FE && npm run build) 2>&1 | tail -10

# 6. Browser visual — manual: open http://localhost:8080 → 工作安全燈號 → 6 cards have data

# 7. Rollback clean
./scripts/labor_safety/rollback.sh
docker exec postgres-manager psql -U postgres -d dashboardmanager -c "SELECT COUNT(*) FROM dashboards WHERE id=502"
docker exec postgres-data psql -U postgres -d dashboard -c "\dt labor_*"

# 8. Idempotency: re-apply
./scripts/labor_safety/apply.sh
# row counts should match step 1 exactly
```

If any step fails: STOP. Diagnose and fix. Do not push.

### Task 5.3: Final smoke + push

```bash
git log --oneline 9bcf8c67..HEAD   # should show 4 commits
git status                          # should be clean (or only untracked design doc)
git push -u origin feat/labor-safety-radar
```

Expected: push succeeds.

---

## Risks & Watch-outs

- **Big5 decoding:** 性平法 + 勞資爭議 CSVs are Big5; loaders must use `encoding="big5"` with `errors="replace"` to avoid UnicodeDecodeError.
- **Date format zoo:** TPE 民國 YYYMMDD vs `113年12月31日` vs ISO vs `108/02/01`. Use the helper functions from design doc §… (already in source files).
- **`*.sh` ignore:** Task 1.1 adds the exception. If you skip it, all three shell scripts will be silently untracked.
- **Cache TTL:** geocode cache (`scripts/.geocode_cache.json`) is shared across worktrees through the underlying `.git`-shared filesystem — but the labor disaster TPE data already has lng/lat from API, so no geocoding needed.
- **NTPC API quota:** snapshot_apis.py runs 6 fetches; if data.ntpc rate-limits, add a 1-second sleep between sources.
- **psql ON_ERROR_STOP=1 with -1:** when a SQL file already wraps its own `BEGIN/COMMIT`, the `-1` flag is a redundant outer transaction. This is intentional double-protection — neither breaks the other.

---

## Definition of Done

- [ ] 4 commits on `feat/labor-safety-radar`, branch pushed to remote
- [ ] All 8 verification items pass
- [ ] DB wipe → init → apply rehearsal completed end-to-end
- [ ] Dashboard 502 visible in browser with 6 cards each rendering real data
- [ ] `rollback.sh` leaves DB indistinguishable from pre-apply state (modulo `pg_dump` fingerprints)
