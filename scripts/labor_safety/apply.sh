#!/usr/bin/env bash
# Apply labor safety migrations and load all data.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "1/3 migrations up ..."
docker exec -i postgres-data    psql -U postgres -d dashboard        -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.up.sql"
# 002 seeded in Phase 3 — uncomment when ready:
# docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"

echo "2/3 ETL ..."
python3 "$ROOT/etl/load_violations_tpe.py"
python3 "$ROOT/etl/load_violations_ntpc.py"
python3 "$ROOT/etl/load_disasters.py"
python3 "$ROOT/etl/load_stats_tpe.py"
python3 "$ROOT/etl/generate_disaster_geojson.py"

echo "3/3 verify row counts ..."
docker exec -i postgres-data psql -U postgres -d dashboard -c "
  SELECT 'labor_violations_tpe'        AS t, COUNT(*) FROM labor_violations_tpe
  UNION ALL SELECT 'labor_violations_ntpc',         COUNT(*) FROM labor_violations_ntpc
  UNION ALL SELECT 'labor_disasters_tpe',           COUNT(*) FROM labor_disasters_tpe
  UNION ALL SELECT 'labor_disasters_ntpc',          COUNT(*) FROM labor_disasters_ntpc
  UNION ALL SELECT 'labor_disputes_industry_tpe',   COUNT(*) FROM labor_disputes_industry_tpe
  UNION ALL SELECT 'labor_insurance_monthly_tpe',   COUNT(*) FROM labor_insurance_monthly_tpe;"

echo "apply complete"
