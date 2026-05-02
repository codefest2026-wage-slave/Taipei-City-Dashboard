## Context

The `food_safety_inspection_metrotaipei` DAG loads two CSVs (個人農場 / 商業業者) into a PostgreSQL table of the same name. The table schema is already defined in `migrations/001_create_table.up.sql`. The `db-sample-data/` folder holds SQL fixtures used for local dev bootstrapping, but no fixture exists yet for this table.

## Goals / Non-Goals

**Goals:**
- Provide an idempotent `db-sample-data/check.sql` that creates the table and inserts ~15 representative rows.
- Cover both `business_type` values, both cities (臺北市 / 新北市), all 5 hazard levels (info / low / medium / high / critical), and both pass (合格) and fail (不合格 / 不符合規定) inspection results.
- Apply the same column transformations the DAG applies: ROC民國 year → AD date, city/district split from leading address characters.

**Non-Goals:**
- Full data dump (17 000+ rows) — a representative sample is sufficient.
- Modifying the DAG, migrations, backend routes, or frontend code.
- Automating fixture generation (manual SQL is fine; the dataset rarely changes shape).

## Decisions

### Use `CREATE TABLE IF NOT EXISTS` copied from migrations
**Decision**: Mirror the DDL from `migrations/001_create_table.up.sql` verbatim (including indexes), wrapped in a transaction.  
**Rationale**: Keeps the fixture self-contained; running it twice is safe. Alternatives (relying on migrations to run first) create ordering dependencies that complicate CI.

### ~15 hand-picked rows, not a full data dump
**Decision**: Pick ≤15 rows total (≈5 from 個人農場, ≈10 from 商業業者).  
**Rationale**: The table has 17 629 source rows; importing all would bloat the fixture and slow CI. A curated sample that exercises every code path (hazard level, city, pass/fail) is more maintainable. Alternatives (pg_dump subset) are harder to audit.

### ROC date converted inline in SQL literals
**Decision**: Convert 民國 dates to AD literals directly in the `INSERT` values (e.g. `110/11/2` → `'2021-11-02'`).  
**Rationale**: SQL fixtures should be self-contained and not require Python. The mapping rule is simple: AD year = ROC year + 1911.

### city / district derived from address prefix in SQL
**Decision**: Hardcode the derived `city` and `district` values in the `INSERT` rows rather than computing them via SQL expressions.  
**Rationale**: The derivation logic (first 3 chars → city, chars 3–6 → district) is deterministic; hardcoding avoids SQL complexity and matches what the DAG produces.

## Risks / Trade-offs

- **Schema drift** → If migrations add/remove columns, the fixture's DDL will be out of sync. Mitigation: fixture DDL is a verbatim copy; `diff` against the migration in CI is the long-term fix (not in scope here).
- **Sample bias** → Hand-picked rows may not exercise every future dashboard filter. Mitigation: sample covers the categorical axes (city, hazard, result, business_type) that existing frontend filters use.

## Migration Plan

1. Write `db-sample-data/check.sql`.
2. Test locally: `psql $DB_DASHBOARD_URI -f db-sample-data/check.sql` — should complete without errors on a fresh schema.
3. Commit. No service restarts needed.
