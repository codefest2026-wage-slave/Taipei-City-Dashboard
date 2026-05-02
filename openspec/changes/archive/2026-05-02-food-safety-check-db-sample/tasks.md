## 1. Write SQL fixture

- [x] 1.1 Create `db-sample-data/check.sql` with `BEGIN` / `COMMIT` wrapper
- [x] 1.2 Copy `CREATE TABLE IF NOT EXISTS food_safety_inspection_metrotaipei` DDL and all three indexes verbatim from `migrations/001_create_table.up.sql`
- [x] 1.3 Insert ~5 rows from 個人農場 CSV, converting ROC dates to AD and splitting city/district from address prefix
- [x] 1.4 Insert ~10 rows from 商業業者 CSV with the same transformations
- [x] 1.5 Verify rows cover: both cities (臺北市/新北市), all hazard levels (info/medium/high/critical), and both pass (合格) and fail (不合格) results

## 2. Verify fixture

- [x] 2.1 Run `psql $DB_DASHBOARD_URI -f db-sample-data/check.sql` against a clean local DB — confirm zero errors
- [x] 2.2 Run the same command a second time — confirm idempotency (no duplicate-key or "already exists" errors)
- [x] 2.3 Spot-check: `SELECT DISTINCT business_type, city, hazard_level, inspection_result FROM food_safety_inspection_metrotaipei ORDER BY 1,2,3,4` — confirm all expected values are present
