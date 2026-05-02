#!/usr/bin/env python3
"""
Generate FE map GeoJSON from food_restaurant_tpe + food_factory_ntpc tables.
Runs LAST in apply.sh (depends on tables being populated).

Outputs:
  Taipei-City-Dashboard-FE/public/mapData/food_restaurant_tpe.geojson
  Taipei-City-Dashboard-FE/public/mapData/food_factory_ntpc.geojson
"""
import json
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR   = REPO_ROOT / "Taipei-City-Dashboard-FE" / "public" / "mapData"


def fetch(query):
    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def to_feature_collection(rows, props_fn):
    feats = []
    for r in rows:
        if r["lng"] is None or r["lat"] is None:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(r["lng"], 6), round(r["lat"], 6)]},
            "properties": props_fn(r),
        })
    return {"type": "FeatureCollection", "features": feats}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    restaurants = fetch(
        "SELECT name, address, district, grade, lng, lat FROM food_restaurant_tpe"
    )
    rest_fc = to_feature_collection(restaurants, lambda r: {
        "name":     r["name"] or "",
        "grade":    r["grade"] or "",
        "address":  r["address"] or "",
        "district": r["district"] or "",
        "city":     "taipei",
    })
    rest_path = OUT_DIR / "food_restaurant_tpe.geojson"
    rest_path.write_text(json.dumps(rest_fc, ensure_ascii=False), encoding="utf-8")
    print(f"✅ {len(rest_fc['features'])} features → {rest_path.name}")

    factories = fetch(
        "SELECT name, address, district, lng, lat FROM food_factory_ntpc"
    )
    fact_fc = to_feature_collection(factories, lambda r: {
        "name":     r["name"] or "",
        "address":  r["address"] or "",
        "district": r["district"] or "",
        "city":     "newtaipei",
    })
    fact_path = OUT_DIR / "food_factory_ntpc.geojson"
    fact_path.write_text(json.dumps(fact_fc, ensure_ascii=False), encoding="utf-8")
    print(f"✅ {len(fact_fc['features'])} features → {fact_path.name}")


if __name__ == "__main__":
    main()
