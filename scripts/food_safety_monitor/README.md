# 食安監控系統 Dashboard 504 — Standalone Seed

Self-contained registration for dashboard 504. **No new tables, no ETL.** All data
is hardcoded in `migrations/001_seed_dashboard.up.sql` (chart) or served from
`Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/*` (geojson/json).

Coexists with 503「食安風險追蹤器」.

## Quickstart

```bash
./scripts/food_safety_monitor/backup_db.sh        # optional safety net
./scripts/food_safety_monitor/apply.sh            # register dashboard 504
# open http://localhost:8080 → login → dashboard 504「食安監控系統」
./scripts/food_safety_monitor/rollback.sh         # remove dashboard 504
```

Idempotent. Re-running `apply.sh` produces identical state.
