#!/usr/bin/env python3
"""
Load NTPC labor violations into labor_violations_ntpc.

Sources (CSV only — NO HTTP):
  1. 勞基法:  scripts/labor_safety/snapshots/ntpc_labor_violations.csv
  2. 性平法:  scripts/labor_safety/snapshots/ntpc_gender_equality_violations.csv
  3. 職安法:  scripts/labor_safety/snapshots/ntpc_occupational_safety_violations.csv

Adapted from scripts/load_labor_violations_ntpc.py (main worktree). All
three NTPC datasets share the same schema (principal/date/law/name/id/
lawcontent/docno/amt_dollartwd). Date values are already ISO YYYY-MM-DD.
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

SNAPSHOTS = Path(__file__).resolve().parent.parent / "snapshots"

DATASETS = [
    ("勞基法", SNAPSHOTS / "ntpc_labor_violations.csv"),
    ("性平法", SNAPSHOTS / "ntpc_gender_equality_violations.csv"),
    ("職安法", SNAPSHOTS / "ntpc_occupational_safety_violations.csv"),
]

INSERT_SQL = """
INSERT INTO labor_violations_ntpc (
    penalty_date, law_category, law_article, company_name,
    principal, tax_id, violation_content, doc_no, fine_amount
) VALUES %s
"""


def parse_fine(v):
    digits = re.sub(r"[^\d]", "", str(v or ""))
    return int(digits) if digits else None


def parse_iso_date(s):
    s = (str(s or "")).strip()
    if not s or not re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return None
    return s[:10]


def clean(v):
    s = str(v or "").strip()
    return s or None


def load_csv(category, path):
    rows = []
    if not path.exists():
        print(f"  ❌ {path} missing — run snapshot_apis.py first", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            try:
                company = (rec.get("name") or "").strip()
                if not company:
                    continue
                rows.append((
                    parse_iso_date(rec.get("date")),
                    category,
                    clean(rec.get("law")),
                    company,
                    clean(rec.get("principal")),
                    clean(rec.get("id")),
                    clean(rec.get("lawcontent")),
                    clean(rec.get("docno")),
                    parse_fine(rec.get("amt_dollartwd")),
                ))
            except Exception as e:
                print(f"  ⚠️  skip {category} row: {e}", file=sys.stderr)
                continue
    print(f"  [{category}] {len(rows):,} rows")
    return rows


def main():
    print("=== load_violations_ntpc ===")
    rows = []
    for category, path in DATASETS:
        rows += load_csv(category, path)

    if not rows:
        print("❌ no rows to insert", file=sys.stderr)
        sys.exit(1)

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE labor_violations_ntpc RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, rows, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(rows):,} rows → labor_violations_ntpc")


if __name__ == "__main__":
    main()
