#!/usr/bin/env python3
"""Load 雙北食品查核及檢驗資訊平台 v2 snapshot into food_safety_inspection_metrotaipei.

Sources (CSV only — NO HTTP):
  - data/食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場_v2.csv  → business_type=個人農場
  - data/食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者_v2.csv  → business_type=商業業者

Idempotent: TRUNCATE then INSERT in a single transaction.
"""
import csv
import re
import sys
from datetime import date
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR  = REPO_ROOT / "data"

SOURCES = [
    ("個人農場", DATA_DIR / "食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場_v2.csv"),
    ("商業業者", DATA_DIR / "食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者_v2.csv"),
]

INSERT_SQL = """
INSERT INTO food_safety_inspection_metrotaipei (
    data_time, business_type, source_id, business_name, address, city, district,
    product_name, inspection_date, inspection_item, inspection_result,
    violated_law_raw, fine_amount, note, violated_law_standardized,
    hazard_level, hazard_basis
) VALUES %s
"""

ROC_DATE_RE = re.compile(r"^\s*(\d{2,3})/(\d{1,2})/(\d{1,2})\s*$")


def _strip(s):
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None


def _int(s):
    s = _strip(s)
    if s is None:
        return None
    try:
        return int(float(s.replace(",", "")))
    except ValueError:
        return None


def _num(s):
    s = _strip(s)
    if s is None:
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _roc_to_date(s):
    s = _strip(s)
    if s is None:
        return None
    m = ROC_DATE_RE.match(s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y + 1911, mo, d)
    except ValueError:
        return None


def _split_address(addr):
    """Return (normalized_addr, city, district) — accept 台北/臺北 variants."""
    if not addr:
        return None, None, None
    a = addr.replace("台北市", "臺北市")
    head3 = a[:3]
    if head3 not in ("臺北市", "新北市"):
        return a, None, None
    district = a[3:6] if len(a) >= 6 else None
    return a, head3, district


def load_rows(business_type: str, path: Path):
    if not path.exists():
        raise FileNotFoundError(f"missing source CSV: {path}")
    out = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            address, city, district = _split_address(_strip(r.get("業者地址")))
            out.append((
                None,                                        # data_time → DEFAULT NOW() via NULL? we set explicitly below
                business_type,
                _int(r.get("項次")),
                _strip(r.get("業者名稱(市招)")),
                address,
                city,
                district,
                _strip(r.get("產品名稱")),
                _roc_to_date(r.get("稽查日期")),
                _strip(r.get("稽查/檢驗項目")),
                _strip(r.get("稽查/檢驗結果")),
                _strip(r.get("違反之食安法條及相關法")),
                _num(r.get("裁罰金額")),
                _strip(r.get("備註")),
                _strip(r.get("違反之食安法條及相關法_標準化")),
                _strip(r.get("危害等級")),
                _strip(r.get("危害判斷依據")),
            ))
    return out


def main():
    rows = []
    for business_type, path in SOURCES:
        sub = load_rows(business_type, path)
        print(f"  {business_type:>4}: {len(sub):>6} rows  ({path.name})")
        rows.extend(sub)
    print(f"  total: {len(rows)} rows")

    # Stamp all rows with the same load timestamp (NOW() inside the txn)
    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE food_safety_inspection_metrotaipei")
        cur.execute("SELECT NOW()")
        now = cur.fetchone()[0]
        rows = [(now,) + r[1:] for r in rows]
        execute_values(cur, INSERT_SQL, rows, page_size=1000)
        cur.execute("COMMIT")

    print(f"✅ {len(rows)} rows → food_safety_inspection_metrotaipei")


if __name__ == "__main__":
    main()
