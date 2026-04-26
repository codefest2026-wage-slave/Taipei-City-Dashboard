"""
Fix EV data from user-supplied CSV files in docs/assets/:
  - EV car TPE: replace 36 synthesized records with 240 real records
  - EV scooter TPE: add 12 commercial charging + 365 battery-swap stations

Run from repo root: python scripts/fix_ev_csv_data.py
Then:
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/fix_ev_csv.sql
"""
import csv
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ── Geocoding (ArcGIS World Geocoder, shared cache with other scripts) ────────
_ARCGIS_URL = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
)
_geocode_cache: dict = {}
_cache_lock = threading.Lock()
_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".geocode_cache.json")


def _load_geocode_cache():
    global _geocode_cache
    if os.path.exists(_CACHE_FILE):
        with open(_CACHE_FILE, encoding="utf-8") as _f:
            _geocode_cache = json.load(_f)
    print(f"  Geocode cache: {len(_geocode_cache)} entries loaded")


def _save_geocode_cache():
    with open(_CACHE_FILE, "w", encoding="utf-8") as _f:
        json.dump(_geocode_cache, _f, ensure_ascii=False)


def _clean_addr(addr):
    addr = re.sub(r"\d+~?\d*樓.*$", "", str(addr))
    addr = re.sub(r"[Bb]\d+.*$", "", addr)
    return addr.strip()


def _fetch_geocode(clean_addr):
    with _cache_lock:
        if clean_addr in _geocode_cache:
            return
    result = None
    try:
        resp = requests.get(
            _ARCGIS_URL,
            params={"SingleLine": clean_addr, "f": "json", "outSR": '{"wkid":4326}', "maxLocations": 1},
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
        _geocode_cache[clean_addr] = result


def batch_geocode(addresses, label="", max_workers=20):
    unique = list({_clean_addr(a) for a in addresses if a and _clean_addr(a)})
    with _cache_lock:
        pending = [a for a in unique if a not in _geocode_cache]
    if pending:
        print(f"  {label}: geocoding {len(pending)} new ({len(unique) - len(pending)} cached)...")
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = [ex.submit(_fetch_geocode, a) for a in pending]
            done = 0
            for _ in as_completed(futs):
                done += 1
                if done % 100 == 0:
                    print(f"    {done}/{len(pending)} done...")
        _save_geocode_cache()
    else:
        print(f"  {label}: {len(unique)} addresses all cached")


def geocode_or_fallback(address, fallback_lng, fallback_lat):
    clean = _clean_addr(address)
    if clean:
        with _cache_lock:
            cached = _geocode_cache.get(clean)
        if cached:
            return cached[0], cached[1]
    return fallback_lng, fallback_lat


# ── District centroids ────────────────────────────────────────────────────────
TPE_DISTRICTS = {
    "中正區": (121.5199, 25.0330), "大同區": (121.5129, 25.0630),
    "中山區": (121.5366, 25.0698), "松山區": (121.5578, 25.0502),
    "大安區": (121.5430, 25.0267), "萬華區": (121.4981, 25.0348),
    "信義區": (121.5648, 25.0330), "士林區": (121.5243, 25.0930),
    "北投區": (121.4980, 25.1319), "內湖區": (121.5881, 25.0838),
    "南港區": (121.6068, 25.0550), "文山區": (121.5687, 24.9961),
}


def district_coords(district_str):
    if district_str in TPE_DISTRICTS:
        return TPE_DISTRICTS[district_str]
    for k, v in TPE_DISTRICTS.items():
        if district_str in k or k in district_str:
            return v
    return (121.5654, 25.0330)


def extract_district(addr):
    m = re.search(r"[一-鿿]{2}區", str(addr))
    return m.group(0) if m else "中正區"


def esc(s):
    return str(s).replace("'", "''")


# ── Charger-type heuristic for EV cars ───────────────────────────────────────
_DC_VENDORS = {"Tesla", "星舟快充", "旭電馳科研"}
_DC_KEYWORDS = ("快充",)


def charger_type_from_vendor(vendor):
    if vendor in _DC_VENDORS:
        return "DC"
    if any(kw in vendor for kw in _DC_KEYWORDS):
        return "DC"
    return "AC+DC"


# ── EV car TPE (240 records) ──────────────────────────────────────────────────
def build_ev_car():
    csv_path = "docs/assets/臺北市營利電動車充電站-240站.csv"
    with open(csv_path, encoding="big5") as f:
        rows = list(csv.DictReader(f))
    print(f"  EV car CSV: {len(rows)} records")

    batch_geocode([r["地址"] for r in rows], label="EV car TPE")

    inserts = []
    features = []
    for r in rows:
        addr = r["地址"]
        name = r["名稱"]
        vendor = r["廠商"]
        district = extract_district(addr)
        ct = charger_type_from_vendor(vendor)
        lng, lat = geocode_or_fallback(addr, *district_coords(district))
        inserts.append(
            f"('{esc(name)}', '{esc(addr)}', '{esc(district)}', {lat}, {lng}, '{ct}', 0, NOW())"
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": name, "address": addr, "district": district,
                "city": "taipei", "charger_type": ct, "slots": 0,
            },
        })

    sql = "TRUNCATE TABLE ev_car_charging_tpe;\n"
    sql += "INSERT INTO ev_car_charging_tpe (name, address, district, lat, lng, charger_type, slots, data_time) VALUES\n"
    sql += ",\n".join(inserts) + ";\n"
    return sql, features


