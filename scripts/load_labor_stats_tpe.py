#!/usr/bin/env python3
"""
Load TPE labor statistics into PostgreSQL dashboard DB.

Tables:
  - labor_disputes_industry_tpe  (from 勞資爭議統計依行業別區分(11503).csv)
  - labor_insurance_monthly_tpe  (from 臺北市勞工保險及就業服務按月別.csv)

Usage:
  python3 scripts/load_labor_stats_tpe.py [--output /tmp/labor_stats_tpe.sql]
"""

import csv
import re
import os
import sys
import argparse
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "docs" / "assets"
DISPUTES_CSV = ASSETS_DIR / "勞資爭議統計依行業別區分(11503).csv"
INSURANCE_CSV = ASSETS_DIR / "臺北市勞工保險及就業服務按月別.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_int(s):
    """Strip commas and convert to int; return None if empty/non-numeric."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s == "" or s == "-":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def to_float(s):
    """Strip commas and convert to float; return None if empty/non-numeric."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s == "" or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sql_val(v):
    """Format a Python value as a SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, str):
        escaped = v.replace("'", "''")
        return f"'{escaped}'"
    return str(v)


def roc_year_month(s):
    """Parse '87年 1月' → '1998-01-01' (ISO date string)."""
    m = re.match(r"(\d+)年\s*(\d+)月", str(s))
    if not m:
        return None
    year = int(m.group(1)) + 1911
    month = int(m.group(2))
    return f"{year}-{month:02d}-01"


# ---------------------------------------------------------------------------
# CSV 1: 勞資爭議統計依行業別
# ---------------------------------------------------------------------------

def load_disputes():
    rows = []
    with open(DISPUTES_CSV, encoding="big5", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year_roc = to_int(row.get("年度", "").strip())
            if year_roc is None:
                continue
            year = year_roc + 1911
            period = row.get("統計月份", "").strip()
            industry = row.get("行業別", "").strip()
            case_count = to_int(row.get("案件數（數量）", ""))
            if not industry or case_count is None:
                continue
            rows.append((year, period, industry, case_count))
    return rows


def disputes_sql(rows):
    lines = []
    lines.append("-- labor_disputes_industry_tpe")
    lines.append("TRUNCATE TABLE labor_disputes_industry_tpe RESTART IDENTITY;")
    lines.append("INSERT INTO labor_disputes_industry_tpe")
    lines.append("  (year, period, industry, case_count)")
    lines.append("VALUES")
    value_parts = []
    for (year, period, industry, case_count) in rows:
        value_parts.append(
            f"  ({sql_val(year)}, {sql_val(period)}, {sql_val(industry)}, {sql_val(case_count)})"
        )
    lines.append(",\n".join(value_parts) + ";")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV 2: 勞工保險及就業服務按月別
# ---------------------------------------------------------------------------

INSURANCE_COL_MAP = {
    "統計期": "period_label",
    "勞工保險投保單位數[家]": "insured_units",
    "勞工保險投保人數[人]": "insured_persons",
    "勞工保險給付件數[件]": "benefit_cases",
    "勞工保險給付金額[千元]": "benefit_amount",
    "市府推介就業服務/新登記求職人數[人]": "new_seekers",
    "市府推介就業服務/新登記求才人數[人]": "new_openings",
    "市府推介就業服務/有效求職推介就業人數[人]": "placed_seekers",
    "市府推介就業服務/有效求才僱用人數[人]": "placed_openings",
    "市府推介就業服務/求職就業率[%]": "placement_rate",
    "市府推介就業服務/求才利用率[%]": "utilization_rate",
    "重大職業災害發生件數[件]": "accident_cases",
    "重大職業災害死亡人數[人]": "accident_deaths",
}

NUMERIC_COLS = {"placement_rate", "utilization_rate"}
BIGINT_COLS = {"benefit_amount"}


def load_insurance():
    rows = []
    with open(INSURANCE_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            period_label = row.get("統計期", "").strip()
            if not period_label:
                continue
            period_date = roc_year_month(period_label)
            if not period_date:
                continue

            rec = {
                "period_label": period_label,
                "period_date": period_date,
            }

            for csv_col, db_col in INSURANCE_COL_MAP.items():
                if db_col in ("period_label",):
                    continue
                raw = row.get(csv_col, "")
                if db_col in NUMERIC_COLS:
                    rec[db_col] = to_float(raw)
                else:
                    rec[db_col] = to_int(raw)

            rows.append(rec)
    return rows


def insurance_sql(rows):
    cols = [
        "period_label", "period_date",
        "insured_units", "insured_persons", "benefit_cases", "benefit_amount",
        "new_seekers", "new_openings", "placed_seekers", "placed_openings",
        "placement_rate", "utilization_rate",
        "accident_cases", "accident_deaths",
    ]
    lines = []
    lines.append("\n-- labor_insurance_monthly_tpe")
    lines.append("TRUNCATE TABLE labor_insurance_monthly_tpe RESTART IDENTITY;")
    lines.append("INSERT INTO labor_insurance_monthly_tpe")
    lines.append(f"  ({', '.join(cols)})")
    lines.append("VALUES")
    value_parts = []
    for rec in rows:
        vals = []
        for c in cols:
            v = rec.get(c)
            if c == "period_date" and v is not None:
                vals.append(f"'{v}'::date")
            else:
                vals.append(sql_val(v))
        value_parts.append(f"  ({', '.join(vals)})")
    lines.append(",\n".join(value_parts) + ";")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate SQL for TPE labor stats")
    parser.add_argument(
        "--output", default="/tmp/labor_stats_tpe.sql",
        help="Output SQL file path (default: /tmp/labor_stats_tpe.sql)"
    )
    args = parser.parse_args()

    print("Reading disputes CSV...")
    dispute_rows = load_disputes()
    print(f"  {len(dispute_rows)} dispute rows loaded")

    print("Reading insurance CSV...")
    insurance_rows = load_insurance()
    print(f"  {len(insurance_rows)} insurance rows loaded")

    print(f"Writing SQL to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("-- TPE labor statistics SQL\n")
        f.write("-- Generated by scripts/load_labor_stats_tpe.py\n\n")
        f.write(disputes_sql(dispute_rows))
        f.write("\n")
        f.write(insurance_sql(insurance_rows))
        f.write("\n")

    print("Done.")

    # Summary
    years = sorted(set(r[0] for r in dispute_rows))
    print(f"\nDisputes: {len(dispute_rows)} rows, years {years[0]}~{years[-1]}")
    dates = sorted(r["period_date"] for r in insurance_rows)
    print(f"Insurance: {len(insurance_rows)} rows, {dates[0]} to {dates[-1]}")


if __name__ == "__main__":
    main()
