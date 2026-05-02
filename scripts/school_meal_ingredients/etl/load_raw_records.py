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
