# Labor Safety Radar — 工作安全燈號

Self-contained dashboard implementation. All data flows from CSV → ETL → DB.
Works against either local docker postgres OR a cloud DB; switch via
`.env.script` (no code changes needed).

## Quick start

```bash
# 0. One-time setup: copy and edit the env file (see "Targeting a DB" below)
cp scripts/labor_safety/.env.script.example scripts/labor_safety/.env.script
$EDITOR scripts/labor_safety/.env.script

# 1. Always backup first
./scripts/labor_safety/backup_db.sh

# 2. Apply (idempotent)
./scripts/labor_safety/apply.sh

# 3. To revert
./scripts/labor_safety/rollback.sh
```

## Targeting a DB (local docker vs. cloud)

Edit `scripts/labor_safety/.env.script` (gitignored). Set:

```
DB_DASHBOARD_HOST=…   DB_DASHBOARD_PORT=…
DB_DASHBOARD_USER=…   DB_DASHBOARD_PASSWORD=…
DB_DASHBOARD_DBNAME=dashboard   DB_DASHBOARD_SSLMODE=disable|require
DB_MANAGER_HOST=…     DB_MANAGER_PORT=…
DB_MANAGER_USER=…     DB_MANAGER_PASSWORD=…
DB_MANAGER_DBNAME=dashboardmanager   DB_MANAGER_SSLMODE=disable|require
```

For **local docker**: `HOST=localhost`, dashboard `PORT=5433`, manager `PORT=5432`,
`SSLMODE=disable`. (Defaults if `.env.script` is missing.)

For **cloud**: real hostname, real credentials, `SSLMODE=require`.

You can also override per-invocation: `DB_DASHBOARD_HOST=foo ./apply.sh`.

The shell scripts all execute `psql` / `pg_dump` via a one-shot
`docker run --rm --network=host postgres:16` container, so no host-side
postgres CLI install is needed. Python loaders connect via psycopg2.

## Layout

- `migrations/` — paired up/down SQL (4 files × up+down = 8), transactional via `psql -v ON_ERROR_STOP=1 -1`
- `etl/` — Python loaders, all read CSV (no live API except `snapshot_apis.py`)
- `snapshots/` — committed CSVs from data.taipei / data.ntpc APIs (regenerate via `etl/snapshot_apis.py` when refreshing)
- `backups/` — pg_dump output (gitignored)
- `_db_env.sh` — sourced by shell scripts to populate `DB_URL_*` and `pg_psql` / `pg_dump_to` helpers
- `etl/_db.py` — Python equivalent for psycopg2 connection kwargs
- `.env.script` — your local config (gitignored); copy from `.env.script.example`

## Data sources

| Table | Source CSV | Fetcher |
|---|---|---|
| labor_violations_tpe | docs/assets/違法名單總表-CSV檔1150105勞基.csv + 性平法 + snapshots/tpe_occupational_safety_violations.csv | etl/load_violations_tpe.py |
| labor_violations_ntpc | snapshots/ntpc_*.csv (3 files) | etl/load_violations_ntpc.py |
| labor_disasters_tpe / labor_disasters_ntpc | snapshots/*_major_disasters.csv | etl/load_disasters.py |
| labor_disputes_industry_tpe / labor_insurance_monthly_tpe | docs/assets/勞資爭議*.csv + 勞工保險*.csv | etl/load_stats_tpe.py |
| gcis_companies_{tpe,ntpc} + industry_codes | docs/assets/L-01-1/*.csv + industrial.xml | etl/load_gcis_companies.py |
| labor_recheck_priority_{tpe,ntpc} | (DB-derived via build SQL) | etl/build_recheck_priority.py → migrations/build_recheck_priority.sql |

## Refresh API snapshots

Run only when you want to update committed CSVs (do not run during normal apply):

```bash
python3 scripts/labor_safety/etl/snapshot_apis.py
git diff scripts/labor_safety/snapshots/   # review changes
git add scripts/labor_safety/snapshots/ && git commit
```

## Restore from backup

```bash
source scripts/labor_safety/_db_env.sh
cat scripts/labor_safety/backups/<TS>/dashboard.sql        | docker run --rm -i --network=host postgres:16 psql "$DB_URL_DASHBOARD"
cat scripts/labor_safety/backups/<TS>/dashboardmanager.sql | docker run --rm -i --network=host postgres:16 psql "$DB_URL_MANAGER"
```
