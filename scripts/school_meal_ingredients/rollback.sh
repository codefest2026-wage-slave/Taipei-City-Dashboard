#!/usr/bin/env bash
# Rollback school meal ingredients: drop school_meal_* tables.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/2 down: drop raw tables ..."
pg_psql -1 < "$ROOT/migrations/002_create_raw_tables.down.sql"

echo "2/2 down: drop dedupe table ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.down.sql"

echo "✅ rollback complete"
