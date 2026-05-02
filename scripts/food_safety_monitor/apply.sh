#!/usr/bin/env bash
# Apply food-safety-monitor (dashboard 504) seed migration.
# Idempotent: safe to re-run. Rollback via rollback.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
echo

echo "1/2 migration up ..."
pg_psql MANAGER -1 < "$ROOT/migrations/001_seed_dashboard.up.sql"

echo "2/2 verify ..."
pg_psql MANAGER -c "
  SELECT id, index, name FROM dashboards WHERE id = 504;
  SELECT id, index, name FROM components WHERE id BETWEEN 1021 AND 1025 ORDER BY id;
"

echo "✅ apply complete — dashboard 504 食安監控系統 registered"
