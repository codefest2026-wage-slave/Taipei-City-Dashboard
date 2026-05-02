#!/usr/bin/env bash
# Backup the dashboard database before any apply/rollback.
# Output: scripts/school_meal_ingredients/backups/<UTC-timestamp>/dashboard.sql
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="$ROOT/backups/$TS"
mkdir -p "$OUT"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "▶ Dumping dashboard …"
pg_dump_to "$OUT/dashboard.sql.partial"
mv "$OUT/dashboard.sql.partial" "$OUT/dashboard.sql"

echo
echo "✅ backup → $OUT"
ls -lh "$OUT"
echo
echo "Restore example:"
echo "  cat $OUT/dashboard.sql | docker run --rm -i --network=host $PG_CLIENT_IMAGE psql \"\$DB_URL_DASHBOARD\""
