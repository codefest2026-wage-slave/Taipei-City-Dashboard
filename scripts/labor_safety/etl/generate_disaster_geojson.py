#!/usr/bin/env python3
"""
Generate GeoJSON layers for the disaster map components from
labor_disasters_tpe (point features) and labor_disasters_ntpc
(district choropleth).

Outputs:
  - Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson
  - Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson

Adapted from scripts/generate_labor_disaster_geojson.py (main worktree).
Reads NTPC district polygons from metrotaipei_town.geojson (filtered by
PNAME='新北市') instead of disaster_shelter_ntpc.geojson, since the
latter is not present in this worktree.
"""
import json
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs, REPO_ROOT  # noqa: E402

MAP_DIR = REPO_ROOT / "Taipei-City-Dashboard-FE/public/mapData"
NTPC_POLY_SOURCE = MAP_DIR / "metrotaipei_town.geojson"
TPE_OUT  = MAP_DIR / "labor_disasters_tpe.geojson"
NTPC_OUT = MAP_DIR / "labor_disasters_ntpc.geojson"


def fetchall(sql):
    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def build_tpe():
    rows = fetchall("""
        SELECT lng, lat, incident_date, company_name, address,
               disaster_type, deaths, injuries
          FROM labor_disasters_tpe
         WHERE lng IS NOT NULL AND lat IS NOT NULL
         ORDER BY incident_date DESC NULLS LAST
    """)
    features = []
    for lng, lat, date, company, addr, dtype, deaths, injuries in rows:
        deaths   = int(deaths or 0)
        injuries = int(injuries or 0)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
            "properties": {
                "city": "taipei",
                "incident_date": date.isoformat() if date else None,
                "company_name":  company,
                "address":       addr,
                "disaster_type": dtype,
                "deaths":        deaths,
                "injuries":      injuries,
                "severity":      "fatal" if deaths > 0 else "injury",
            },
        })
    return features


def load_ntpc_polygons():
    """Return {district_name: geometry} for 新北市 from metrotaipei_town."""
    if not NTPC_POLY_SOURCE.exists():
        return {}
    src = json.loads(NTPC_POLY_SOURCE.read_text(encoding="utf-8"))
    out = {}
    for feat in src.get("features", []):
        props = feat.get("properties", {}) or {}
        if props.get("PNAME") != "新北市":
            continue
        name = (props.get("TNAME") or "").strip()
        if name and feat.get("geometry"):
            out[name] = feat["geometry"]
    return out


def build_ntpc():
    rows = fetchall("""
        SELECT district,
               COUNT(*)        AS incidents,
               SUM(deaths)     AS total_deaths,
               SUM(injuries)   AS total_injuries
          FROM labor_disasters_ntpc
         WHERE district IS NOT NULL AND district <> ''
         GROUP BY district
         ORDER BY incidents DESC
    """)
    polys = load_ntpc_polygons()

    features = []
    unmatched = []
    for district, incidents, deaths, injuries in rows:
        geom = polys.get(district) or polys.get(district + "區")
        if not geom:
            unmatched.append(district)
            continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "city":           "newtaipei",
                "district":       district,
                "incidents":      int(incidents or 0),
                "total_deaths":   int(deaths or 0),
                "total_injuries": int(injuries or 0),
            },
        })
    if unmatched:
        print(f"  ⚠️  no polygon for districts: {unmatched}", file=sys.stderr)
    return features


def write(path, features):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False, indent=2)


def main():
    print("=== generate_disaster_geojson ===")
    tpe  = build_tpe()
    write(TPE_OUT, tpe)
    print(f"✅ {len(tpe):,} features → {TPE_OUT.relative_to(REPO_ROOT)}")

    ntpc = build_ntpc()
    write(NTPC_OUT, ntpc)
    print(f"✅ {len(ntpc):,} features → {NTPC_OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
