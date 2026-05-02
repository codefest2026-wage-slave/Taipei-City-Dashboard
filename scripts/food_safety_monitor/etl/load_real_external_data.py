#!/usr/bin/env python3
"""ETL: real external (校外) food-safety data — businesses with any FAIL
inspection record from food_safety_inspection_metrotaipei.

Source:
  DB.dashboard.food_safety_inspection_metrotaipei (17,344 commercial /
  individual-farm inspection records, 2020-06 ~ 2026-02, 雙北).

Target:
  Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/
    restaurants.geojson         — one feature per (business, address) with FAIL
    restaurant_inspections.json — full inspection history keyed by business id
    district_heatmap.geojson    — district choropleth (fail_count per district)
  Taipei-City-Dashboard-FE/public/mapData/
    fsm_restaurants.geojson, fsm_district_heat.geojson (Mapbox source mirrors)

Identity:
  business id = sha1(business_name + address)[:12] — stable + deterministic
  schools/suppliers from 校內 ETL untouched.

Aggregation per business (only businesses that have ≥1 FAIL kept):
  - hazard_level: max severity across ALL records (Critical > High > Medium >
    Low > Info) — represents worst-recorded risk
  - fail_count: count where inspection_result IN ('不合格','不符合規定')
  - total_inspections, latest_fail_date, latest_inspection_date
  - history[]: full chronological list (date, result, hazard, issue, fine)

Coloring rule:
  hazard_level → Mapbox circle-color: critical/high → red, medium → amber,
  low/info → blue. (Wired in the BE migration paint expression.)

Geocoding: ArcGIS World GeocodeServer + persistent JSON cache (shared with
the 校內 ETL — same Geocoder class / cache file).

Re-run: python3 scripts/food_safety_monitor/etl/load_real_external_data.py
"""
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2

# Reuse Geocoder + helpers from the 校內 ETL
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[3]
SCHOOL_ETL = ROOT / "scripts/food_safety_monitor/etl/load_real_school_data.py"
spec = importlib.util.spec_from_file_location("school_etl", SCHOOL_ETL)
school_etl = importlib.util.module_from_spec(spec)
sys.modules["school_etl"] = school_etl
spec.loader.exec_module(school_etl)
Geocoder = school_etl.Geocoder
get_db = school_etl.get_db
address_district = school_etl.address_district
polygon_centroid = school_etl.polygon_centroid

DST_MOCK = ROOT / "Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor"
DST_MAP = ROOT / "Taipei-City-Dashboard-FE/public/mapData"
TOWN_GEOJSON = DST_MAP / "metrotaipei_town.geojson"

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def biz_id(name, address):
    return hashlib.sha1(f"{name}|{address}".encode("utf-8")).hexdigest()[:12]


def normalize_severity(level):
    if not level:
        return "info"
    s = level.strip().lower()
    return s if s in SEVERITY_RANK else "info"


