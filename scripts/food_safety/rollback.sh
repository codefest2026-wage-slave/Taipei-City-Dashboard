#!/usr/bin/env bash
# Rollback food safety: remove dashboard 503, drop all food_* tables, clean GeoJSON.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard:        $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
echo

echo "1/3 down: dashboard registrations ..."
pg_psql MANAGER -1 < "$ROOT/migrations/002_seed_dashboard.down.sql"

echo "2/3 down: drop tables ..."
pg_psql DASHBOARD -1 < "$ROOT/migrations/001_create_tables.down.sql"

echo "3/3 clean GeoJSON ..."
rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson"
rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/food_factory_ntpc.geojson"

echo "✅ rollback complete"
