#!/usr/bin/env bash
# Backup both dashboard databases before any apply/rollback.
# Output: scripts/labor_safety/backups/<UTC-timestamp>/{dashboard,dashboardmanager}.sql
#
# Connects via env vars resolved by _db_env.sh — works for local docker
# postgres or cloud DB depending on scripts/labor_safety/.env.script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="$ROOT/backups/$TS"
mkdir -p "$OUT"

echo "▶ target dashboard:        $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo "▶ target dashboardmanager: $DB_MANAGER_HOST:$DB_MANAGER_PORT/$DB_MANAGER_DBNAME (sslmode=$DB_MANAGER_SSLMODE)"
echo

echo "▶ Dumping dashboard …"
pg_dump_to "$OUT/dashboard.sql" DASHBOARD
echo "▶ Dumping dashboardmanager …"
pg_dump_to "$OUT/dashboardmanager.sql" MANAGER

echo
echo "✅ backup → $OUT"
ls -lh "$OUT"
echo
echo "Restore example:"
echo "  cat $OUT/dashboard.sql        | docker run --rm -i --network=host $PG_CLIENT_IMAGE psql \"\$DB_URL_DASHBOARD\""
echo "  cat $OUT/dashboardmanager.sql | docker run --rm -i --network=host $PG_CLIENT_IMAGE psql \"\$DB_URL_MANAGER\""
