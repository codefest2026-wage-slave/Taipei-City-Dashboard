## Why

The `food_safety_inspection_metrotaipei` DAG merges two CSV sources (個人農場 and 商業業者) into PostgreSQL, but the repo has no seeded SQL fixture for the resulting table. Without a `db-sample-data/check.sql` file, local development and CI cannot bootstrap the dashboard DB with representative food-safety rows, blocking demo and onboarding workflows.

## What Changes

- Add `db-sample-data/check.sql`: creates the `food_safety_inspection_metrotaipei` table (idempotent) and inserts a representative sample of rows drawn from both CSV sources, with the same column mapping and transformations the DAG applies (ROC date → AD date, city/district extraction, `business_type` tag).

## Capabilities

### New Capabilities

- `food-safety-check-db-sample`: SQL fixture that seeds `food_safety_inspection_metrotaipei` with sample rows covering both `個人農場` and `商業業者` business types, hazard levels (info / low / medium / high / critical), both cities (臺北市 / 新北市), and pass/fail inspection results.

### Modified Capabilities

## Impact

- New file: `db-sample-data/check.sql`
- No changes to existing code, DAG, migrations, or backend routes.
- Local Docker setup (`docker-compose-db.yaml`) gains importable sample data for the food safety table.
