#!/usr/bin/env python3
"""
Load 食藥署食品查核及檢驗資訊平台 2026-05-02 台北/新北 稽查紀錄 → food_risk_inspection.

Sources (CSV only — no HTTP):
  - docs/assets/食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場.csv
  - docs/assets/食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者.csv

兩份 CSV 已由 scripts/food_safety/main.py 預處理：
  - 法條欄位標準化 (violated_law_standardized)
  - 危害分級 (hazard_level: critical/high/medium/low/info)
  - 個人農場 vs 商業業者 分流（依檔名）

本 loader 為純 psycopg2 standalone 腳本（與 _食安雷達_ 其他 loader 一致），
不依賴 Airflow runtime。重複執行安全（TRUNCATE + 重灌）。
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
ASSETS    = REPO_ROOT / "docs" / "assets"

# (business_type, csv_path)
SOURCES = [
    ("個人農場", ASSETS / "食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場.csv"),
    ("商業業者", ASSETS / "食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者.csv"),
]

INSERT_SQL = """
INSERT INTO food_risk_inspection (
    source_id, business_type, business_name, address, city, district,
    product_name, inspection_date, inspection_item, inspection_result,
    violated_law_raw, fine_amount, note,
    violated_law_standardized, hazard_level, hazard_basis
) VALUES %s
"""


def parse_roc_date(text):
    """民國日期 (e.g. '110/11/2') → datetime.date；無效回傳 None。"""
    s = str(text or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d+)/(\d+)/(\d+)$", s)
    if not m:
        return None
    try:
        roc_y, mo, d = (int(g) for g in m.groups())
        return date(roc_y + 1911, mo, d)
    except (ValueError, OverflowError):
        return None


def num_int(s):
    v = str(s or "").strip().replace(",", "")
    if v in ("", "-", "—"):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def num_decimal(s):
    v = str(s or "").strip().replace(",", "")
    if v in ("", "-", "—"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def derive_city_district(address: str):
    """從地址前 6 字抽出 (city, district)。
    main.py 已先把 '台北市' 統一成 '臺北市'，但 raw CSV 部分列仍為 '台北市'，
    所以此處再過一次。"""
    a = (address or "").strip().replace("台北市", "臺北市")
    head3 = a[:3]
    if head3 not in ("臺北市", "新北市"):
        return None, None
    return head3, a[3:6] or None


def parse_csv(path: Path, business_type: str):
    """讀單份 CSV → list[tuple] for execute_values."""
    if not path.exists():
        sys.stderr.write(f"❌ missing CSV: {path}\n")
        sys.exit(1)
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            address = (r.get("業者地址") or "").strip()
            city, district = derive_city_district(address)
            out.append((
                num_int(r.get("項次")),
                business_type,
                (r.get("業者名稱(市招)") or "").strip() or None,
                address or None,
                city,
                district,
                (r.get("產品名稱") or "").strip() or None,
                parse_roc_date(r.get("稽查日期")),
                (r.get("稽查/檢驗項目") or "").strip() or None,
                (r.get("稽查/檢驗結果") or "").strip() or None,
                (r.get("違反之食安法條及相關法") or "").strip() or None,
                num_decimal(r.get("裁罰金額")),
                (r.get("備註") or "").strip() or None,
                (r.get("違反之食安法條及相關法_標準化") or "").strip() or None,
                (r.get("危害等級") or "").strip() or None,
                (r.get("危害判斷依據") or "").strip() or None,
            ))
    return out


def main():
    rows = []
    for biz_type, path in SOURCES:
        sub = parse_csv(path, biz_type)
        rows.extend(sub)
        print(f"  · {biz_type}: {len(sub):,} rows from {path.name}")

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE food_risk_inspection RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, rows, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(rows):,} rows → food_risk_inspection")


if __name__ == "__main__":
    main()
