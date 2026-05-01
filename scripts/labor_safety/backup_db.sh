#!/usr/bin/env bash
# Backup both dashboard databases before any apply/rollback.
# Output: scripts/labor_safety/backups/<UTC-timestamp>/{dashboard,dashboardmanager}.sql
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TS="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="$ROOT/backups/$TS"
mkdir -p "$OUT"

# Confirm containers are up
for c in postgres-data postgres-manager; do
  if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "container '$c' is not running. Start docker compose first." >&2
    exit 1
  fi
done

echo "Dumping dashboard ..."
docker exec postgres-data    pg_dump -U postgres -d dashboard        > "$OUT/dashboard.sql"
echo "Dumping dashboardmanager ..."
docker exec postgres-manager pg_dump -U postgres -d dashboardmanager > "$OUT/dashboardmanager.sql"

echo
echo "backup -> $OUT"
ls -lh "$OUT"
echo
echo "Restore example:"
echo "  docker exec -i postgres-data    psql -U postgres -d dashboard        < $OUT/dashboard.sql"
echo "  docker exec -i postgres-manager psql -U postgres -d dashboardmanager < $OUT/dashboardmanager.sql"