# ── EV scooter commercial (12 charging + 365 swap) ───────────────────────────
def build_ev_scooter_commercial():
    charging_path = "docs/assets/臺北市營利電動機車充電站-12站.csv"
    swap_path = "docs/assets/臺北市營利電動機車換電站-365站.csv"

    with open(charging_path, encoding="big5") as f:
        charging_rows = list(csv.DictReader(f))
    with open(swap_path, encoding="big5") as f:
        swap_rows = list(csv.DictReader(f))

    print(f"  EV scooter commercial: {len(charging_rows)} charging + {len(swap_rows)} swap")

    all_addrs = [r["地址"] for r in charging_rows + swap_rows]
    batch_geocode(all_addrs, label="EV scooter commercial TPE")

    inserts = []
    features = []

    for r in charging_rows:
        addr = r["地址"]
        name = r["名稱"]
        operator = r["廠商"]
        district = extract_district(addr)
        lng, lat = geocode_or_fallback(addr, *district_coords(district))
        inserts.append(
            f"('{esc(name)}', '{esc(addr)}', '{esc(district)}', {lat}, {lng}, '{esc(operator)}', 0, NOW())"
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": name, "address": addr, "district": district,
                "city": "taipei", "operator": operator,
            },
        })

    for r in swap_rows:
        addr = r["地址"]
        name = r["名稱"]
        operator = r["廠商"] + " (換電)"
        district = extract_district(addr)
        lng, lat = geocode_or_fallback(addr, *district_coords(district))
        inserts.append(
            f"('{esc(name)}', '{esc(addr)}', '{esc(district)}', {lat}, {lng}, '{esc(operator)}', 0, NOW())"
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": name, "address": addr, "district": district,
                "city": "taipei", "operator": operator,
            },
        })

    sql = "INSERT INTO ev_scooter_charging_tpe (name, address, district, lat, lng, operator, slots, data_time) VALUES\n"
    sql += ",\n".join(inserts) + ";\n"
    return sql, features


# ── GeoJSON helpers ───────────────────────────────────────────────────────────
GEOJSON_DIR = "Taipei-City-Dashboard-FE/public/mapData"


def load_geojson_features(filename):
    path = os.path.join(GEOJSON_DIR, filename)
    if not os.path.exists(path):
        return []
    d = json.load(open(path, encoding="utf-8"))
    return d.get("features", [])


def write_geojson(filename, features):
    path = os.path.join(GEOJSON_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
    print(f"  -> {filename}: {len(features)} features")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=== Fix EV CSV Data ===")
    _load_geocode_cache()

    # EV car
    print("\nBuilding EV car TPE records...")
    car_sql, car_features = build_ev_car()

    # EV scooter commercial
    print("\nBuilding EV scooter commercial records...")
    scooter_sql, new_scooter_features = build_ev_scooter_commercial()

    # Write SQL
    sql_path = "/tmp/fix_ev_csv.sql"
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(car_sql)
        f.write("\n")
        f.write(scooter_sql)
    print(f"\nSQL written to {sql_path}")

    # Update GeoJSON: ev_car_charging.geojson (TPE only, replace all with 240 real)
    print("\nWriting GeoJSON files...")
    write_geojson("ev_car_charging.geojson", car_features)

    # Update GeoJSON: ev_scooter_charging.geojson (TPE: existing 398 + new 377)
    existing_scooter = load_geojson_features("ev_scooter_charging.geojson")
    combined_scooter = existing_scooter + new_scooter_features
    write_geojson("ev_scooter_charging.geojson", combined_scooter)

    print(f"\nDone. Next step:")
    print(f"  docker exec -i postgres-data psql -U postgres -d dashboard < {sql_path}")


if __name__ == "__main__":
    main()
