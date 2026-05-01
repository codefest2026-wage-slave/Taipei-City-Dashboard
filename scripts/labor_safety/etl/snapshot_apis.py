#!/usr/bin/env python3
"""
One-shot snapshot tool: fetch 6 API endpoints and write CSV files into
scripts/labor_safety/snapshots/. Re-run this only when refreshing data;
the regular apply.sh does NOT call this — it only reads committed CSVs.

Endpoints (port from main worktree's load_labor_violations_*.py and
load_labor_disasters.py):

  data.taipei (paginated by limit/offset)
    - tpe_occupational_safety_violations.csv  RID 90d05db5…
    - tpe_major_disasters.csv                 RID ab4ddbe2…

  data.ntpc (paginated by size/page)
    - ntpc_labor_violations.csv               UUID a3408b16…  (~14,155)
    - ntpc_gender_equality_violations.csv     UUID d7b245c0…  (~47)
    - ntpc_occupational_safety_violations.csv UUID 8ec84245…  (~4,148)
    - ntpc_major_disasters.csv                UUID 80743c0e…  (~206)

Usage:
    python3 scripts/labor_safety/etl/snapshot_apis.py
"""
import csv
import sys
import time
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parent.parent / "snapshots"

PAGE_SIZE = 1000
SLEEP_BETWEEN_SOURCES = 1.0  # seconds, to avoid rate-limiting


def fetch_data_taipei(rid):
    """Paginate https://data.taipei/api/v1/dataset/<rid>?scope=resourceAquire."""
    url = f"https://data.taipei/api/v1/dataset/{rid}"
    rows = []
    offset = 0
    while True:
        resp = requests.get(
            url,
            params={"scope": "resourceAquire", "limit": PAGE_SIZE, "offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json().get("result", {}).get("results", []) or []
        if not batch:
            break
        rows.extend(batch)
        print(f"  data.taipei {rid[:8]}… offset={offset}: +{len(batch)} (total {len(rows)})")
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def fetch_data_ntpc(uuid):
    """Paginate https://data.ntpc.gov.tw/api/datasets/<uuid>/json?size&page."""
    url = f"https://data.ntpc.gov.tw/api/datasets/{uuid}/json"
    rows = []
    page = 0
    while True:
        resp = requests.get(
            url,
            params={"size": PAGE_SIZE, "page": page},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json() or []
        if not batch:
            break
        rows.extend(batch)
        print(f"  data.ntpc {uuid[:8]}… page={page}: +{len(batch)} (total {len(rows)})")
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return rows


# Each entry: (filename, fetcher, id, expected-range-tuple-or-None)
SOURCES = [
    {
        "filename": "tpe_occupational_safety_violations.csv",
        "fetch":    fetch_data_taipei,
        "id":       "90d05db5-d46f-4900-a450-b284b0f20fb9",
        "expect":   None,  # hundreds-to-thousands per plan
    },
    {
        "filename": "tpe_major_disasters.csv",
        "fetch":    fetch_data_taipei,
        "id":       "ab4ddbe2-90f5-49a6-a7ad-45e5b6d14871",
        "expect":   None,  # hundreds per plan
    },
    {
        "filename": "ntpc_labor_violations.csv",
        "fetch":    fetch_data_ntpc,
        "id":       "a3408b16-7b28-4fa5-9834-d147aae909bf",
        "expect":   (13447, 14862),  # ~14,155 ±5%
    },
    {
        "filename": "ntpc_gender_equality_violations.csv",
        "fetch":    fetch_data_ntpc,
        "id":       "d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4",
        "expect":   (44, 50),  # ~47 ±5%
    },
    {
        "filename": "ntpc_occupational_safety_violations.csv",
        "fetch":    fetch_data_ntpc,
        "id":       "8ec84245-450b-45df-9bc5-510ab6e02e73",
        "expect":   (3940, 4356),  # ~4,148 ±5%
    },
    {
        "filename": "ntpc_major_disasters.csv",
        "fetch":    fetch_data_ntpc,
        "id":       "80743c0e-b7e7-4d4a-825b-df354a542f65",
        "expect":   (195, 217),  # ~206 ±5%
    },
]


def union_keys(rows):
    """Return ordered list of all keys that appear in any row."""
    seen = []
    seen_set = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_set:
                seen.append(k)
                seen_set.add(k)
    return seen


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"▶ writing snapshots to {OUT_DIR}\n")

    summary = []
    for i, src in enumerate(SOURCES):
        if i > 0:
            time.sleep(SLEEP_BETWEEN_SOURCES)
        print(f"[{i+1}/{len(SOURCES)}] {src['filename']}")
        try:
            rows = src["fetch"](src["id"])
        except requests.RequestException as e:
            print(f"❌ {src['filename']}: HTTP error — {e}", file=sys.stderr)
            sys.exit(1)

        if not rows:
            print(f"❌ {src['filename']}: 0 rows from API — abort", file=sys.stderr)
            sys.exit(1)

        if src["expect"] is not None:
            lo, hi = src["expect"]
            if not (lo <= len(rows) <= hi):
                print(
                    f"❌ {src['filename']}: {len(rows)} rows outside expected "
                    f"[{lo},{hi}] — hard fail",
                    file=sys.stderr,
                )
                sys.exit(1)

        out = OUT_DIR / src["filename"]
        fieldnames = union_keys(rows)
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"✅ {src['filename']}: {len(rows):,} rows\n")
        summary.append((src["filename"], len(rows)))

    print("── summary ──")
    for name, n in summary:
        print(f"  {name}: {n:,} rows")


if __name__ == "__main__":
    main()
