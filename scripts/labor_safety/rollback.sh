#!/usr/bin/env bash
# Rollback labor safety: remove dashboard 502, drop all 6 tables, clean GeoJSON.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"

echo "1/3 down: dashboard registrations ..."
docker exec -i postgres-manager psql -U postgres -d dashboardmanager -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/002_seed_dashboard.down.sql"

echo "2/3 down: drop tables ..."
docker exec -i postgres-data psql -U postgres -d dashboard -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/003_recheck_schema.down.sql"
docker exec -i postgres-data psql -U postgres -d dashboard -v ON_ERROR_STOP=1 -1 < "$ROOT/migrations/001_create_tables.down.sql"

echo "3/3 clean GeoJSON ..."
rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson"
rm -f "$REPO_ROOT/Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson"

echo "rollback complete"
