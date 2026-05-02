## ADDED Requirements

### Requirement: SQL fixture creates table idempotently
`db-sample-data/check.sql` SHALL contain a `CREATE TABLE IF NOT EXISTS food_safety_inspection_metrotaipei` statement with the same column definitions and indexes as `migrations/001_create_table.up.sql`, wrapped in a `BEGIN` / `COMMIT` transaction.

#### Scenario: Running fixture on empty schema
- **WHEN** the SQL file is executed against a PostgreSQL DB with no existing `food_safety_inspection_metrotaipei` table
- **THEN** the table and all three indexes are created without error

#### Scenario: Running fixture twice (idempotency)
- **WHEN** the SQL file is executed a second time on the same DB
- **THEN** no error is raised and no duplicate rows are inserted

### Requirement: Sample rows cover both business types
The `INSERT` statements SHALL include rows with `business_type = '個人農場'` and rows with `business_type = '商業業者'`.

#### Scenario: Both business types present
- **WHEN** the fixture is loaded and `SELECT DISTINCT business_type FROM food_safety_inspection_metrotaipei` is run
- **THEN** the result contains both `'個人農場'` and `'商業業者'`

### Requirement: Sample rows cover both cities
The `INSERT` statements SHALL include rows where `city = '臺北市'` and rows where `city = '新北市'`.

#### Scenario: Both cities present
- **WHEN** the fixture is loaded and `SELECT DISTINCT city FROM food_safety_inspection_metrotaipei` is run
- **THEN** the result contains both `'臺北市'` and `'新北市'`

### Requirement: Sample rows cover all five hazard levels
The `INSERT` statements SHALL include at least one row for each of the five hazard level values: `info`, `low`, `medium`, `high`, `critical`.

#### Scenario: All hazard levels present
- **WHEN** the fixture is loaded and `SELECT DISTINCT hazard_level FROM food_safety_inspection_metrotaipei ORDER BY 1` is run
- **THEN** the result contains `critical`, `high`, `info`, `medium` (low may be absent only if no source row exists; otherwise SHALL be present)

### Requirement: Sample rows cover pass and fail inspection results
The `INSERT` statements SHALL include rows where `inspection_result = '合格'` and rows where `inspection_result` is a non-conformance value (e.g. `'不合格'`).

#### Scenario: Pass and fail results both present
- **WHEN** the fixture is loaded and `SELECT inspection_result FROM food_safety_inspection_metrotaipei` is run
- **THEN** the result contains at least one `'合格'` row and at least one non-conformance row

### Requirement: Dates are stored as AD calendar dates
Inspection dates from the source CSVs (ROC民國 format `YYY/MM/DD`) SHALL be converted to ISO AD dates (`YYYY-MM-DD`) before insertion. The conversion rule is `AD year = ROC year + 1911`.

#### Scenario: ROC date 110/11/2 is inserted as AD date
- **WHEN** the fixture is loaded
- **THEN** `SELECT inspection_date FROM food_safety_inspection_metrotaipei WHERE source_id = 1 AND business_type = '個人農場'` returns `2021-11-02`

### Requirement: city and district are derived from address prefix
The `city` column SHALL contain `'臺北市'` or `'新北市'` (the first 3 characters of the address), and `district` SHALL contain the next 3 characters (e.g. `'中山區'`). Addresses that do not begin with a recognised city SHALL have `NULL` in both columns.

#### Scenario: Address starting with 臺北市中山區
- **WHEN** the fixture is loaded
- **THEN** a row with `address = '臺北市中山區'` has `city = '臺北市'` and `district = '中山區'`
