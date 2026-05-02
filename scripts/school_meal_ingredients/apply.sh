#!/usr/bin/env bash
# Apply school meal ingredients migrations and load deduped names.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
#
# Connects via env vars resolved by _db_env.sh — works for local docker
# postgres or cloud DB depending on scripts/school_meal_ingredients/.env.script.
#
# IMPORTANT: This does NOT call snapshot_apis.py. Run that manually to
# refresh the committed CSVs in snapshots/ before running apply.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/3 migrations up ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.up.sql"

echo "2/3 ETL ..."
python3 "$ROOT/etl/load_ingredient_names.py"

echo "3/3 verify row count ..."
pg_psql -c "SELECT 'school_meal_ingredient_names' AS t, COUNT(*) FROM school_meal_ingredient_names;"

echo "✅ apply complete"
