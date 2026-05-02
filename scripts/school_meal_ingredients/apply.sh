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

echo "1/4 migrations up ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.up.sql"
pg_psql -1 < "$ROOT/migrations/002_create_raw_tables.up.sql"

echo "2/4 ETL: raw records ..."
python3 "$ROOT/etl/load_raw_records.py"

echo "3/4 ETL: ingredient names dedupe ..."
python3 "$ROOT/etl/load_ingredient_names.py"

echo "4/4 verify row counts ..."
pg_psql -c "
SELECT 'school_meal_ingredient_names'              AS t, COUNT(*) FROM school_meal_ingredient_names
UNION ALL SELECT 'school_meal_food_dictionary',              COUNT(*) FROM school_meal_food_dictionary
UNION ALL SELECT 'school_meal_caterers',                     COUNT(*) FROM school_meal_caterers
UNION ALL SELECT 'school_meal_seasoning_records_nation',     COUNT(*) FROM school_meal_seasoning_records_nation
UNION ALL SELECT 'school_meal_ingredient_records',           COUNT(*) FROM school_meal_ingredient_records
UNION ALL SELECT 'school_meal_dish_records',                 COUNT(*) FROM school_meal_dish_records
UNION ALL SELECT 'school_meal_dish_ingredient_records',      COUNT(*) FROM school_meal_dish_ingredient_records;"

echo "✅ apply complete"
