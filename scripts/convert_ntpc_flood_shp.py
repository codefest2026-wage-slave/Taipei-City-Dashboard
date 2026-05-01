"""
Convert NTPC flood inundation SHP (TWD97 TM2) → GeoJSON (WGS84).

Source: docs/assets/DIS-D2-1/ntpc_flood_shp/24h350r.shp (主要選用 24小時 350mm 中度颱風情境)
Output:
  - Taipei-City-Dashboard-FE/public/mapData/ntpc_flood_24h350.geojson

Run: python3 scripts/convert_ntpc_flood_shp.py
"""
import json
import os
import sys

import shapefile
from pyproj import Transformer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHP = os.path.join(REPO, "docs/assets/DIS-D2-1/ntpc_flood_shp/24h350r.shp")
OUT = os.path.join(REPO, "Taipei-City-Dashboard-FE/public/mapData/ntpc_flood_24h350.geojson")

tx = Transformer.from_crs("EPSG:3826", "EPSG:4326", always_xy=True)


def shape_to_multipolygon(shape):
    """Convert pyshp Polygon shape (with parts) → GeoJSON MultiPolygon coordinates."""
    parts = list(shape.parts) + [len(shape.points)]
    rings = []
    for i in range(len(parts) - 1):
        ring = []
        for x, y in shape.points[parts[i]:parts[i + 1]]:
            lng, lat = tx.transform(x, y)
            ring.append([round(lng, 6), round(lat, 6)])
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        rings.append(ring)
    # Each ring becomes its own polygon (outer ring only — assume no holes for simplicity)
    return [[ring] for ring in rings]


def main():
    sf = shapefile.Reader(SHP)
    print(f"Reading {SHP}", file=sys.stderr)
    print(f"  features: {len(sf.shapes())}", file=sys.stderr)

    features = []
    field_names = [f[0] for f in sf.fields[1:]]  # skip DeletionFlag
    for shape, rec in zip(sf.shapes(), sf.records()):
        attrs = dict(zip(field_names, rec))
        # Filter out depth ≤ 0.3m (noise) and very low GRIDCODE 1 if it's huge
        depth = attrs.get("type") or attrs.get("TYPE") or ""
        coords = shape_to_multipolygon(shape)
        features.append({
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": coords},
            "properties": {
                "GRIDCODE": attrs.get("GRIDCODE"),
                "depth": depth,
                "area_m2": float(attrs.get("A", 0) or 0),
                "scenario": "24h-350mm",
                "city": "newtaipei",
            },
        })
        print(f"  GRIDCODE={attrs.get('GRIDCODE')} depth={depth} parts={len(shape.parts)}", file=sys.stderr)

    # Drop GRIDCODE 1 (淹水深度 0-0.3m, 範圍最大 52000 m²但表示水流無傷大雅) for visual clarity
    # 保留淹水深度 ≥ 0.3m 的範圍（GRIDCODE 2-6）
    filtered = [f for f in features if f["properties"]["GRIDCODE"] != 1]
    print(f"\nAfter filtering GRIDCODE=1: {len(filtered)} features (kept depths ≥ 0.3m)", file=sys.stderr)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": filtered}, f, ensure_ascii=False)
    size_kb = os.path.getsize(OUT) / 1024
    print(f"Wrote {OUT} ({size_kb:.0f} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
