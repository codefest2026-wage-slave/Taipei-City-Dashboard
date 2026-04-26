#!/usr/bin/env python3
"""Generate GeoJSON for labor disaster map layers from PostgreSQL."""

import json
import subprocess


def run_sql(sql):
    result = subprocess.run(
        ["docker", "exec", "postgres-data", "psql", "-U", "postgres",
         "-d", "dashboard", "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True
    )
    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def main():
    # TPE: point features with GPS
    tpe_rows = run_sql("""
        SELECT lng, lat, incident_date, company_name, address,
               disaster_type, deaths, injuries
        FROM labor_disasters_tpe
        WHERE lng IS NOT NULL AND lat IS NOT NULL
        ORDER BY incident_date DESC
    """)

    tpe_features = []
    for row in tpe_rows:
        if len(row) < 8:
            continue
        lng, lat, date, company, addr, dtype, deaths, injuries = row
        try:
            lng_f, lat_f = float(lng), float(lat)
        except ValueError:
            continue
        tpe_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng_f, lat_f]},
            "properties": {
                "city": "taipei",
                "incident_date": date,
                "company_name": company,
                "address": addr,
                "disaster_type": dtype,
                "deaths": int(deaths or 0),
                "injuries": int(injuries or 0),
                "severity": "fatal" if int(deaths or 0) > 0 else "injury"
            }
        })

    tpe_geojson = {"type": "FeatureCollection", "features": tpe_features}
    tpe_path = "Taipei-City-Dashboard-FE/public/mapData/labor_disasters_tpe.geojson"
    with open(tpe_path, "w", encoding="utf-8") as f:
        json.dump(tpe_geojson, f, ensure_ascii=False, indent=2)
    print(f"TPE disaster GeoJSON: {len(tpe_features)} features → {tpe_path}")

    # NTPC: aggregate by district
    ntpc_rows = run_sql("""
        SELECT district, COUNT(*) AS incidents,
               SUM(deaths) AS total_deaths,
               SUM(injuries) AS total_injuries
        FROM labor_disasters_ntpc
        WHERE district IS NOT NULL AND district != ''
        GROUP BY district
        ORDER BY incidents DESC
    """)

    ntpc_stats = {}
    for row in ntpc_rows:
        if len(row) < 4:
            continue
        district, incidents, deaths, injuries = row
        ntpc_stats[district] = {
            "incidents": int(incidents or 0),
            "total_deaths": int(deaths or 0),
            "total_injuries": int(injuries or 0),
        }

    print(f"NTPC districts with data: {list(ntpc_stats.keys())}")

    # Load existing NTPC district polygons from disaster_shelter_ntpc.geojson
    shelter_path = "Taipei-City-Dashboard-FE/public/mapData/disaster_shelter_ntpc.geojson"
    with open(shelter_path, encoding="utf-8") as f:
        shelter = json.load(f)

    # Build district -> polygon geometry map
    district_polys = {}
    for feat in shelter["features"]:
        props = feat.get("properties", {})
        # Try common district property names
        d = (props.get("district") or props.get("行政區") or
             props.get("District") or props.get("DISTRICT") or "").strip()
        if d and d not in district_polys and feat.get("geometry"):
            district_polys[d] = feat["geometry"]

    print(f"Available polygon districts: {sorted(district_polys.keys())[:10]}...")

    # Build NTPC GeoJSON: one feature per district with stats + polygon geometry
    ntpc_features = []
    unmatched = []
    for district, stats in ntpc_stats.items():
        geom = district_polys.get(district) or district_polys.get(district + "區")
        if not geom:
            unmatched.append(district)
            # Use a null geometry point as fallback — choropleth won't render but data preserved
            geom = None
        feature = {
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "city": "newtaipei",
                "district": district,
                **stats
            }
        }
        if geom:
            ntpc_features.append(feature)

    if unmatched:
        print(f"WARNING: no polygon found for districts: {unmatched}")

    ntpc_geojson = {"type": "FeatureCollection", "features": ntpc_features}
    ntpc_path = "Taipei-City-Dashboard-FE/public/mapData/labor_disasters_ntpc.geojson"
    with open(ntpc_path, "w", encoding="utf-8") as f:
        json.dump(ntpc_geojson, f, ensure_ascii=False, indent=2)
    print(f"NTPC disaster GeoJSON: {len(ntpc_features)} district features → {ntpc_path}")


if __name__ == "__main__":
    main()
