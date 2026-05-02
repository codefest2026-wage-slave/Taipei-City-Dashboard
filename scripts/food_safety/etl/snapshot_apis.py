#!/usr/bin/env python3
"""
One-shot snapshot tool: fetch NTPC food factory API and write CSV into
scripts/food_safety/snapshots/. Re-run only when refreshing data; the
regular apply.sh does NOT call this — it only reads committed CSVs.

Endpoint:
  https://data.ntpc.gov.tw/api/datasets/c51d5111-c300-44c9-b4f1-4b28b9929ca2/json
  Paginated by size+page, expected ~1232 rows.
"""
import csv
import sys
import time
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "snapshots"
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "ntpc_food_factory.csv"

UUID = "c51d5111-c300-44c9-b4f1-4b28b9929ca2"
PAGE_SIZE = 200


def fetch_all():
    url = f"https://data.ntpc.gov.tw/api/datasets/{UUID}/json"
    rows = []
    page = 0
    while True:
        resp = requests.get(url, params={"size": PAGE_SIZE, "page": page}, timeout=60)
        resp.raise_for_status()
        batch = resp.json() or []
        if not batch:
            break
        rows.extend(batch)
        print(f"  page {page}: {len(batch)} rows, total {len(rows)}")
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.5)
    return rows


def main():
    print(f"Fetching NTPC food factories (UUID {UUID}) …")
    rows = fetch_all()
    if not rows:
        print("ERROR: zero rows returned", file=sys.stderr)
        sys.exit(1)

    cols = sorted({k for r in rows for k in r.keys()})
    with open(OUT_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"✅ {len(rows)} rows → {OUT_FILE}")


if __name__ == "__main__":
    main()