def main():
    print("connecting to DB...")
    conn = get_db()
    cur = conn.cursor()

    # All inspection records for businesses that have at least one FAIL.
    # Subquery: ids of (name, address) pairs with any FAIL → join to get all
    # records for those businesses (FAIL + PASS).
    cur.execute("""
        WITH bad AS (
            SELECT DISTINCT business_name, address
            FROM food_safety_inspection_metrotaipei
            WHERE inspection_result IN ('不合格','不符合規定')
              AND business_name IS NOT NULL
              AND address IS NOT NULL
        )
        SELECT i.business_name, i.address, i.city, i.district, i.business_type,
               i.inspection_date, i.inspection_result, i.hazard_level,
               i.fine_amount, i.violated_law_standardized, i.note,
               i.inspection_item, i.product_name
        FROM food_safety_inspection_metrotaipei i
        JOIN bad b ON i.business_name = b.business_name
                  AND i.address = b.address
        WHERE i.inspection_date IS NOT NULL
        ORDER BY i.inspection_date DESC
    """)
    rows = cur.fetchall()
    print(f"  rows fetched: {len(rows):,}")
    cur.close()
    conn.close()

    # ── Aggregate per business ──────────────────────────────
    biz = {}  # bid → {name, address, city, district, business_type, history[], ...}
    for r in rows:
        (name, address, city, district, btype, date, result, level,
         fine, law_std, note, item, product) = r
        bid = biz_id(name, address)
        agg = biz.get(bid)
        if agg is None:
            agg = {
                "id": bid,
                "name": name,
                "address": address,
                "city": city,
                "district": district,
                "business_type": btype,
                "history": [],
                "_severity_max": "info",
                "fail_count": 0,
                "latest_fail_date": None,
            }
            biz[bid] = agg
        sev = normalize_severity(level)
        if SEVERITY_RANK[sev] > SEVERITY_RANK[agg["_severity_max"]]:
            agg["_severity_max"] = sev
        is_fail = result in ("不合格", "不符合規定")
        if is_fail:
            agg["fail_count"] += 1
            d = date.strftime("%Y/%m/%d")
            if agg["latest_fail_date"] is None or d > agg["latest_fail_date"]:
                agg["latest_fail_date"] = d
        agg["history"].append({
            "date": date.strftime("%Y/%m/%d"),
            "status": "FAIL" if is_fail else "PASS",
            "severity": sev.capitalize(),
            "issue": (law_std or note or item or product or result or "").strip()[:120],
            "fine_amount": float(fine) if fine is not None else None,
            "result_raw": result,
            "hazard_level": sev,
        })
    print(f"  distinct businesses (with ≥1 FAIL): {len(biz):,}")

    # ── Geocode each business ────────────────────────────────
    print("  geocoding addresses...")
    geocoder = Geocoder()
    fallback_centroids = district_centroids()
    features = []
    inspection_records = {}
    for i, (bid, b) in enumerate(biz.items()):
        loc = geocoder.lookup(b["address"]) if b["address"] else None
        if loc:
            coord = list(loc)
        else:
            cd = (b["city"] or "臺北市", b["district"] or "中正區")
            cx, cy = fallback_centroids.get(cd, (121.50, 25.04))
            coord = [cx, cy]
        sev = b["_severity_max"]
        latest_insp = max((h["date"] for h in b["history"]), default=None)
        features.append({
            "type": "Feature",
            "properties": {
                "id": bid,
                "name": b["name"],
                "address": b["address"],
                "city": b["city"],
                "district": b["district"],
                "business_type": b["business_type"],
                "hazard_level": sev,
                "fail_count": b["fail_count"],
                "total_inspections": len(b["history"]),
                "latest_fail_date": b["latest_fail_date"],
                "latest_inspection_date": latest_insp,
                "geocoded": loc is not None,
            },
            "geometry": {"type": "Point", "coordinates": coord},
        })
        inspection_records[bid] = {
            "name": b["name"],
            "address": b["address"],
            "history": b["history"],
        }
        if (i + 1) % 100 == 0:
            geocoder.flush()
            print(f"    geocoded {i + 1}/{len(biz)} (api calls so far: {geocoder.calls})")
    geocoder.flush()
    print(f"  geocode summary: {sum(1 for v in geocoder.cache.values() if v)} hits / "
          f"{sum(1 for v in geocoder.cache.values() if v is None)} misses / "
          f"{geocoder.calls} new API calls")

    # ── District heatmap (fail_count per district) ───────────
    fail_per_district = Counter()
    for f in features:
        p = f["properties"]
        key = (p["city"], p["district"])
        fail_per_district[key] += p["fail_count"]
    max_fc = max(fail_per_district.values()) if fail_per_district else 1
    town = json.loads(TOWN_GEOJSON.read_text())
    heat_features = []
    for f in town["features"]:
        p = f["properties"]
        key = (p["PNAME"], p["TNAME"])
        fc = fail_per_district.get(key, 0)
        # Normalize 0..100 by linear scale (max_fc)
        density = round(fc / max_fc * 100) if max_fc else 0
        heat_features.append({
            "type": "Feature",
            "properties": {
                **p,
                "fail_count": fc,
                "density": density,
            },
            "geometry": f["geometry"],
        })
    heat_geo = {"type": "FeatureCollection", "features": heat_features}

    # ── Write outputs ────────────────────────────────────────
    rest_geo = {"type": "FeatureCollection", "features": features}
    DST_MOCK.mkdir(parents=True, exist_ok=True)

    for path in (DST_MOCK / "restaurants.geojson", DST_MAP / "fsm_restaurants.geojson"):
        path.write_text(json.dumps(rest_geo, ensure_ascii=False))
    (DST_MOCK / "restaurant_inspections.json").write_text(
        json.dumps(inspection_records, ensure_ascii=False)
    )
    for path in (DST_MOCK / "district_heatmap.geojson", DST_MAP / "fsm_district_heat.geojson"):
        path.write_text(json.dumps(heat_geo, ensure_ascii=False))

    sev_dist = Counter(f["properties"]["hazard_level"] for f in features)
    print()
    print(f"✅ Wrote restaurants={len(features)}, district heat features={len(heat_features)}")
    print(f"   max hazard distribution: {dict(sev_dist)}")
    print(f"   district fail_count peak: {max_fc} (max district)")


def district_centroids():
    geo = json.loads(TOWN_GEOJSON.read_text())
    out = {}
    for f in geo["features"]:
        p = f["properties"]
        c = polygon_centroid(f["geometry"]["coordinates"])
        if c:
            out[(p["PNAME"], p["TNAME"])] = c
    return out


if __name__ == "__main__":
    main()
