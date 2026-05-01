"""
L-04-1 Task #11+#12：計算每里質心距最近就服站距離 + 可及性缺口指數，
並產出 GeoJSON Choropleth 圖層。

讀入：
  - dashboard DB: employment_service_centers_tpe/_ntpc, village_population_tpe/_ntpc, district_income_tpe
  - FE assets: Taipei-City-Dashboard-FE/public/mapData/metrotaipei_village.geojson

輸出：
  - dashboard DB: employment_accessibility_tpe / _ntpc 物化表
  - Taipei-City-Dashboard-FE/public/mapData/employment_accessibility.geojson (TPE)
  - Taipei-City-Dashboard-FE/public/mapData/employment_accessibility_ntpc.geojson (NTPC)

Run:
  python3 scripts/build_employment_accessibility.py
"""

import csv
import json
import math
import os
import subprocess
import sys
from io import StringIO

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_SRC = os.path.join(REPO, "Taipei-City-Dashboard-FE/public/mapData/metrotaipei_village.geojson")
GEO_OUT_DIR = os.path.join(REPO, "Taipei-City-Dashboard-FE/public/mapData")
SQL_OUT = "/tmp/employment_accessibility_table.sql"

# 服務半徑（公尺）：台北 1km / 新北 3km
SERVICE_RADIUS_TPE = 1000
SERVICE_RADIUS_NTPC = 3000


def psql_csv(query):
    """Run a SELECT in dashboard DB and return list of dicts."""
    cmd = [
        "docker", "exec", "-i", "postgres-data",
        "psql", "-U", "postgres", "-d", "dashboard",
        "--csv", "-c", query,
    ]
    out = subprocess.check_output(cmd, text=True)
    return list(csv.DictReader(StringIO(out)))


def haversine(lng1, lat1, lng2, lat2):
    """Distance between two lng/lat points in meters."""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def polygon_centroid(coords):
    """Return (lng, lat) centroid for a polygon ring (first ring only)."""
    if not coords:
        return None, None
    if isinstance(coords[0][0], (int, float)):
        ring = coords
    else:
        ring = coords[0]
    n = len(ring)
    if n == 0:
        return None, None
    cx = sum(p[0] for p in ring) / n
    cy = sum(p[1] for p in ring) / n
    return cx, cy


def feature_centroid(feat):
    geom = feat.get("geometry") or {}
    t = geom.get("type")
    coords = geom.get("coordinates") or []
    if t == "Polygon":
        return polygon_centroid(coords)
    if t == "MultiPolygon":
        # use largest ring's centroid (rough)
        biggest, area = None, 0
        for poly in coords:
            ring = poly[0] if poly else []
            if len(ring) > area:
                area = len(ring)
                biggest = poly
        if biggest:
            return polygon_centroid(biggest)
    return None, None


