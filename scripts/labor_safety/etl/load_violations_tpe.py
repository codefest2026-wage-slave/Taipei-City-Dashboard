#!/usr/bin/env python3
"""
Load TPE labor violations into labor_violations_tpe.

Sources (CSV only — NO HTTP):
  1. 勞基法:  docs/assets/違法名單總表-CSV檔1150105勞基.csv (UTF-8 BOM)
  2. 性平法:  docs/assets/臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv (Big5)
  3. 職安法:  scripts/labor_safety/snapshots/tpe_occupational_safety_violations.csv (UTF-8)

Adapted from scripts/load_labor_violations_tpe.py (main worktree). Strips
all HTTP fetch logic; reads pre-snapshotted CSV instead. Writes inside one
TRUNCATE-then-INSERT transaction.
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs, REPO_ROOT  # noqa: E402

LABR_CSV     = REPO_ROOT / "docs/assets/違法名單總表-CSV檔1150105勞基.csv"
GENDER_CSV   = REPO_ROOT / "docs/assets/臺北市政府勞動局違反性別平等工作法事業單位及事業主公布總表【公告月份：11504】.csv"
SAFETY_CSV   = Path(__file__).resolve().parent.parent / "snapshots/tpe_occupational_safety_violations.csv"

INSERT_SQL = """
INSERT INTO labor_violations_tpe (
    announcement_date, penalty_date, doc_no, company_name,
    principal, law_category, law_article, violation_content, fine_amount
) VALUES %s
"""


# ── helpers ──────────────────────────────────────────────────────────────

def parse_fine(v):
    digits = re.sub(r"[^\d]", "", str(v or ""))
    return int(digits) if digits else None


def roc_yyymmdd(s):
    """Convert ROC YYYMMDD digits to ISO date string, or None."""
    s = re.sub(r"[^\d]", "", str(s or ""))
    if len(s) < 7:
        return None
    try:
        return f"{int(s[:3]) + 1911}-{s[3:5]}-{s[5:7]}"
    except ValueError:
        return None


def clean(v):
    s = str(v or "").strip()
    return s or None


# ── source 1: 勞基法 (UTF-8 BOM) ─────────────────────────────────────────

def load_labor_csv():
    rows = []
    if not LABR_CSV.exists():
        print(f"  ⚠️  {LABR_CSV} missing — skipping 勞基法", file=sys.stderr)
        return rows
    with LABR_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            try:
                company = (rec.get("事業單位或事業主之名稱") or "").strip()
                if not company:
                    continue
                rows.append((
                    roc_yyymmdd(rec.get("公告日期")),
                    roc_yyymmdd(rec.get("處分日期")),
                    clean(rec.get("處分字號")),
                    company,
                    clean(rec.get("負責人姓名")),
                    "勞基法",
                    clean(rec.get("違反勞動基準法條款")),
                    clean(rec.get("違反法規內容")),
                    parse_fine(rec.get("罰鍰金額")),
                ))
            except Exception as e:
                print(f"  ⚠️  skip 勞基法 row: {e}", file=sys.stderr)
                continue
    print(f"  [勞基法] {len(rows):,} rows")
    return rows


# ── source 2: 性平法 (Big5) ──────────────────────────────────────────────

def find_clause_col(headers):
    for i, h in enumerate(headers):
        if "條款" in h:
            return i
    return None


def load_gender_csv():
    rows = []
    if not GENDER_CSV.exists():
        print(f"  ⚠️  {GENDER_CSV} missing — skipping 性平法", file=sys.stderr)
        return rows
    with GENDER_CSV.open(encoding="big5", errors="replace", newline="") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return rows
        clause_idx = find_clause_col(headers)

        def col(rec, name):
            try:
                return rec[headers.index(name)]
            except (ValueError, IndexError):
                return ""

        for rec in reader:
            try:
                while len(rec) < len(headers):
                    rec.append("")
                company = col(rec, "事業單位名稱/自然人姓名").strip()
                if not company or company == "無":
                    continue
                law_article = rec[clause_idx].strip() if clause_idx is not None else ""
                rows.append((
                    roc_yyymmdd(col(rec, "公告日期")),
                    roc_yyymmdd(col(rec, "處分日期")),
                    clean(col(rec, "處分字號")),
                    company,
                    clean(col(rec, "事業單位代表人")),
                    "性平法",
                    clean(law_article),
                    clean(col(rec, "違反法規內容")),
                    parse_fine(col(rec, "罰鍰金額")),
                ))
            except Exception as e:
                print(f"  ⚠️  skip 性平法 row: {e}", file=sys.stderr)
                continue
    print(f"  [性平法] {len(rows):,} rows")
    return rows


# ── source 3: 職安法 snapshot ────────────────────────────────────────────

def load_safety_snapshot():
    rows = []
    if not SAFETY_CSV.exists():
        print(f"  ❌ {SAFETY_CSV} missing — run snapshot_apis.py first", file=sys.stderr)
        sys.exit(1)
    with SAFETY_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            try:
                company = (rec.get("事業單位或事業組織名稱") or "").strip()
                if not company:
                    continue
                rows.append((
                    roc_yyymmdd(rec.get("公告日期")),
                    roc_yyymmdd(rec.get("處分日期")),
                    clean(rec.get("處分字號")),
                    company,
                    clean(rec.get("負責人姓名")),
                    "職安法",
                    clean(rec.get("違反職業安全衛生法條款")),
                    clean(rec.get("違反法規內容")),
                    None,  # 職安法 has no fine field
                ))
            except Exception as e:
                print(f"  ⚠️  skip 職安法 row: {e}", file=sys.stderr)
                continue
    print(f"  [職安法] {len(rows):,} rows")
    return rows


# ── main ─────────────────────────────────────────────────────────────────

def main():
    print("=== load_violations_tpe ===")
    rows = []
    rows += load_labor_csv()
    rows += load_gender_csv()
    rows += load_safety_snapshot()

    if not rows:
        print("❌ no rows to insert", file=sys.stderr)
        sys.exit(1)

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE labor_violations_tpe RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, rows, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(rows):,} rows → labor_violations_tpe")


if __name__ == "__main__":
    main()
