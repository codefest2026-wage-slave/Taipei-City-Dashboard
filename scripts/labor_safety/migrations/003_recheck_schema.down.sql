-- scripts/labor_safety/migrations/003_recheck_schema.down.sql
-- Rollback for 003: drop GCIS tables AND the materialized recheck tables
-- (the latter created by build_recheck_priority.sql via CREATE TABLE AS).
-- up: 003_recheck_schema.up.sql
BEGIN;

DROP TABLE IF EXISTS labor_recheck_priority_ntpc CASCADE;
DROP TABLE IF EXISTS labor_recheck_priority_tpe  CASCADE;
DROP TABLE IF EXISTS gcis_companies_ntpc         CASCADE;
DROP TABLE IF EXISTS gcis_companies_tpe          CASCADE;
DROP TABLE IF EXISTS industry_codes              CASCADE;
DROP FUNCTION IF EXISTS norm_company(text);

COMMIT;
