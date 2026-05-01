#!/usr/bin/env python3
"""
Load TPE labor statistics into labor_disputes_industry_tpe and
labor_insurance_monthly_tpe.

Sources (CSV only — pre-existing in docs/assets/, NO HTTP):
  1. docs/assets/勞資爭議統計依行業別區分(11503).csv     (Big5)
  2. docs/assets/臺北市勞工保險及就業服務按月別.csv      (UTF-8 BOM)

Adapted from scripts/load_labor_stats_tpe.py (main worktree).
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs, REPO_ROOT  # noqa: E402

DISPUTES_CSV  = REPO_ROOT / "docs/assets/勞資爭議統計依行業別區分(11503).csv"
INSURANCE_CSV = REPO_ROOT / "docs/assets/臺北市勞工保險及就業服務按月別.csv"

INSERT_DISPUTES = """
INSERT INTO labor_disputes_industry_tpe (year, period, industry, case_count) VALUES %s
"""

INSURANCE_COLS = (
    "period_label, period_date, "
    "insured_units, insured_persons, benefit_cases, benefit_amount, "
    "new_seekers, new_openings, placed_seekers, placed_openings, "
    "placement_rate, utilization_rate, accident_cases, accident_deaths"
)
INSERT_INSURANCE = f"INSERT INTO labor_insurance_monthly_tpe ({INSURANCE_COLS}) VALUES %s"

INSURANCE_COL_MAP = {
    "統計期":                                "period_label",
    "勞工保險投保單位數[家]":                 "insured_units",
    "勞工保險投保人數[人]":                   "insured_persons",
    "勞工保險給付件數[件]":                   "benefit_cases",
    "勞工保險給付金額[千元]":                 "benefit_amount",
    "市府推介就業服務/新登記求職人數[人]":    "new_seekers",
    "市府推介就業服務/新登記求才人數[人]":    "new_openings",
    "市府推介就業服務/有效求職推介就業人數[人]": "placed_seekers",
    "市府推介就業服務/有效求才僱用人數[人]":  "placed_openings",
    "市府推介就業服務/求職就業率[%]":         "placement_rate",
    "市府推介就業服務/求才利用率[%]":         "utilization_rate",
    "重大職業災害發生件數[件]":               "accident_cases",
    "重大職業災害死亡人數[人]":               "accident_deaths",
}
NUMERIC_COLS = {"placement_rate", "utilization_rate"}


def to_int(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def to_float(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def roc_year_month(s):
    """'87年 1月' → '1998-01-01'."""
    m = re.match(r"(\d+)年\s*(\d+)月", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-01"


def load_disputes():
    rows = []
    if not DISPUTES_CSV.exists():
        print(f"  ⚠️  {DISPUTES_CSV} missing — skipping disputes", file=sys.stderr)
        return rows
    with DISPUTES_CSV.open(encoding="big5", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                year_roc = to_int(row.get("年度", "").strip())
                if year_roc is None:
                    continue
                year = year_roc + 1911
                period   = (row.get("統計月份") or "").strip() or None
                industry = (row.get("行業別") or "").strip()
                cases    = to_int(row.get("案件數（數量）") or "")
                if not industry or cases is None:
                    continue
                rows.append((year, period, industry, cases))
            except Exception as e:
                print(f"  ⚠️  skip disputes row: {e}", file=sys.stderr)
                continue
    print(f"  [disputes] {len(rows):,} rows")
    return rows


def load_insurance():
    rows = []
    if not INSURANCE_CSV.exists():
        print(f"  ⚠️  {INSURANCE_CSV} missing — skipping insurance", file=sys.stderr)
        return rows
    with INSURANCE_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                period_label = (row.get("統計期") or "").strip()
                if not period_label:
                    continue
                period_date = roc_year_month(period_label)
                if not period_date:
                    continue
                rec = {"period_label": period_label, "period_date": period_date}
                for csv_col, db_col in INSURANCE_COL_MAP.items():
                    if db_col == "period_label":
                        continue
                    raw = row.get(csv_col, "")
                    rec[db_col] = to_float(raw) if db_col in NUMERIC_COLS else to_int(raw)
                rows.append((
                    rec["period_label"],   rec["period_date"],
                    rec.get("insured_units"),    rec.get("insured_persons"),
                    rec.get("benefit_cases"),    rec.get("benefit_amount"),
                    rec.get("new_seekers"),      rec.get("new_openings"),
                    rec.get("placed_seekers"),   rec.get("placed_openings"),
                    rec.get("placement_rate"),   rec.get("utilization_rate"),
                    rec.get("accident_cases"),   rec.get("accident_deaths"),
                ))
            except Exception as e:
                print(f"  ⚠️  skip insurance row: {e}", file=sys.stderr)
                continue
    print(f"  [insurance] {len(rows):,} rows")
    return rows


def main():
    print("=== load_stats_tpe ===")
    disputes  = load_disputes()
    insurance = load_insurance()

    if not disputes and not insurance:
        print("❌ no rows to insert", file=sys.stderr)
        sys.exit(1)

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE labor_disputes_industry_tpe RESTART IDENTITY")
        if disputes:
            execute_values(cur, INSERT_DISPUTES, disputes, page_size=500)
        cur.execute("TRUNCATE labor_insurance_monthly_tpe RESTART IDENTITY")
        if insurance:
            execute_values(cur, INSERT_INSURANCE, insurance, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(disputes):,} rows → labor_disputes_industry_tpe")
    print(f"✅ {len(insurance):,} rows → labor_insurance_monthly_tpe")


if __name__ == "__main__":
    main()
