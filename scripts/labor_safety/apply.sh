#!/usr/bin/env bash
# Apply labor safety migrations and load all data.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
#
# Connects via env vars resolved by _db_env.sh — works for local docker
# postgres or cloud DB depending on scripts/labor_safety/.env.script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard:        $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
echo

echo "1/3 migrations up ..."
pg_psql DASHBOARD -1 < "$ROOT/migrations/001_create_tables.up.sql"
pg_psql MANAGER   -1 < "$ROOT/migrations/002_seed_dashboard.up.sql"
pg_psql DASHBOARD -1 < "$ROOT/migrations/003_recheck_schema.up.sql"
pg_psql MANAGER   -1 < "$ROOT/migrations/004_register_recheck.up.sql"

echo "2/3 ETL ..."
python3 "$ROOT/etl/load_violations_tpe.py"
python3 "$ROOT/etl/load_violations_ntpc.py"
python3 "$ROOT/etl/load_disasters.py"
python3 "$ROOT/etl/load_stats_tpe.py"
python3 "$ROOT/etl/generate_disaster_geojson.py"
python3 "$ROOT/etl/load_gcis_companies.py"
python3 "$ROOT/etl/build_recheck_priority.py"
python3 "$ROOT/etl/generate_recheck_geojson.py"

echo "3/3 verify row counts ..."
pg_psql DASHBOARD -c "
  SELECT 'labor_violations_tpe'        AS t, COUNT(*) FROM labor_violations_tpe
  UNION ALL SELECT 'labor_violations_ntpc',         COUNT(*) FROM labor_violations_ntpc
  UNION ALL SELECT 'labor_disasters_tpe',           COUNT(*) FROM labor_disasters_tpe
  UNION ALL SELECT 'labor_disasters_ntpc',          COUNT(*) FROM labor_disasters_ntpc
  UNION ALL SELECT 'labor_disputes_industry_tpe',   COUNT(*) FROM labor_disputes_industry_tpe
  UNION ALL SELECT 'labor_insurance_monthly_tpe',   COUNT(*) FROM labor_insurance_monthly_tpe
  UNION ALL SELECT 'gcis_companies_tpe',            COUNT(*) FROM gcis_companies_tpe
  UNION ALL SELECT 'gcis_companies_ntpc',           COUNT(*) FROM gcis_companies_ntpc
  UNION ALL SELECT 'labor_recheck_priority_tpe',    COUNT(*) FROM labor_recheck_priority_tpe
  UNION ALL SELECT 'labor_recheck_priority_ntpc',   COUNT(*) FROM labor_recheck_priority_ntpc;"

echo "✅ apply complete"
