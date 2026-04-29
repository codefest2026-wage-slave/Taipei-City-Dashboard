"""
Generate GeoJSON for L-01-1 複查優先佇列引擎 map layer.

Reads top-N highest-risk employers from labor_recheck_priority_{tpe,ntpc},
geocodes addresses via ArcGIS (with fallback to district centroid), and writes:

  Taipei-City-Dashboard-FE/public/mapData/labor_recheck_priority.geojson       (TPE only)
  Taipei-City-Dashboard-FE/public/mapData/labor_recheck_priority_ntpc.geojson  (NTPC only)

Run:
  python3 scripts/generate_recheck_priority_geojson.py
"""

import json
import os
import random
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

random.seed(42)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_DIR = os.path.join(REPO, "Taipei-City-Dashboard-FE", "public", "mapData")
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".geocode_cache.json")
TOP_N = 500  # 取每市前 500 名高風險雇主

ARCGIS_URL = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
)

_geocode_cache: dict = {}
_cache_lock = threading.Lock()

TPE_DISTRICTS = {
    "中正區": (121.5199, 25.0330), "大同區": (121.5129, 25.0630),
    "中山區": (121.5366, 25.0698), "松山區": (121.5578, 25.0502),
    "大安區": (121.5430, 25.0267), "萬華區": (121.4981, 25.0348),
    "信義區": (121.5648, 25.0330), "士林區": (121.5243, 25.0930),
    "北投區": (121.4980, 25.1319), "內湖區": (121.5881, 25.0838),
    "南港區": (121.6068, 25.0550), "文山區": (121.5687, 24.9961),
}

NTPC_DISTRICTS = {
    "板橋區": (121.4634, 25.0136), "三重區": (121.4872, 25.0614),
    "中和區": (121.4977, 24.9978), "永和區": (121.5168, 25.0081),
    "新莊區": (121.4506, 25.0351), "新店區": (121.5412, 24.9680),
    "樹林區": (121.4116, 24.9897), "鶯歌區": (121.3459, 24.9559),
    "三峽區": (121.3673, 24.9327), "淡水區": (121.4423, 25.1653),
    "汐止區": (121.6566, 25.0657), "瑞芳區": (121.8027, 25.1027),
    "土城區": (121.4420, 24.9731), "蘆洲區": (121.4746, 25.0915),
    "五股區": (121.4359, 25.0787), "泰山區": (121.4227, 25.0563),
    "林口區": (121.3873, 25.0876), "深坑區": (121.6153, 24.9905),
    "石碇區": (121.6537, 24.9748), "坪林區": (121.7149, 24.9312),
    "三芝區": (121.4994, 25.2157), "石門區": (121.5695, 25.2826),
    "八里區": (121.4062, 25.1595), "平溪區": (121.7416, 25.0174),
    "雙溪區": (121.8726, 25.0338), "貢寮區": (121.8898, 25.0258),
    "金山區": (121.6391, 25.2233), "萬里區": (121.6784, 25.1785),
    "烏來區": (121.5462, 24.8651),
}


def jitter(lng, lat, radius=0.005):
    return (lng + random.uniform(-radius, radius), lat + random.uniform(-radius, radius))


def district_coords(addr, city):
    """Match district name from address; return centroid + jitter."""
    table = TPE_DISTRICTS if city == "taipei" else NTPC_DISTRICTS
    if not addr:
        fallback = (121.5654, 25.0330) if city == "taipei" else (121.4634, 25.0136)
        return jitter(*fallback)
    for d, coords in table.items():
        if d in addr:
            return jitter(*coords)
    fallback = (121.5654, 25.0330) if city == "taipei" else (121.4634, 25.0136)
    return jitter(*fallback)


def _load_cache():
    global _geocode_cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            _geocode_cache = json.load(f)
    print(f"  Geocode cache: {len(_geocode_cache)} entries", file=sys.stderr)


def _save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_geocode_cache, f, ensure_ascii=False)


def _clean_addr(addr):
    addr = re.sub(r"\d+~?\d*樓.*$", "", str(addr or ""))
    addr = re.sub(r"[Bb]\d+.*$", "", addr)
    return addr.strip()


