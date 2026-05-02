# School Meal Raw Records ETL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `scripts/school_meal_ingredients/` so that **every** CSV snapshot lands in `dashboard` DB as typed rows. The existing dedupe table (`school_meal_ingredient_names`) is preserved unchanged; this plan adds 6 new raw-data tables and one loader that fans out by filename.

**Architecture:** Mirror the existing labor-safety pattern: SQL migration creates 6 typed tables; one Python loader (`load_raw_records.py`) does TRUNCATE + `execute_values` per target. `apply.sh` is extended to call the new loader between migrations and the existing dedupe loader. No changes to `snapshot_apis.py` or `load_ingredient_names.py`.

**Tech Stack:** psycopg2, PostgreSQL (`dashboard` DB), bash.

**Scope:** delta plan — augments `docs/superpowers/plans/2026-05-02-school-meal-ingredients.md` (already executed). All file paths below are relative to the worktree base `/Users/teddy_peng/Projects/my/Taipei-City-Dashboard/.worktrees/school-meal-ingredients/`.

**Standing rules**
- Do NOT run `apply.sh` against any DB. The user runs it themselves once code is ready.
- Do NOT run `load_raw_records.py` against any DB.
- Do NOT modify `scripts/labor_safety/`, `scripts/school_meal_ingredients/etl/snapshot_apis.py`, `scripts/school_meal_ingredients/etl/load_ingredient_names.py`, or `migrations/001_create_ingredient_names.{up,down}.sql`.
- Verification = `python3 -c "import ast; ast.parse(...)"` for python, `bash -n` for shell, `grep -c '^BEGIN;$'` for SQL transactional framing, plus a runtime smoke test for pure helpers (`parse_city_filename` + `parse_date`).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql` | Create | DDL for 6 new tables + minimal indexes; transactional, idempotent |
| `scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql` | Create | Inverse DROPs |
| `scripts/school_meal_ingredients/etl/load_raw_records.py` | Create | One file, 6 mapper functions, glob+route |
| `scripts/school_meal_ingredients/apply.sh` | Modify | Insert step "2/4 load raw records" between migrations and dedupe |
| `scripts/school_meal_ingredients/rollback.sh` | Modify | Add `002_create_raw_tables.down.sql` BEFORE 001 down (FK-safe ordering — none here, but matches reverse order convention) |
| `scripts/school_meal_ingredients/README.md` | Modify | Add a "Raw record tables" section listing the 6 tables |

---

## Task 1: Migration 002 (6 raw tables)

**Files:**
- Create: `scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql`
- Create: `scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql`

- [ ] **Step 1: Write `migrations/002_create_raw_tables.up.sql`**

```sql
-- scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql
-- Project: 校園食材登入平台 raw-record tables
-- Purpose: Land every snapshot CSV into a typed table. Idempotent.
-- down:    migrations/002_create_raw_tables.down.sql
BEGIN;

-- 1. food_chinese_names.csv → food_dictionary (one-shot 食材中文名稱資料集)
CREATE TABLE IF NOT EXISTS school_meal_food_dictionary (
    id              SERIAL PRIMARY KEY,
    food_category   VARCHAR(100),
    formal_name     VARCHAR(200) NOT NULL,
    alias_name      TEXT
);
CREATE INDEX IF NOT EXISTS idx_smfd_formal_name
    ON school_meal_food_dictionary (formal_name);

-- 2. nation_*_學校供餐團膳業者*.csv → caterers
CREATE TABLE IF NOT EXISTS school_meal_caterers (
    id          SERIAL PRIMARY KEY,
    county      VARCHAR(20),
    name        VARCHAR(300) NOT NULL,
    tax_id      VARCHAR(20),
    address     VARCHAR(500)
);
CREATE INDEX IF NOT EXISTS idx_smc_tax_id
    ON school_meal_caterers (tax_id);

