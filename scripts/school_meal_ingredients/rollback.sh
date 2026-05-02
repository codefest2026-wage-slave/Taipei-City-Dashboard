#!/usr/bin/env bash
# Rollback school meal ingredients: drop school_meal_ingredient_names.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/1 down: drop tables ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.down.sql"

echo "✅ rollback complete"
