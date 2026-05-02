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

Works for both local docker and cloud DB targets — the `pg_psql` helper
resolves the right `DB_URL_*` from `.env.script` / defaults:

```bash
source scripts/food_safety/_db_env.sh
cat scripts/food_safety/backups/<TS>/dashboard.sql        | docker run --rm -i --network=host "$PG_CLIENT_IMAGE" psql "$DB_URL_DASHBOARD"
cat scripts/food_safety/backups/<TS>/dashboardmanager.sql | docker run --rm -i --network=host "$PG_CLIENT_IMAGE" psql "$DB_URL_MANAGER"
```

## Cloud DB target

Copy `.env.script.example` → `.env.script` and override `DB_DASHBOARD_*` / `DB_MANAGER_*`. The same `apply.sh` works.
