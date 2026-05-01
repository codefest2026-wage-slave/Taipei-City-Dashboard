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
