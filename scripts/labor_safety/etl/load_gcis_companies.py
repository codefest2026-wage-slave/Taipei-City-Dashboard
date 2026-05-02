#!/usr/bin/env python3
"""Load GCIS company registration data into the dashboard DB.

Reads:
  docs/assets/L-01-1/台北市公司登記資料-{業別}.csv  ×11
  docs/assets/L-01-1/新北市公司登記資料-{業別}.csv  ×11
  docs/assets/L-01-1/industrial.xml  (主計總處 行業分類)

Writes (TRUNCATE-then-INSERT, single transaction per table):
  gcis_companies_tpe  / gcis_companies_ntpc  (industry classification + capital)
  industry_codes  (joined by build_recheck_priority.sql for industry_name)
"""
import csv
import glob
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from _db import db_kwargs

REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = REPO_ROOT / "docs" / "assets" / "L-01-1"
INDUSTRIAL_XML = ASSETS_DIR / "industrial.xml"


def _roc_to_iso(roc):
    """民國 '1131022' / '0991231' / '991231' → '2024-10-22' / None."""
    if not roc:
        return None
    s = str(roc).strip()
    if not s.isdigit() or len(s) < 6:
        return None
    if len(s) == 6:
        s = "0" + s
    if len(s) != 7:
        return None
    try:
        y = int(s[:3]) + 1911
        m = int(s[3:5])
        d = int(s[5:7])
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return None


def _first_industry_code(raw):
    """'011999,639099,723000,' → '0119' (first 4 digits of primary code)."""
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        return None
    digits = re.sub(r"\D", "", parts[0])
    return digits[:4] if len(digits) >= 4 else (digits or None)


def _parse_industrial_xml(path):
    rows = []
    tree = ET.parse(path)
    for row in tree.getroot().findall("Row"):
        code = row.findtext("行業類別", "").strip()
        name = row.findtext("行業名稱", "").strip()
        if code and name:
            digits = re.sub(r"\D", "", code)
            if not digits and len(code) == 1 and code.isalpha():
                level = 1
            else:
                level = len(digits)
            rows.append((code, name, level))
    return rows


def _parse_company_csv(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            tax_id = (r.get("統一編號") or "").strip()
            name = (r.get("公司名稱") or "").strip()
            if not tax_id or not name:
                continue
            cap_raw = (r.get("資本總額") or "").strip()
            capital = int(cap_raw) if cap_raw.isdigit() else None
            yield (
                tax_id,
                name,
                (r.get("公司地址") or "").strip() or None,
                _first_industry_code(r.get("行業代號(財政資訊中心匯入)")
                                     or r.get("行業代號（財政資訊中心匯入）", "")),
                capital,
                _roc_to_iso(r.get("核准設立日期", "")),
            )


def _load_city(cur, table, prefix):
    cur.execute(f"TRUNCATE {table} RESTART IDENTITY")
    seen = set()
    rows = []
    for path in sorted(ASSETS_DIR.glob(f"{prefix}公司登記資料-*.csv")):
        n = 0
        for rec in _parse_company_csv(path):
            tid = rec[0]
            if tid in seen:
                continue
            seen.add(tid)
            rows.append(rec)
            n += 1
        print(f"  {path.name}: {n}", file=sys.stderr)
    execute_values(
        cur,
        f"INSERT INTO {table} (tax_id, company_name, address, industry_code, capital, established_date) VALUES %s",
        rows,
        page_size=1000,
    )
    print(f"✅ {len(rows):,} rows → {table}")


def main():
    if not ASSETS_DIR.is_dir():
        sys.exit(f"❌ missing dir: {ASSETS_DIR}")
    if not INDUSTRIAL_XML.is_file():
        sys.exit(f"❌ missing file: {INDUSTRIAL_XML}")

    industry_rows = _parse_industrial_xml(INDUSTRIAL_XML)
    print(f"  industrial.xml: {len(industry_rows)} codes", file=sys.stderr)

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE industry_codes")
        execute_values(
            cur,
            "INSERT INTO industry_codes (code, name, level) VALUES %s ON CONFLICT (code) DO NOTHING",
            industry_rows,
            page_size=500,
        )
        print(f"✅ {len(industry_rows):,} rows → industry_codes")

        _load_city(cur, "gcis_companies_tpe", "台北市")
        _load_city(cur, "gcis_companies_ntpc", "新北市")
        cur.execute("COMMIT")


if __name__ == "__main__":
    main()
