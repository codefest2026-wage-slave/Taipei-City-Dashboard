#!/usr/bin/env bash
# Apply food safety migrations and load all data.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
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

echo "2/3 ETL ..."
python3 "$ROOT/etl/load_inspection_tpe.py"
python3 "$ROOT/etl/load_restaurant_tpe.py"
python3 "$ROOT/etl/load_factory_ntpc.py"
python3 "$ROOT/etl/load_mohw_dual_city.py"
python3 "$ROOT/etl/load_mohw_poisoning.py"
python3 "$ROOT/etl/generate_geojson.py"

echo "3/3 verify row counts ..."
pg_psql DASHBOARD -c "
  SELECT 'food_inspection_tpe'      AS t, COUNT(*) FROM food_inspection_tpe
  UNION ALL SELECT 'food_testing_tpe',         COUNT(*) FROM food_testing_tpe
  UNION ALL SELECT 'food_restaurant_tpe',      COUNT(*) FROM food_restaurant_tpe
  UNION ALL SELECT 'food_factory_ntpc',        COUNT(*) FROM food_factory_ntpc
  UNION ALL SELECT 'food_inspection_by_city',  COUNT(*) FROM food_inspection_by_city
  UNION ALL SELECT 'food_type_violations',     COUNT(*) FROM food_type_violations
  UNION ALL SELECT 'food_poisoning_cause',     COUNT(*) FROM food_poisoning_cause;"

# Floor check: fail loudly if any food_* table has zero rows after ETL.
# Catches silent regressions (upstream column rename, snapshot truncation, etc.)
empty_tables="$(pg_psql DASHBOARD -At -c "
  SELECT t FROM (
    SELECT 'food_inspection_tpe'      AS t, COUNT(*) AS n FROM food_inspection_tpe
    UNION ALL SELECT 'food_testing_tpe',         COUNT(*) FROM food_testing_tpe
    UNION ALL SELECT 'food_restaurant_tpe',      COUNT(*) FROM food_restaurant_tpe
    UNION ALL SELECT 'food_factory_ntpc',        COUNT(*) FROM food_factory_ntpc
    UNION ALL SELECT 'food_inspection_by_city',  COUNT(*) FROM food_inspection_by_city
    UNION ALL SELECT 'food_type_violations',     COUNT(*) FROM food_type_violations
    UNION ALL SELECT 'food_poisoning_cause',     COUNT(*) FROM food_poisoning_cause
  ) c WHERE n = 0;" | tr -d '[:space:]')"
if [ -n "$empty_tables" ]; then
  echo "❌ FAIL: empty food_* table(s) detected after ETL: $empty_tables" >&2
  exit 1
fi

echo "✅ apply complete"
