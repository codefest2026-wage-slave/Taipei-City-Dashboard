#!/usr/bin/env bash
# Rollback dashboard 504 seed (removes all 504-related rows).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ rolling back dashboard 504 ..."
pg_psql MANAGER -1 < "$ROOT/migrations/001_seed_dashboard.down.sql"

echo "▶ verify ..."
pg_psql MANAGER -c "SELECT id FROM dashboards WHERE id = 504;"
echo "✅ rollback complete"