-- 3. nation_*_調味料及供應商*.csv → seasoning records (national, date-range entries)
CREATE TABLE IF NOT EXISTS school_meal_seasoning_records_nation (
    id                          SERIAL PRIMARY KEY,
    county                      VARCHAR(20),
    district                    VARCHAR(50),
    school_name                 VARCHAR(300),
    start_date                  DATE,
    end_date                    DATE,
    caterer_name                VARCHAR(300),
    caterer_tax_id              VARCHAR(20),
    seasoning_supplier_name     VARCHAR(300),
    seasoning_name              VARCHAR(200),
    certification_label         VARCHAR(100),
    certification_no            VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_smsrn_seasoning_name
    ON school_meal_seasoning_records_nation (seasoning_name);

-- 4. (tpe|ntpc)_*_*_午餐食材及供應商*.csv → ingredient records
CREATE TABLE IF NOT EXISTS school_meal_ingredient_records (
    id                          SERIAL PRIMARY KEY,
    -- provenance from filename (the API query that produced this row)
    year_queried                SMALLINT NOT NULL,
    month_queried               SMALLINT NOT NULL,
    county_queried              VARCHAR(20) NOT NULL,
    grade_queried               VARCHAR(20) NOT NULL,
    -- row data
    county                      VARCHAR(20),
    district                    VARCHAR(50),
    school_name                 VARCHAR(300),
    meal_date                   DATE,
    caterer_name                VARCHAR(300),
    caterer_tax_id              VARCHAR(20),
    ingredient_supplier_name    VARCHAR(300),
    ingredient_supplier_tax_id  VARCHAR(20),
    ingredient_name             VARCHAR(200),
    seasoning_supplier_name     VARCHAR(300),
    seasoning_supplier_tax_id   VARCHAR(20),
    seasoning_name              VARCHAR(200),
    certification_label         VARCHAR(100),
    certification_no            VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_smir_provenance
    ON school_meal_ingredient_records (year_queried, month_queried, county_queried);
CREATE INDEX IF NOT EXISTS idx_smir_ingredient_name
    ON school_meal_ingredient_records (ingredient_name);

-- 5. (tpe|ntpc)_*_*_午餐菜色資料集.csv → dish records
CREATE TABLE IF NOT EXISTS school_meal_dish_records (
    id                  SERIAL PRIMARY KEY,
    year_queried        SMALLINT NOT NULL,
    month_queried       SMALLINT NOT NULL,
    county_queried      VARCHAR(20) NOT NULL,
    grade_queried       VARCHAR(20) NOT NULL,
    county              VARCHAR(20),
    district            VARCHAR(50),
    school_name         VARCHAR(300),
    meal_date           DATE,
    dish_name           VARCHAR(200)
);
CREATE INDEX IF NOT EXISTS idx_smdr_provenance
    ON school_meal_dish_records (year_queried, month_queried, county_queried);
CREATE INDEX IF NOT EXISTS idx_smdr_dish_name
    ON school_meal_dish_records (dish_name);

-- 6. (tpe|ntpc)_*_*_午餐菜色及食材*.csv → dish-ingredient join records
CREATE TABLE IF NOT EXISTS school_meal_dish_ingredient_records (
    id                          SERIAL PRIMARY KEY,
    year_queried                SMALLINT NOT NULL,
    month_queried               SMALLINT NOT NULL,
    county_queried              VARCHAR(20) NOT NULL,
    grade_queried               VARCHAR(20) NOT NULL,
    county                      VARCHAR(20),
    district                    VARCHAR(50),
    school_name                 VARCHAR(300),
    meal_date                   DATE,
    caterer_name                VARCHAR(300),
    caterer_tax_id              VARCHAR(20),
    ingredient_supplier_name    VARCHAR(300),
    ingredient_supplier_tax_id  VARCHAR(20),
    dish_category               VARCHAR(100),
    dish_name                   VARCHAR(200),
    ingredient_name             VARCHAR(200),
    seasoning_supplier_name     VARCHAR(300),
    seasoning_supplier_tax_id   VARCHAR(20),
    seasoning_name              VARCHAR(200),
    certification_label         VARCHAR(100),
    certification_no            VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_smdir_provenance
    ON school_meal_dish_ingredient_records (year_queried, month_queried, county_queried);
CREATE INDEX IF NOT EXISTS idx_smdir_ingredient_name
    ON school_meal_dish_ingredient_records (ingredient_name);
CREATE INDEX IF NOT EXISTS idx_smdir_dish_name
    ON school_meal_dish_ingredient_records (dish_name);

COMMIT;
```

- [ ] **Step 2: Write `migrations/002_create_raw_tables.down.sql`**

```sql
-- scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
BEGIN;
DROP TABLE IF EXISTS school_meal_dish_ingredient_records;
DROP TABLE IF EXISTS school_meal_dish_records;
DROP TABLE IF EXISTS school_meal_ingredient_records;
DROP TABLE IF EXISTS school_meal_seasoning_records_nation;
DROP TABLE IF EXISTS school_meal_caterers;
DROP TABLE IF EXISTS school_meal_food_dictionary;
COMMIT;
```

- [ ] **Step 3: Verify**

```bash
grep -c '^BEGIN;$'  scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql
grep -c '^COMMIT;$' scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql
grep -c '^BEGIN;$'  scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
grep -c '^COMMIT;$' scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
grep -c 'CREATE TABLE IF NOT EXISTS' scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql
grep -c '^DROP TABLE IF EXISTS'      scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
```
Expected: `1`, `1`, `1`, `1`, `6`, `6`.

- [ ] **Step 4: Commit**

```bash
git add scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql \
        scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
git commit -m "feat(school-meal): migration 002 — 6 raw-record tables"
```

---

## Task 2: `etl/load_raw_records.py`

**Files:**
- Create: `scripts/school_meal_ingredients/etl/load_raw_records.py`

- [ ] **Step 1: Write `scripts/school_meal_ingredients/etl/load_raw_records.py`**

```python
#!/usr/bin/env python3
"""Load all CSV snapshots into typed raw tables.

Routes by filename:
  food_chinese_names.csv                     → school_meal_food_dictionary
  nation_*_學校供餐團膳業者資料集.csv         → school_meal_caterers
  nation_*_調味料及供應商資料集.csv           → school_meal_seasoning_records_nation
  (tpe|ntpc)_*_*_午餐食材及供應商資料集.csv  → school_meal_ingredient_records
  (tpe|ntpc)_*_*_午餐菜色資料集.csv          → school_meal_dish_records
  (tpe|ntpc)_*_*_午餐菜色及食材資料集.csv    → school_meal_dish_ingredient_records

Each TRUNCATE + INSERT is wrapped in the surrounding transaction (psycopg2's
`with conn:` context). All loaders run in the same transaction so a partial
failure rolls back the whole load.
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

SMI_ROOT      = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = SMI_ROOT / "snapshots"

CITY_FROM_PREFIX = {"tpe": "臺北市", "ntpc": "新北市", "nation": "全國"}


# ── filename routing ────────────────────────────────────────────────

CITY_FILENAME_RE = re.compile(
    r"^(?P<prefix>tpe|ntpc)_"
    r"(?P<year>\d{4})(?P<month>\d{2})"
    r"(?:_(?P<grade>[^_]+))?"
    r"_(?P<datasetname>.+)\.csv$"
)


def parse_city_filename(path):
    """For (tpe|ntpc)_YYYYMM[_grade]_<datasetname>.csv return
    (year:int, month:int, county_queried:str, grade_queried:str, datasetname:str)
    or None for non-matching filenames.
    """
    m = CITY_FILENAME_RE.match(path.name)
    if not m:
        return None
    return (
        int(m.group("year")),
        int(m.group("month")),
        CITY_FROM_PREFIX[m.group("prefix")],
        m.group("grade") or "",
        m.group("datasetname"),
    )


# ── value cleaners ──────────────────────────────────────────────────

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(s):
    """Accept 'YYYY/MM/DD', 'YYYY-MM-DD', or 'YYYY-MM-DD HH:MM:SS[.N]'.

    Returns ISO 'YYYY-MM-DD' string (psycopg2 casts to DATE) or None.
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.split()[0]            # drop time portion
    s = s.replace("/", "-")
    return s if DATE_RE.match(s) else None


def clean(v, max_len=None):
    """Strip + None-on-empty + optional length cap."""
    s = (str(v) if v is not None else "").strip()
    if not s:
        return None
    return s[:max_len] if max_len else s


# ── per-table loaders ───────────────────────────────────────────────

INSERT_FOOD_DICT_SQL = """
INSERT INTO school_meal_food_dictionary (food_category, formal_name, alias_name)
VALUES %s
"""


def load_food_dictionary(cur):
    path = SNAPSHOTS_DIR / "food_chinese_names.csv"
    if not path.exists():
        print(f"  ⚠️  {path.name} missing — skipping food_dictionary", file=sys.stderr)
        cur.execute("TRUNCATE school_meal_food_dictionary RESTART IDENTITY")
        return 0
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            formal = clean(r.get("食材中文標準名稱"), 200)
            if not formal:
                continue
            rows.append((
                clean(r.get("食材類別"), 100),
                formal,
                clean(r.get("俗名")),
            ))
    cur.execute("TRUNCATE school_meal_food_dictionary RESTART IDENTITY")
    if rows:
        execute_values(cur, INSERT_FOOD_DICT_SQL, rows, page_size=500)
    return len(rows)


INSERT_CATERER_SQL = """
INSERT INTO school_meal_caterers (county, name, tax_id, address)
VALUES %s
"""


def load_caterers(cur):
    rows = []
    files = sorted(SNAPSHOTS_DIR.glob("nation_*_學校供餐團膳業者*.csv"))
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                name = clean(r.get("業者名稱"), 300)
                if not name:
                    continue
                rows.append((
                    clean(r.get("縣市名稱"), 20),
                    name,
                    clean(r.get("業者統一編號"), 20),
                    clean(r.get("業者地址"), 500),
                ))
    cur.execute("TRUNCATE school_meal_caterers RESTART IDENTITY")
    if rows:
        execute_values(cur, INSERT_CATERER_SQL, rows, page_size=500)
    return len(rows)


INSERT_SEASONING_NATION_SQL = """
INSERT INTO school_meal_seasoning_records_nation (
    county, district, school_name, start_date, end_date,
    caterer_name, caterer_tax_id,
    seasoning_supplier_name, seasoning_name,
    certification_label, certification_no
) VALUES %s
"""


def load_seasoning_records_nation(cur):
    rows = []
    files = sorted(SNAPSHOTS_DIR.glob("nation_*_調味料及供應商*.csv"))
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append((
                    clean(r.get("縣市名稱"), 20),
                    clean(r.get("區域名稱"), 50),
                    clean(r.get("學校名稱"), 300),
                    parse_date(r.get("開始使用日期")),
                    parse_date(r.get("結束使用日期")),
                    clean(r.get("供餐業者"), 300),
                    clean(r.get("供餐業者統一編號"), 20),
                    clean(r.get("調味料供應商名稱"), 300),
                    clean(r.get("調味料名稱"), 200),
                    clean(r.get("認證標章"), 100),
                    clean(r.get("認證編號"), 100),
                ))
    cur.execute("TRUNCATE school_meal_seasoning_records_nation RESTART IDENTITY")
    if rows:
        execute_values(cur, INSERT_SEASONING_NATION_SQL, rows, page_size=1000)
    return len(rows)


INSERT_INGREDIENT_RECORD_SQL = """
INSERT INTO school_meal_ingredient_records (
    year_queried, month_queried, county_queried, grade_queried,
    county, district, school_name, meal_date,
    caterer_name, caterer_tax_id,
    ingredient_supplier_name, ingredient_supplier_tax_id, ingredient_name,
    seasoning_supplier_name, seasoning_supplier_tax_id, seasoning_name,
    certification_label, certification_no
) VALUES %s
"""

INGREDIENT_FN_RE = re.compile(r"^(?:tpe|ntpc)_\d{6}(?:_[^_]+)?_午餐食材及供應商.+\.csv$")


def load_ingredient_records(cur):
    rows = []
    files = sorted(p for p in SNAPSHOTS_DIR.glob("*.csv") if INGREDIENT_FN_RE.match(p.name))
    for path in files:
        meta = parse_city_filename(path)
        if not meta:
            continue
        yyyy, mm, county_q, grade_q, _ds = meta
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append((
                    yyyy, mm, county_q, grade_q,
                    clean(r.get("市縣名稱"), 20),
                    clean(r.get("區域名稱"), 50),
                    clean(r.get("學校名稱"), 300),
                    parse_date(r.get("供餐日期")),
                    clean(r.get("供餐業者"), 300),
                    clean(r.get("供餐業者統一編號"), 20),
                    clean(r.get("食材供應商名稱"), 300),
                    clean(r.get("食材供應商統編"), 20),
                    clean(r.get("食材名稱"), 200),
                    clean(r.get("調味料供應商名稱"), 300),
                    clean(r.get("調味料供應商統編"), 20),
                    clean(r.get("調味料名稱"), 200),
                    clean(r.get("認證標章"), 100),
                    clean(r.get("認證號碼"), 100),
                ))
    cur.execute("TRUNCATE school_meal_ingredient_records RESTART IDENTITY")
    if rows:
        execute_values(cur, INSERT_INGREDIENT_RECORD_SQL, rows, page_size=1000)
    return len(rows)


INSERT_DISH_RECORD_SQL = """
INSERT INTO school_meal_dish_records (
    year_queried, month_queried, county_queried, grade_queried,
    county, district, school_name, meal_date, dish_name
) VALUES %s
"""

DISH_FN_RE = re.compile(r"^(?:tpe|ntpc)_\d{6}(?:_[^_]+)?_午餐菜色資料集\.csv$")


def load_dish_records(cur):
    rows = []
    files = sorted(p for p in SNAPSHOTS_DIR.glob("*.csv") if DISH_FN_RE.match(p.name))
    for path in files:
        meta = parse_city_filename(path)
        if not meta:
            continue
        yyyy, mm, county_q, grade_q, _ds = meta
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append((
                    yyyy, mm, county_q, grade_q,
                    clean(r.get("市縣名稱"), 20),
                    clean(r.get("區域名稱"), 50),
                    clean(r.get("學校名稱"), 300),
                    parse_date(r.get("供餐日期")),
                    clean(r.get("菜色名稱"), 200),
                ))
    cur.execute("TRUNCATE school_meal_dish_records RESTART IDENTITY")
    if rows:
        execute_values(cur, INSERT_DISH_RECORD_SQL, rows, page_size=1000)
    return len(rows)


INSERT_DISH_INGREDIENT_RECORD_SQL = """
INSERT INTO school_meal_dish_ingredient_records (
    year_queried, month_queried, county_queried, grade_queried,
    county, district, school_name, meal_date,
    caterer_name, caterer_tax_id,
    ingredient_supplier_name, ingredient_supplier_tax_id,
    dish_category, dish_name, ingredient_name,
    seasoning_supplier_name, seasoning_supplier_tax_id, seasoning_name,
    certification_label, certification_no
) VALUES %s
"""

DISH_INGREDIENT_FN_RE = re.compile(r"^(?:tpe|ntpc)_\d{6}(?:_[^_]+)?_午餐菜色及食材.+\.csv$")


def load_dish_ingredient_records(cur):
    rows = []
    files = sorted(p for p in SNAPSHOTS_DIR.glob("*.csv") if DISH_INGREDIENT_FN_RE.match(p.name))
    for path in files:
        meta = parse_city_filename(path)
        if not meta:
            continue
        yyyy, mm, county_q, grade_q, _ds = meta
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append((
                    yyyy, mm, county_q, grade_q,
                    clean(r.get("市縣名稱"), 20),
                    clean(r.get("區域名稱"), 50),
                    clean(r.get("學校名稱"), 300),
                    parse_date(r.get("供餐日期")),
                    clean(r.get("供餐業者"), 300),
                    clean(r.get("供餐業者統一編號"), 20),
                    clean(r.get("食材供應商名稱"), 300),
                    clean(r.get("食材供應商統編"), 20),
                    clean(r.get("菜色類別"), 100),
                    clean(r.get("菜色名稱"), 200),
                    clean(r.get("食材名稱"), 200),
                    clean(r.get("調味料供應商名稱"), 300),
                    clean(r.get("調味料供應商統編"), 20),
                    clean(r.get("調味料名稱"), 200),
                    clean(r.get("認證標章"), 100),
                    clean(r.get("認證號碼"), 100),
                ))
    cur.execute("TRUNCATE school_meal_dish_ingredient_records RESTART IDENTITY")
    if rows:
        execute_values(cur, INSERT_DISH_INGREDIENT_RECORD_SQL, rows, page_size=1000)
    return len(rows)


def main():
    print("=== load_raw_records ===")
    if not SNAPSHOTS_DIR.exists() or not list(SNAPSHOTS_DIR.glob("*.csv")):
        print("❌ no snapshot CSVs found — run snapshot_apis.py first.", file=sys.stderr)
        sys.exit(1)

    counts = {}
    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        counts["food_dictionary"]          = load_food_dictionary(cur)
        counts["caterers"]                 = load_caterers(cur)
        counts["seasoning_records_nation"] = load_seasoning_records_nation(cur)
        counts["ingredient_records"]       = load_ingredient_records(cur)
        counts["dish_records"]             = load_dish_records(cur)
        counts["dish_ingredient_records"]  = load_dish_ingredient_records(cur)

    print("✅ raw records loaded:")
    for table, n in counts.items():
        print(f"  school_meal_{table:30s}: {n:>10,} rows")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: chmod +x**

```bash
chmod +x scripts/school_meal_ingredients/etl/load_raw_records.py
```

- [ ] **Step 3: Verify python syntax**

```bash
python3 -c "import ast; ast.parse(open('scripts/school_meal_ingredients/etl/load_raw_records.py').read())"
```
Expected: no output.

- [ ] **Step 4: Verify pure-function helpers (no DB)**

```bash
cd /Users/teddy_peng/Projects/my/Taipei-City-Dashboard/.worktrees/school-meal-ingredients
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "scripts/school_meal_ingredients/etl")
import load_raw_records as L

# parse_city_filename
assert L.parse_city_filename(Path("tpe_202410_國中小_午餐食材及供應商資料集.csv")) == \
    (2024, 10, "臺北市", "國中小", "午餐食材及供應商資料集")
assert L.parse_city_filename(Path("ntpc_202503_高中職_午餐菜色資料集.csv")) == \
    (2025, 3, "新北市", "高中職", "午餐菜色資料集")
# nation prefix is NOT a city filename
assert L.parse_city_filename(Path("nation_202410_學校供餐團膳業者資料集.csv")) is None
assert L.parse_city_filename(Path("food_chinese_names.csv")) is None

# parse_date — three accepted formats
assert L.parse_date("2024/10/01") == "2024-10-01"
assert L.parse_date("2024-10-01") == "2024-10-01"
assert L.parse_date("2024-10-01 00:00:00.0") == "2024-10-01"
assert L.parse_date("") is None
assert L.parse_date(None) is None
assert L.parse_date("garbage") is None

# clean
assert L.clean("  abc  ") == "abc"
assert L.clean("") is None
assert L.clean(None) is None
assert L.clean("a" * 250, max_len=200) == "a" * 200

# routing regexes
assert L.INGREDIENT_FN_RE.match("tpe_202410_國中小_午餐食材及供應商資料集.csv") is not None
assert L.INGREDIENT_FN_RE.match("ntpc_202503_高中職_午餐食材及供應商資料集.csv") is not None
assert L.DISH_FN_RE.match("tpe_202410_國中小_午餐菜色資料集.csv") is not None
assert L.DISH_FN_RE.match("tpe_202410_國中小_午餐菜色及食材資料集.csv") is None  # not dish_records!
assert L.DISH_INGREDIENT_FN_RE.match("tpe_202410_國中小_午餐菜色及食材資料集.csv") is not None
assert L.DISH_INGREDIENT_FN_RE.match("tpe_202410_國中小_午餐菜色資料集.csv") is None  # not dish_ingredient!

print("OK")
PY
```
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/school_meal_ingredients/etl/load_raw_records.py
git commit -m "feat(school-meal): add load_raw_records.py (6 raw tables)"
```

---

## Task 3: Wire into apply.sh + rollback.sh

**Files:**
- Modify: `scripts/school_meal_ingredients/apply.sh`
- Modify: `scripts/school_meal_ingredients/rollback.sh`

- [ ] **Step 1: Update `apply.sh` — replace the body verbatim**

The new body of `apply.sh` (between the `source "$ROOT/_db_env.sh"` line and the `echo "✅ apply complete"` final line). Existing comment block + shebang + ROOT/source unchanged. Replace the section starting at `echo "▶ target dashboard:"` through `echo "✅ apply complete"` with:

```bash
echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/4 migrations up ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.up.sql"
pg_psql -1 < "$ROOT/migrations/002_create_raw_tables.up.sql"

echo "2/4 ETL: raw records ..."
python3 "$ROOT/etl/load_raw_records.py"

echo "3/4 ETL: ingredient names dedupe ..."
python3 "$ROOT/etl/load_ingredient_names.py"

echo "4/4 verify row counts ..."
pg_psql -c "
SELECT 'school_meal_ingredient_names'              AS t, COUNT(*) FROM school_meal_ingredient_names
UNION ALL SELECT 'school_meal_food_dictionary',              COUNT(*) FROM school_meal_food_dictionary
UNION ALL SELECT 'school_meal_caterers',                     COUNT(*) FROM school_meal_caterers
UNION ALL SELECT 'school_meal_seasoning_records_nation',     COUNT(*) FROM school_meal_seasoning_records_nation
UNION ALL SELECT 'school_meal_ingredient_records',           COUNT(*) FROM school_meal_ingredient_records
UNION ALL SELECT 'school_meal_dish_records',                 COUNT(*) FROM school_meal_dish_records
UNION ALL SELECT 'school_meal_dish_ingredient_records',      COUNT(*) FROM school_meal_dish_ingredient_records;"

echo "✅ apply complete"
```

Expected final apply.sh (full file) for reference:

```bash
#!/usr/bin/env bash
# Apply school meal ingredients migrations and load deduped names.
# Idempotent: safe to run multiple times. Use rollback.sh to revert.
#
# Connects via env vars resolved by _db_env.sh — works for local docker
# postgres or cloud DB depending on scripts/school_meal_ingredients/.env.script.
#
# IMPORTANT: This does NOT call snapshot_apis.py. Run that manually to
# refresh the committed CSVs in snapshots/ before running apply.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/4 migrations up ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.up.sql"
pg_psql -1 < "$ROOT/migrations/002_create_raw_tables.up.sql"

echo "2/4 ETL: raw records ..."
python3 "$ROOT/etl/load_raw_records.py"

echo "3/4 ETL: ingredient names dedupe ..."
python3 "$ROOT/etl/load_ingredient_names.py"

echo "4/4 verify row counts ..."
pg_psql -c "
SELECT 'school_meal_ingredient_names'              AS t, COUNT(*) FROM school_meal_ingredient_names
UNION ALL SELECT 'school_meal_food_dictionary',              COUNT(*) FROM school_meal_food_dictionary
UNION ALL SELECT 'school_meal_caterers',                     COUNT(*) FROM school_meal_caterers
UNION ALL SELECT 'school_meal_seasoning_records_nation',     COUNT(*) FROM school_meal_seasoning_records_nation
UNION ALL SELECT 'school_meal_ingredient_records',           COUNT(*) FROM school_meal_ingredient_records
UNION ALL SELECT 'school_meal_dish_records',                 COUNT(*) FROM school_meal_dish_records
UNION ALL SELECT 'school_meal_dish_ingredient_records',      COUNT(*) FROM school_meal_dish_ingredient_records;"

echo "✅ apply complete"
```

- [ ] **Step 2: Update `rollback.sh` — replace the body**

Existing rollback.sh body has step "1/1 down: drop tables ..." running 001 down. Replace with:

```bash
echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/2 down: drop raw tables ..."
pg_psql -1 < "$ROOT/migrations/002_create_raw_tables.down.sql"

echo "2/2 down: drop dedupe table ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.down.sql"

echo "✅ rollback complete"
```

Expected final rollback.sh (full file) for reference:

```bash
#!/usr/bin/env bash
# Rollback school meal ingredients: drop school_meal_* tables.
# Idempotent: safe even if apply was never run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./_db_env.sh
source "$ROOT/_db_env.sh"

echo "▶ target dashboard: $DB_DASHBOARD_HOST:$DB_DASHBOARD_PORT/$DB_DASHBOARD_DBNAME (sslmode=$DB_DASHBOARD_SSLMODE)"
echo

echo "1/2 down: drop raw tables ..."
pg_psql -1 < "$ROOT/migrations/002_create_raw_tables.down.sql"

echo "2/2 down: drop dedupe table ..."
pg_psql -1 < "$ROOT/migrations/001_create_ingredient_names.down.sql"

echo "✅ rollback complete"
```

(The header comment changed from "drop school_meal_ingredient_names" to "drop school_meal_* tables" — that one-line edit is intentional.)

- [ ] **Step 3: Verify**

```bash
bash -n scripts/school_meal_ingredients/apply.sh
bash -n scripts/school_meal_ingredients/rollback.sh
grep -c '002_create_raw_tables' scripts/school_meal_ingredients/apply.sh
grep -c '002_create_raw_tables' scripts/school_meal_ingredients/rollback.sh
grep -c 'load_raw_records.py'   scripts/school_meal_ingredients/apply.sh
grep -c '1/4 migrations up'     scripts/school_meal_ingredients/apply.sh
grep -c '4/4 verify'            scripts/school_meal_ingredients/apply.sh
```
Expected: clean parse on both; counts `1`, `1`, `1`, `1`, `1`.

- [ ] **Step 4: Commit**

```bash
git add scripts/school_meal_ingredients/apply.sh \
        scripts/school_meal_ingredients/rollback.sh
git commit -m "feat(school-meal): wire raw-records loader into apply.sh + rollback.sh"
```

---

## Task 4: Update README

**Files:**
- Modify: `scripts/school_meal_ingredients/README.md`

- [ ] **Step 1: Insert a new "Raw record tables" section AFTER "Datasets in scope" and BEFORE "Snapshot crawler — token expiry"**

In `scripts/school_meal_ingredients/README.md`, find the line `## Snapshot crawler — token expiry` and insert the following block immediately above it (with a trailing blank line):

```markdown
## Raw record tables (apply.sh step 2/4)

`load_raw_records.py` lands every CSV's rows into a typed table. Re-running
the loader TRUNCATEs each target before INSERT, so apply.sh stays idempotent.

| Table | Source CSV | Provenance columns? |
|---|---|---|
| `school_meal_food_dictionary` | `food_chinese_names.csv` | no — one-shot dictionary |
| `school_meal_caterers` | `nation_*_學校供餐團膳業者*.csv` | no — country-wide list |
| `school_meal_seasoning_records_nation` | `nation_*_調味料及供應商*.csv` | no — entries carry their own start/end dates |
| `school_meal_ingredient_records` | `(tpe\|ntpc)_*_*_午餐食材及供應商*.csv` | yes — `year_queried, month_queried, county_queried, grade_queried` |
| `school_meal_dish_records` | `(tpe\|ntpc)_*_*_午餐菜色資料集.csv` | yes — same 4 |
| `school_meal_dish_ingredient_records` | `(tpe\|ntpc)_*_*_午餐菜色及食材*.csv` | yes — same 4 |

The dedupe table `school_meal_ingredient_names` (apply.sh step 3/4) is
unchanged — still derived from the same CSV scan with column-detection +
fallback.

```

- [ ] **Step 2: Verify**

```bash
grep -c '^## Raw record tables' scripts/school_meal_ingredients/README.md
grep -c 'school_meal_food_dictionary' scripts/school_meal_ingredients/README.md
grep -c 'school_meal_dish_ingredient_records' scripts/school_meal_ingredients/README.md
head -1 scripts/school_meal_ingredients/README.md
tail -1 scripts/school_meal_ingredients/README.md
```
Expected: counts `1`, ≥1, ≥1; head still `# School Meal Ingredients — 校園食材登入平台 ETL`; tail still 3 backticks.

- [ ] **Step 3: Commit**

```bash
git add scripts/school_meal_ingredients/README.md
git commit -m "docs(school-meal): document 6 raw record tables in README"
```

---

## Task 5: Final tree verification + delivery checklist

**Files:** none changed; verification only.

- [ ] **Step 1: Verify final tree**

```bash
find scripts/school_meal_ingredients -type f -not -path '*/__pycache__/*' -not -path '*/snapshots/*.csv' -not -path '*/snapshots/manifest.json' -not -path '*/backups/*' | sort
```
Expected (17 paths — adds `002_create_raw_tables.{up,down}.sql` and `etl/load_raw_records.py` to the prior 15):
```
scripts/school_meal_ingredients/.env.script.example
scripts/school_meal_ingredients/.gitignore
scripts/school_meal_ingredients/README.md
scripts/school_meal_ingredients/_db_env.sh
scripts/school_meal_ingredients/apply.sh
scripts/school_meal_ingredients/backup_db.sh
scripts/school_meal_ingredients/backups/.gitkeep
scripts/school_meal_ingredients/etl/__init__.py
scripts/school_meal_ingredients/etl/_db.py
scripts/school_meal_ingredients/etl/load_ingredient_names.py
scripts/school_meal_ingredients/etl/load_raw_records.py
scripts/school_meal_ingredients/etl/snapshot_apis.py
scripts/school_meal_ingredients/migrations/001_create_ingredient_names.down.sql
scripts/school_meal_ingredients/migrations/001_create_ingredient_names.up.sql
scripts/school_meal_ingredients/migrations/002_create_raw_tables.down.sql
scripts/school_meal_ingredients/migrations/002_create_raw_tables.up.sql
scripts/school_meal_ingredients/rollback.sh
scripts/school_meal_ingredients/snapshots/.gitkeep
```

- [ ] **Step 2: Verify executable bits**

```bash
ls -la scripts/school_meal_ingredients/*.sh \
       scripts/school_meal_ingredients/etl/*.py
```
Expected: all `*.sh` + `etl/snapshot_apis.py` + `etl/load_ingredient_names.py` + `etl/load_raw_records.py` have `x` bit. `etl/__init__.py` and `etl/_db.py` do NOT.

- [ ] **Step 3: Verify all shell scripts parse**

```bash
for f in scripts/school_meal_ingredients/*.sh; do
  bash -n "$f" && echo "OK $f"
done
```
Expected: 4 lines (apply.sh, rollback.sh, backup_db.sh, _db_env.sh).

- [ ] **Step 4: Verify all python files parse**

```bash
for f in scripts/school_meal_ingredients/etl/*.py; do
  python3 -c "import ast; ast.parse(open('$f').read())" && echo "OK $f"
done
```
Expected: 4 lines (`__init__.py`, `_db.py`, `load_ingredient_names.py`, `load_raw_records.py`, `snapshot_apis.py` — actually 5).

- [ ] **Step 5: Verify NO DB / API was executed by Claude**

```bash
git -C /Users/teddy_peng/Projects/my/Taipei-City-Dashboard/.worktrees/school-meal-ingredients log --oneline -10
```
Expected: 4–5 new commits all `feat(school-meal)` / `docs(school-meal)` (one per Task 1–4) + this plan-doc commit. None mentions DB execution.

- [ ] **Step 6: Print delivery summary**

```
✅ Raw-records ETL extension complete.

New tables in dashboard DB after user runs ./apply.sh:
  - school_meal_food_dictionary
  - school_meal_caterers
  - school_meal_seasoning_records_nation
  - school_meal_ingredient_records
  - school_meal_dish_records
  - school_meal_dish_ingredient_records

Existing dedupe table school_meal_ingredient_names unchanged.

Next steps for the USER:
  1. ./scripts/school_meal_ingredients/backup_db.sh   # backup before re-applying
  2. ./scripts/school_meal_ingredients/rollback.sh    # drop old tables (optional clean slate)
  3. ./scripts/school_meal_ingredients/apply.sh       # creates new tables + loads all CSVs
```

---

## Self-Review

**Spec coverage:**
- 6 tables defined (Task 1) ✓
- All 6 mapped from CSVs (Task 2) ✓
- apply.sh wired (Task 3) ✓
- rollback.sh wired (Task 3) ✓
- README updated (Task 4) ✓
- Delivery verified (Task 5) ✓

**Placeholder scan:** All steps contain literal SQL / Python / bash. No "TBD" / "implement later" anywhere.

**Type / name consistency:** Table names match across migration, loader (TRUNCATE / INSERT SQL), apply.sh verify query, README. Column names in INSERT match column names in CREATE TABLE. Filename regexes (`INGREDIENT_FN_RE`, `DISH_FN_RE`, `DISH_INGREDIENT_FN_RE`) used consistently in their respective loader functions. `parse_city_filename` returns 5-tuple consistently with all 3 city-table loaders' destructuring.

**Idempotency:** `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` + `TRUNCATE … RESTART IDENTITY` per loader → re-running apply.sh is safe.

**Standing rules:** No DB connection by Claude (only by user); no live API calls; `scripts/labor_safety/` not touched; existing `snapshot_apis.py` / `load_ingredient_names.py` / migration 001 not modified.
