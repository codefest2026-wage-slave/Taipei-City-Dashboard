#!/usr/bin/env python3
"""
Load NTPC food factories into food_factory_ntpc.

Source (CSV only — NO HTTP):
  scripts/food_safety/snapshots/ntpc_food_factory.csv
  (regenerated via etl/snapshot_apis.py — NOT during apply)

Schema reference: WGS84 coords from `wgs84ax` (lng) / `wgs84ay` (lat),
district extracted from `address` field (新北市XX區...).
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent / "snapshots" / "ntpc_food_factory.csv"

INSERT_SQL = """
INSERT INTO food_factory_ntpc (name, address, tax_id, lng, lat, district) VALUES %s
"""


def main():
    out = []
    with open(CSV_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                lng = float(r.get("wgs84ax", 0))
                lat = float(r.get("wgs84ay", 0))
            except (ValueError, TypeError):
                continue
            if not (120 < lng < 122.5 and 24 < lat < 26):
                continue
            addr = r.get("address", "")
            m = re.search(r"新北市(\S+區)", addr)
            district = m.group(1) if m else ""
            out.append((
                r.get("organizer", r.get("name_ins", "")),
                addr,
                r.get("tax_id_number", ""),
                lng,
                lat,
                district,
            ))

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE food_factory_ntpc RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, out)
        cur.execute("COMMIT")
    print(f"✅ {len(out)} rows → food_factory_ntpc")


if __name__ == "__main__":
    main()
