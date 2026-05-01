#!/usr/bin/env python3
"""
Load major workplace disasters (重大職災) into labor_disasters_tpe and
labor_disasters_ntpc.

Sources (CSV only — NO HTTP):
  - TPE:  scripts/labor_safety/snapshots/tpe_major_disasters.csv
            (GPS-point records, ROC text date '113年12月31日')
  - NTPC: scripts/labor_safety/snapshots/ntpc_major_disasters.csv
            (district-level, ROC slash date '108/02/01')

Adapted from scripts/load_labor_disasters.py (main worktree).
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
TPE_CSV  = SNAPSHOTS / "tpe_major_disasters.csv"
NTPC_CSV = SNAPSHOTS / "ntpc_major_disasters.csv"

INSERT_TPE = """
INSERT INTO labor_disasters_tpe (
    incident_date, company_name, address, disaster_type,
    deaths, injuries, lng, lat
) VALUES %s
"""

INSERT_NTPC = """
INSERT INTO labor_disasters_ntpc (
    incident_date, disaster_type, deaths, injuries, district, industry
) VALUES %s
"""


def roc_text_date(s):
    """'113年12月31日' → '2024-12-31'."""
    m = re.match(r"(\d+)年(\d+)月(\d+)日", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def roc_slash_date(s):
    """'108/02/01' → '2019-02-01'."""
    m = re.match(r"(\d+)/(\d+)/(\d+)", str(s or ""))
    if not m:
        return None
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def parse_casualties(s):
    m = re.match(r"(\d+)死(\d+)傷", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def to_int(v, default=0):
    try:
        return int(v) if v not in (None, "") else default
    except (ValueError, TypeError):
        return default


def to_float(v):
    try:
        f = float(v) if v not in (None, "") else None
        return f
    except (ValueError, TypeError):
        return None


def load_tpe():
    rows = []
    skipped = 0
    if not TPE_CSV.exists():
        print(f"  ❌ {TPE_CSV} missing — run snapshot_apis.py first", file=sys.stderr)
        sys.exit(1)
    with TPE_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                lng = to_float(r.get("經度"))
                lat = to_float(r.get("緯度"))
                if not lng or not lat:
                    skipped += 1
                    continue
                rows.append((
                    roc_text_date(r.get("發生日期")),
                    (r.get("事業單位名稱") or "").strip() or None,
                    (r.get("地址") or "").strip() or None,
                    (r.get("災害類型") or "").strip() or None,
                    to_int(r.get("死亡人數"), 0),
                    to_int(r.get("受傷人數"), 0),
                    lng,
                    lat,
                ))
            except Exception as e:
                print(f"  ⚠️  skip TPE row: {e}", file=sys.stderr)
                skipped += 1
                continue
    print(f"  [TPE] {len(rows):,} rows ({skipped} skipped — missing coords)")
    return rows


def load_ntpc():
    rows = []
    if not NTPC_CSV.exists():
        print(f"  ❌ {NTPC_CSV} missing — run snapshot_apis.py first", file=sys.stderr)
        sys.exit(1)
    with NTPC_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                deaths, injuries = parse_casualties(r.get("disaster"))
                rows.append((
                    roc_slash_date(r.get("date")),
                    (r.get("type") or "").strip() or None,
                    deaths,
                    injuries,
                    (r.get("location") or "").strip() or None,
                    (r.get("category") or "").strip() or None,
                ))
            except Exception as e:
                print(f"  ⚠️  skip NTPC row: {e}", file=sys.stderr)
                continue
    print(f"  [NTPC] {len(rows):,} rows")
    return rows


def main():
    print("=== load_disasters ===")
    tpe = load_tpe()
    ntpc = load_ntpc()

    if not tpe and not ntpc:
        print("❌ no rows to insert", file=sys.stderr)
        sys.exit(1)

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE labor_disasters_tpe RESTART IDENTITY")
        if tpe:
            execute_values(cur, INSERT_TPE, tpe, page_size=500)
        cur.execute("TRUNCATE labor_disasters_ntpc RESTART IDENTITY")
        if ntpc:
            execute_values(cur, INSERT_NTPC, ntpc, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(tpe):,} rows → labor_disasters_tpe")
    print(f"✅ {len(ntpc):,} rows → labor_disasters_ntpc")


if __name__ == "__main__":
    main()
