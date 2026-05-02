-- scripts/labor_safety/migrations/001_create_tables.down.sql
-- Rollback for 001: drop all 6 labor_safety tables.
-- up:   migrations/001_create_tables.up.sql
BEGIN;

DROP TABLE IF EXISTS labor_insurance_monthly_tpe   CASCADE;
DROP TABLE IF EXISTS labor_disputes_industry_tpe   CASCADE;
DROP TABLE IF EXISTS labor_disasters_ntpc          CASCADE;
DROP TABLE IF EXISTS labor_disasters_tpe           CASCADE;
DROP TABLE IF EXISTS labor_violations_ntpc         CASCADE;
DROP TABLE IF EXISTS labor_violations_tpe          CASCADE;

COMMIT;