def _fetch_geocode(clean):
    with _cache_lock:
        if clean in _geocode_cache:
            return
    result = None
    try:
        resp = requests.get(
            ARCGIS_URL,
            params={
                "SingleLine": clean,
                "f": "json",
                "outSR": '{"wkid":4326}',
                "maxLocations": 1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        cands = resp.json().get("candidates", [])
        if cands and cands[0].get("score", 0) >= 80:
            loc = cands[0]["location"]
            result = [loc["x"], loc["y"]]
    except Exception:
        pass
    with _cache_lock:
        _geocode_cache[clean] = result


def batch_geocode(addresses, label):
    unique = list({_clean_addr(a) for a in addresses if a and _clean_addr(a)})
    with _cache_lock:
        pending = [a for a in unique if a not in _geocode_cache]
    if not pending:
        print(f"  {label}: {len(unique)} addresses all cached", file=sys.stderr)
        return
    print(f"  {label}: geocoding {len(pending)} new ({len(unique) - len(pending)} cached)…",
          file=sys.stderr)
    with ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(_fetch_geocode, a) for a in pending]
        done = 0
        for _ in as_completed(futs):
            done += 1
            if done % 100 == 0:
                print(f"    {done}/{len(pending)}…", file=sys.stderr)
    _save_cache()


def geocode_or_fallback(addr, city):
    clean = _clean_addr(addr)
    if clean:
        with _cache_lock:
            cached = _geocode_cache.get(clean)
        if cached:
            return cached[0], cached[1]
    return district_coords(addr, city)


def fetch_top_employers(city):
    """Fetch top-N rows via psql --csv (avoids host psycopg2 dependency)."""
    table = "labor_recheck_priority_tpe" if city == "taipei" else "labor_recheck_priority_ntpc"
    query = (
        f"SELECT id, company_name, COALESCE(address, '') AS address, "
        f"COALESCE(industry_name, '') AS industry_name, "
        f"total_violations, labor_count, safety_count, gender_count, "
        f"days_since_last, COALESCE(capital, 0) AS capital, "
        f"disaster_count, risk_score "
        f"FROM {table} ORDER BY risk_score DESC NULLS LAST LIMIT {TOP_N};"
    )
    cmd = [
        "docker", "exec", "-i", "postgres-data",
        "psql", "-U", "postgres", "-d", "dashboard",
        "--csv", "-c", query,
    ]
    out = subprocess.check_output(cmd, text=True)
    import csv
    from io import StringIO
    reader = csv.DictReader(StringIO(out))
    return list(reader)


def build_geojson(rows, city_prop):
    features = []
    for r in rows:
        try:
            lng, lat = geocode_or_fallback(r["address"], "taipei" if city_prop == "taipei" else "newtaipei")
        except Exception:
            continue
        capital = int(r["capital"]) if r["capital"] else 0
        capital_man = round(capital / 10000) if capital else 0  # 萬元
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": r["company_name"],
                "city": city_prop,
                "address": r["address"],
                "industry": r["industry_name"] or "未知",
                "total_violations": int(r["total_violations"]),
                "labor": int(r["labor_count"]),
                "safety": int(r["safety_count"]),
                "gender": int(r["gender_count"]),
                "days_since_last": int(r["days_since_last"]) if r["days_since_last"] else None,
                "capital_man": capital_man,
                "disaster_count": int(r["disaster_count"]),
                "risk_score": float(r["risk_score"]) if r["risk_score"] else 0,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def main():
    os.makedirs(GEO_DIR, exist_ok=True)
    _load_cache()

    print("Fetching TPE top employers…", file=sys.stderr)
    tpe_rows = fetch_top_employers("taipei")
    print(f"  → {len(tpe_rows)} rows", file=sys.stderr)
    batch_geocode([r["address"] for r in tpe_rows], "TPE")

    print("Fetching NTPC top employers…", file=sys.stderr)
    ntpc_rows = fetch_top_employers("newtaipei")
    print(f"  → {len(ntpc_rows)} rows", file=sys.stderr)
    batch_geocode([r["address"] for r in ntpc_rows], "NTPC")

    tpe_geo = build_geojson(tpe_rows, "taipei")
    ntpc_geo = build_geojson(ntpc_rows, "newtaipei")

    tpe_out = os.path.join(GEO_DIR, "labor_recheck_priority.geojson")
    ntpc_out = os.path.join(GEO_DIR, "labor_recheck_priority_ntpc.geojson")
    with open(tpe_out, "w", encoding="utf-8") as f:
        json.dump(tpe_geo, f, ensure_ascii=False)
    with open(ntpc_out, "w", encoding="utf-8") as f:
        json.dump(ntpc_geo, f, ensure_ascii=False)
    print(f"\nWrote {len(tpe_geo['features'])} TPE features → {tpe_out}", file=sys.stderr)
    print(f"Wrote {len(ntpc_geo['features'])} NTPC features → {ntpc_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
