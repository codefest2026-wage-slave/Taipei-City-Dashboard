#!/usr/bin/env python3
"""
Load TPE certified restaurants into food_restaurant_tpe.

Source (CSV only — NO HTTP, geocoding strictly cache-only):
  docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv

Geocoding: read scripts/food_safety/etl/.geocode_cache.json (9,680 entries
pre-fetched). If address is not in cache, fall back to district centroid
with jitter (NEVER calls external API — labor-safety rule §3.2.3).
"""
import csv
import json
import random
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

REPO_ROOT  = Path(__file__).resolve().parents[3]
CSV_PATH   = REPO_ROOT / "docs" / "assets" / "114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv"
CACHE_PATH = Path(__file__).resolve().parent / ".geocode_cache.json"

# TPE district centroids keyed by 行政區域代碼
TPE_DISTRICT = {
    "63000010": (121.5771, 25.0504, "松山區"),
    "63000020": (121.5639, 25.0330, "信義區"),
    "63000030": (121.5432, 25.0260, "大安區"),
    "63000040": (121.5301, 25.0637, "中山區"),
    "63000050": (121.5186, 25.0432, "中正區"),
    "63000060": (121.5102, 25.0633, "大同區"),
    "63000070": (121.5002, 25.0347, "萬華區"),
    "63000080": (121.5706, 24.9892, "文山區"),
    "63000090": (121.6071, 25.0554, "南港區"),
    "63000100": (121.5878, 25.0831, "內湖區"),
    "63000110": (121.5261, 25.0924, "士林區"),
    "63000120": (121.5008, 25.1318, "北投區"),
}

INSERT_SQL = """
INSERT INTO food_restaurant_tpe (name, address, district, grade, lng, lat) VALUES %s
"""


def clean_addr(addr):
    addr = re.sub(r"\d+~?\d*[Ff樓].*$", "", str(addr or ""))
    addr = re.sub(r"[Bb]\d+.*$", "", addr)
    return addr.strip()


def main():
    random.seed(42)
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    out = []
    for r in rows:
        code = r.get("行政區域代碼", "")
        centroid = TPE_DISTRICT.get(code, (121.5654, 25.0330, "其他"))
        addr = r.get("地址", "")
        coords = cache.get(clean_addr(addr))
        if coords:
            lng, lat = coords[0], coords[1]
        else:
            lng = centroid[0] + random.uniform(-0.006, 0.006)
            lat = centroid[1] + random.uniform(-0.004, 0.004)
        out.append((
            r.get("業者名稱店名") or "",
            addr,
            centroid[2],
            r.get("評核結果") or "",
            round(lng, 6),
            round(lat, 6),
        ))

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE food_restaurant_tpe RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, out)
        cur.execute("COMMIT")
    print(f"✅ {len(out)} rows → food_restaurant_tpe")


if __name__ == "__main__":
    main()