def main():
    print("Loading GeoJSON…", file=sys.stderr)
    with open(GEO_SRC, encoding="utf-8") as f:
        geo = json.load(f)
    feats = geo.get("features", [])
    print(f"  {len(feats)} village features", file=sys.stderr)

    # Centers
    print("Loading employment centers…", file=sys.stderr)
    centers_tpe = [
        (float(r["lng"]), float(r["lat"]), r["name"])
        for r in psql_csv("SELECT name, lng, lat FROM employment_service_centers_tpe WHERE lng IS NOT NULL")
    ]
    centers_ntpc = [
        (float(r["lng"]), float(r["lat"]), r["name"])
        for r in psql_csv("SELECT name, lng, lat FROM employment_service_centers_ntpc WHERE lng IS NOT NULL")
    ]
    print(f"  TPE={len(centers_tpe)}, NTPC={len(centers_ntpc)}", file=sys.stderr)

    # Village population
    print("Loading village populations…", file=sys.stderr)
    pop_tpe = {(r["district"], r["village"]): r for r in psql_csv(
        "SELECT district, village, total_pop, midage_pop, elder_pop, households FROM village_population_tpe"
    )}
    pop_ntpc = {(r["district"], r["village"]): r for r in psql_csv(
        "SELECT district, village, total_pop, midage_pop, elder_pop, households FROM village_population_ntpc"
    )}
    print(f"  TPE={len(pop_tpe)}, NTPC={len(pop_ntpc)}", file=sys.stderr)

    # District income (TPE only)
    income_tpe = {r["district"]: r for r in psql_csv(
        "SELECT district, avg_disposable_per_household, worker_per_household FROM district_income_tpe"
    )}

    # Process features
    tpe_features, ntpc_features = [], []
    rows_for_sql = {"tpe": [], "ntpc": []}

    for feat in feats:
        props = feat.get("properties") or {}
        pname = props.get("PNAME") or ""
        district = props.get("TNAME") or ""
        village = props.get("VNAME") or ""
        cx, cy = feature_centroid(feat)
        if cx is None or village == "":
            continue

        is_tpe = pname == "臺北市"
        centers = centers_tpe if is_tpe else centers_ntpc
        radius = SERVICE_RADIUS_TPE if is_tpe else SERVICE_RADIUS_NTPC
        pop_table = pop_tpe if is_tpe else pop_ntpc

        # nearest center
        nearest_dist = float("inf")
        nearest_name = ""
        for clng, clat, cname in centers:
            d = haversine(cx, cy, clng, clat)
            if d < nearest_dist:
                nearest_dist = d
                nearest_name = cname

        # population
        pop = pop_table.get((district, village)) or {}
        try:
            total_pop = int(pop.get("total_pop") or 0)
            midage = int(pop.get("midage_pop") or 0)
            elder = int(pop.get("elder_pop") or 0)
        except ValueError:
            total_pop = midage = elder = 0

        # 弱勢勞工代理：中高齡 + 高齡×1.5
        vulnerable = midage + int(elder * 1.5)

        # 台北加權：所屬行政區的「每戶可支配所得倒數」（千元）
        income_factor = 1.0
        avg_disposable = None
        if is_tpe:
            inc = income_tpe.get(district)
            if inc:
                try:
                    avg_disposable = int(inc["avg_disposable_per_household"])
                    # 1230 (poorest) → 1.39 倍；1708 (richest) → 1.0 倍（線性反比）
                    income_factor = 1708.0 / avg_disposable if avg_disposable > 0 else 1.0
                except ValueError:
                    pass

        # accessibility gap score
        # 距離倍數：service radius 內為 0 / 2 倍以上達上限
        dist_ratio = max(0, min(1, (nearest_dist - radius) / radius))
        # 弱勢規模倍數：1000 人 → 1.0
        vuln_ratio = min(vulnerable / 1000.0, 1.5)
        # final score 0-100
        gap_score = round(dist_ratio * 60 + vuln_ratio * 30 + (income_factor - 1) * 10, 1)

        feat_props = {
            "city": "taipei" if is_tpe else "newtaipei",
            "district": district,
            "village": village,
            "full_name": f"{pname}{district}{village}",
            "centroid_lng": round(cx, 6),
            "centroid_lat": round(cy, 6),
            "nearest_center": nearest_name,
            "nearest_dist_m": round(nearest_dist, 1),
            "service_radius_m": radius,
            "in_service": nearest_dist <= radius,
            "total_pop": total_pop,
            "midage_pop": midage,
            "elder_pop": elder,
            "vulnerable_proxy": vulnerable,
            "avg_disposable_kntd": avg_disposable,
            "gap_score": gap_score,
        }
        new_feat = {
            "type": "Feature",
            "geometry": feat.get("geometry"),
            "properties": feat_props,
        }
        if is_tpe:
            tpe_features.append(new_feat)
        else:
            ntpc_features.append(new_feat)

        rows_for_sql["tpe" if is_tpe else "ntpc"].append({
            "district": district, "village": village,
            "centroid_lng": cx, "centroid_lat": cy,
            "nearest_center": nearest_name, "nearest_dist_m": nearest_dist,
            "in_service": nearest_dist <= radius,
            "total_pop": total_pop, "midage_pop": midage, "elder_pop": elder,
            "vulnerable_proxy": vulnerable, "avg_disposable_kntd": avg_disposable,
            "gap_score": gap_score,
        })

    print(f"\nProcessed: TPE={len(tpe_features)} villages, NTPC={len(ntpc_features)} villages", file=sys.stderr)

    # ─── write GeoJSON files ───
    tpe_out = os.path.join(GEO_OUT_DIR, "employment_accessibility.geojson")
    ntpc_out = os.path.join(GEO_OUT_DIR, "employment_accessibility_ntpc.geojson")
    with open(tpe_out, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": tpe_features}, f, ensure_ascii=False)
    with open(ntpc_out, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": ntpc_features}, f, ensure_ascii=False)
    print(f"Wrote {tpe_out}", file=sys.stderr)
    print(f"Wrote {ntpc_out}", file=sys.stderr)

    # ─── write SQL for materialized table ───
    def esc(v):
        if v is None:
            return "NULL"
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        return str(v)

    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n")
        for city in ("tpe", "ntpc"):
            tbl = f"employment_accessibility_{city}"
            f.write(f"\nDROP TABLE IF EXISTS {tbl};\n")
            f.write(f"""CREATE TABLE {tbl} (
    id SERIAL PRIMARY KEY,
    district VARCHAR(20) NOT NULL,
    village VARCHAR(50) NOT NULL,
    centroid_lng DOUBLE PRECISION,
    centroid_lat DOUBLE PRECISION,
    nearest_center VARCHAR(200),
    nearest_dist_m DOUBLE PRECISION,
    in_service BOOLEAN,
    total_pop INTEGER,
    midage_pop INTEGER,
    elder_pop INTEGER,
    vulnerable_proxy INTEGER,
    avg_disposable_kntd INTEGER,
    gap_score NUMERIC(5,1)
);
""")
            BATCH = 200
            rows = rows_for_sql[city]
            for i in range(0, len(rows), BATCH):
                chunk = rows[i:i + BATCH]
                vals = [
                    "({d},{v},{lng},{lat},{c},{dist},{ins},{tp},{m},{e},{vp},{ad},{gs})".format(
                        d=esc(r["district"]), v=esc(r["village"]),
                        lng=r["centroid_lng"], lat=r["centroid_lat"],
                        c=esc(r["nearest_center"]), dist=r["nearest_dist_m"],
                        ins=esc(r["in_service"]),
                        tp=r["total_pop"], m=r["midage_pop"], e=r["elder_pop"],
                        vp=r["vulnerable_proxy"],
                        ad=esc(r["avg_disposable_kntd"]),
                        gs=r["gap_score"],
                    )
                    for r in chunk
                ]
                f.write(
                    f"INSERT INTO {tbl} (district, village, centroid_lng, centroid_lat, "
                    f"nearest_center, nearest_dist_m, in_service, total_pop, midage_pop, elder_pop, "
                    f"vulnerable_proxy, avg_disposable_kntd, gap_score) VALUES\n"
                    + ",\n".join(vals) + ";\n"
                )
            f.write(f"CREATE INDEX idx_{tbl}_score ON {tbl}(gap_score DESC);\n")
        f.write("COMMIT;\n")
    print(f"Wrote {SQL_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
