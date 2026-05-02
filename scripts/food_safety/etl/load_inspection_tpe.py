#!/usr/bin/env python3
"""
Load TPE 20-year food inspection + testing statistics.

Sources (CSV only — NO HTTP):
  - docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv → food_inspection_tpe
  - docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv → food_testing_tpe

Both are ROC-year (e.g. '95年') keyed annual statistics from 臺北市衛生局.
Adapted from scripts/generate_food_safety_sql.py (parent worktree).
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS    = REPO_ROOT / "docs" / "assets"
INSP_CSV  = ASSETS / "臺北市食品衛生管理稽查工作-年度統計.csv"
TEST_CSV  = ASSETS / "臺北市食品衛生管理查驗工作-年度統計.csv"

INSP_INSERT = """
INSERT INTO food_inspection_tpe (
    year, total_inspections, restaurant_insp, drink_shop_insp,
    street_vendor_insp, market_insp, supermarket_insp, manufacturer_insp,
    total_noncompliance, restaurant_nc, drink_shop_nc, street_vendor_nc,
    market_nc, supermarket_nc, manufacturer_nc, food_poisoning_cases
) VALUES %s
"""

TEST_INSERT = """
INSERT INTO food_testing_tpe (
    year, total_tested, total_violations, violation_rate,
    viol_labeling, viol_ad, viol_additive, viol_container, viol_microbe,
    viol_mycotoxin, viol_vetdrug, viol_chemical, viol_composition, viol_other
) VALUES %s
"""


def parse_roc_year(text):
    m = re.match(r"(\d+)年", str(text or "").strip())
    if not m:
        return None
    return int(m.group(1)) + 1911


def num(s):
    try:
        v = str(s or "").strip().replace(",", "")
        if v in ("", "-", "—"):
            return None
        f = float(v)
        return int(f) if f == int(f) else f
    except (ValueError, AttributeError):
        return None


def load_inspection():
    with open(INSP_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        year = parse_roc_year(r.get("統計期"))
        if year is None or year < 2006:
            continue
        out.append((
            year,
            num(r.get("食品衛生管理稽查工作/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/餐飲店/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/冷飲店/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/飲食攤販/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/傳統市場/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/超級市場/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/製造廠商/稽查家次[家次]")),
            num(r.get("食品衛生管理稽查工作/不合格飭令改善家次[家次]")),
            num(r.get("食品衛生管理稽查工作/餐飲店/不合格飭令改善家次[家次]")),
            num(r.get("食品衛生管理稽查工作/冷飲店/不合格飭令改善家次[家次]")),
            num(r.get("食品衛生管理稽查工作/飲食攤販/不合格飭令改善家次[家次]")),
            num(r.get("食品衛生管理稽查工作/傳統市場/不合格飭令改善家次[家次]")),
            num(r.get("食品衛生管理稽查工作/超級市場/不合格飭令改善家次[家次]")),
            num(r.get("食品衛生管理稽查工作/製造廠商/不合格飭令改善家次[家次]")),
            num(r.get("食品中毒人數[人]")),
        ))
    return out


def load_testing():
    with open(TEST_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        year = parse_roc_year(r.get("統計期"))
        if year is None:
            continue
        out.append((
            year,
            num(r.get("查驗件數/總計[件]")),
            num(r.get("與規定不符件數/總計[件]")),
            num(r.get("不符規定比率[%]")),
            num(r.get("與規定不符件數按原因別/違規標示[件]")),
            num(r.get("與規定不符件數按原因別/違規廣告[件]")),
            num(r.get("與規定不符件數按原因別/食品添加物[件]")),
            num(r.get("與規定不符件數按原因別/食品器皿容器包裝檢驗[件]")),
            num(r.get("與規定不符件數按原因別/微生物[件]")),
            num(r.get("與規定不符件數按原因別/真菌毒素[件]")),
            num(r.get("與規定不符件數按原因別/動物用藥殘留[件]")),
            num(r.get("與規定不符件數按原因別/化學成分[件]")),
            num(r.get("與規定不符件數按原因別/成分分析[件]")),
            num(r.get(" 與規定不符件數按原因別/其他[件]",
                      r.get("與規定不符件數按原因別/其他[件]"))),
        ))
    return out


def main():
    insp = load_inspection()
    test = load_testing()
    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE food_inspection_tpe RESTART IDENTITY")
        execute_values(cur, INSP_INSERT, insp)
        cur.execute("TRUNCATE food_testing_tpe RESTART IDENTITY")
        execute_values(cur, TEST_INSERT, test)
        cur.execute("COMMIT")
    print(f"✅ {len(insp)} rows → food_inspection_tpe")
    print(f"✅ {len(test)} rows → food_testing_tpe")


if __name__ == "__main__":
    main()
