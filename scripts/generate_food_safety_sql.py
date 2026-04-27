#!/usr/bin/env python3
"""
Generate SQL + GeoJSON for 食安風險追蹤器 (Food Safety Risk Tracker) dashboard.

Data sources:
  - TPE certified restaurants: docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv
  - TPE inspection stats:      docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv
  - TPE testing stats:         docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv
  - NTPC food factories:       data.ntpc API (UUID c51d5111-c300-44c9-b4f1-4b28b9929ca2)

Output:
  - /tmp/food_safety_data.sql                   → inject into postgres-data (dashboard DB)
  - FE/public/mapData/food_restaurant_tpe.geojson
  - FE/public/mapData/food_factory_ntpc.geojson

Run from repo root:
  python scripts/generate_food_safety_sql.py
"""
import csv
import json
import os
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).parent.parent
ASSETS_DIR = REPO_ROOT / "docs/assets"
MAPDATA_DIR = REPO_ROOT / "Taipei-City-Dashboard-FE/public/mapData"
SQL_OUT = Path("/tmp/food_safety_data.sql")

# ── Geocoding (ArcGIS, free, no key) ──────────────────────────────────────────
_ARCGIS_URL = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
)
_CACHE_FILE = Path(__file__).parent / ".geocode_cache.json"
_geocode_cache: dict = {}
_cache_lock = threading.Lock()


def _load_geocode_cache():
    global _geocode_cache
    if _CACHE_FILE.exists():
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _geocode_cache = json.load(f)
    print(f"  Geocode cache: {len(_geocode_cache)} entries loaded")


def _save_geocode_cache():
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_geocode_cache, f, ensure_ascii=False)


def _clean_addr(addr):
    addr = re.sub(r"\d+~?\d*[Ff樓].*$", "", str(addr))
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
            params={
                "SingleLine": clean_addr,
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
        _geocode_cache[clean_addr] = result


def batch_geocode(addresses, label="", max_workers=20):
    unique = list({_clean_addr(a) for a in addresses if a and _clean_addr(a)})
    with _cache_lock:
        to_fetch = [a for a in unique if a not in _geocode_cache]
    print(f"  [{label}] geocoding {len(to_fetch)} new / {len(unique)} unique addresses …")
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_geocode, a): a for a in to_fetch}
        done = 0
        for _ in as_completed(futures):
            done += 1
            if done % 100 == 0:
                print(f"    … {done}/{len(to_fetch)}")
    _save_geocode_cache()
    with _cache_lock:
        hits = sum(1 for a in unique if _geocode_cache.get(a) is not None)
    print(f"  [{label}] success: {hits}/{len(unique)}")


def geocode_or_fallback(addr, fallback_lng, fallback_lat):
    clean = _clean_addr(addr)
    with _cache_lock:
        result = _geocode_cache.get(clean)
    if result:
        return result[0], result[1]
    return (
        fallback_lng + random.uniform(-0.006, 0.006),
        fallback_lat + random.uniform(-0.004, 0.004),
    )


# TPE district centroids keyed by 行政區域代碼
TPE_DISTRICT = {
    "63000010": (121.5771, 25.0504, "松山區"),
    "63000020": (121.5639, 25.0330, "信義區"),
    "63000030": (121.5432, 25.0260, "大安區"),
    "63000040": (121.5301, 25.0637, "中山區"),
    "63000050": (121.5186, 25.0432, "中正區"),
    "63000060": (121.5102, 25.0633, "大同區"),
    "63000070": (121.5002, 25.0347, "萬華區"),
    "63000080": (121.5706, 24.9892, "文山區"),
    "63000090": (121.6071, 25.0554, "南港區"),
    "63000100": (121.5878, 25.0831, "內湖區"),
    "63000110": (121.5261, 25.0924, "士林區"),
    "63000120": (121.5008, 25.1318, "北投區"),
}


# ── SQL helpers ───────────────────────────────────────────────────────────────
def esc(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def num(s, default="NULL"):
    try:
        v = str(s).strip().replace(",", "")
        if v in ("", "-", "—"):
            return default
        f = float(v)
        return str(int(f)) if f == int(f) else str(f)
    except Exception:
        return default


# ── Data fetch: NTPC factories ────────────────────────────────────────────────
def fetch_ntpc_factories():
    base = "https://data.ntpc.gov.tw/api/datasets/c51d5111-c300-44c9-b4f1-4b28b9929ca2/json"
    rows = []
    page = 0
    print("  Fetching NTPC food factories …")
    while True:
        r = requests.get(base, params={"size": 200, "page": page}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        rows.extend(data)
        print(f"    page {page}: {len(data)} rows, total {len(rows)}")
        if len(data) < 200:
            break
        page += 1
    return rows


# ── Data load: CSV files ──────────────────────────────────────────────────────
def load_restaurants():
    path = ASSETS_DIR / "114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv"
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_rok_year(text):
    """Convert ROC year string like '95年' to AD integer 2006."""
    m = re.match(r"(\d+)年", str(text).strip())
    if not m:
        return None
    return int(m.group(1)) + 1911


def load_inspection_stats():
    path = ASSETS_DIR / "臺北市食品衛生管理稽查工作-年度統計.csv"
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    result = []
    for r in rows:
        year = parse_rok_year(r["統計期"])
        if year is None or year < 2006:
            continue
        result.append({
            "year": year,
            "total_inspections": num(r.get("食品衛生管理稽查工作/稽查家次[家次]")),
            "restaurant_insp": num(r.get("食品衛生管理稽查工作/餐飲店/稽查家次[家次]")),
            "drink_shop_insp": num(r.get("食品衛生管理稽查工作/冷飲店/稽查家次[家次]")),
            "street_vendor_insp": num(r.get("食品衛生管理稽查工作/飲食攤販/稽查家次[家次]")),
            "market_insp": num(r.get("食品衛生管理稽查工作/傳統市場/稽查家次[家次]")),
            "supermarket_insp": num(r.get("食品衛生管理稽查工作/超級市場/稽查家次[家次]")),
            "manufacturer_insp": num(r.get("食品衛生管理稽查工作/製造廠商/稽查家次[家次]")),
            "total_noncompliance": num(r.get("食品衛生管理稽查工作/不合格飭令改善家次[家次]")),
            "restaurant_nc": num(r.get("食品衛生管理稽查工作/餐飲店/不合格飭令改善家次[家次]")),
            "drink_shop_nc": num(r.get("食品衛生管理稽查工作/冷飲店/不合格飭令改善家次[家次]")),
            "street_vendor_nc": num(r.get("食品衛生管理稽查工作/飲食攤販/不合格飭令改善家次[家次]")),
            "market_nc": num(r.get("食品衛生管理稽查工作/傳統市場/不合格飭令改善家次[家次]")),
            "supermarket_nc": num(r.get("食品衛生管理稽查工作/超級市場/不合格飭令改善家次[家次]")),
            "manufacturer_nc": num(r.get("食品衛生管理稽查工作/製造廠商/不合格飭令改善家次[家次]")),
            "food_poisoning_cases": num(r.get("食品中毒人數[人]")),
        })
    return result


def load_testing_stats():
    path = ASSETS_DIR / "臺北市食品衛生管理查驗工作-年度統計.csv"
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    result = []
    for r in rows:
        year = parse_rok_year(r["統計期"])
        if year is None:
            continue
        result.append({
            "year": year,
            "total_tested": num(r.get("查驗件數/總計[件]")),
            "total_violations": num(r.get("與規定不符件數/總計[件]")),
            "violation_rate": num(r.get("不符規定比率[%]")),
            "viol_labeling": num(r.get("與規定不符件數按原因別/違規標示[件]")),
            "viol_ad": num(r.get("與規定不符件數按原因別/違規廣告[件]")),
            "viol_additive": num(r.get("與規定不符件數按原因別/食品添加物[件]")),
            "viol_container": num(r.get("與規定不符件數按原因別/食品器皿容器包裝檢驗[件]")),
            "viol_microbe": num(r.get("與規定不符件數按原因別/微生物[件]")),
            "viol_mycotoxin": num(r.get("與規定不符件數按原因別/真菌毒素[件]")),
            "viol_vetdrug": num(r.get("與規定不符件數按原因別/動物用藥殘留[件]")),
            "viol_chemical": num(r.get("與規定不符件數按原因別/化學成分[件]")),
            "viol_composition": num(r.get("與規定不符件數按原因別/成分分析[件]")),
            "viol_other": num(r.get(" 與規定不符件數按原因別/其他[件]",
                                   r.get("與規定不符件數按原因別/其他[件]"))),
        })
    return result


# ── SQL generation ────────────────────────────────────────────────────────────
def build_sql(inspection_rows, testing_rows, factory_rows, restaurant_rows):
    lines = [
        "-- Food Safety Risk Tracker — city data tables",
        "-- Generated by scripts/generate_food_safety_sql.py",
        "",
        "-- ── Schema ──────────────────────────────────────────────────────────",
        "DROP TABLE IF EXISTS food_inspection_tpe CASCADE;",
        "CREATE TABLE food_inspection_tpe (",
        "  year INTEGER PRIMARY KEY,",
        "  total_inspections INTEGER,",
        "  restaurant_insp INTEGER,",
        "  drink_shop_insp INTEGER,",
        "  street_vendor_insp INTEGER,",
        "  market_insp INTEGER,",
        "  supermarket_insp INTEGER,",
        "  manufacturer_insp INTEGER,",
        "  total_noncompliance INTEGER,",
        "  restaurant_nc INTEGER,",
        "  drink_shop_nc INTEGER,",
        "  street_vendor_nc INTEGER,",
        "  market_nc INTEGER,",
        "  supermarket_nc INTEGER,",
        "  manufacturer_nc INTEGER,",
        "  food_poisoning_cases INTEGER",
        ");",
        "",
        "DROP TABLE IF EXISTS food_testing_tpe CASCADE;",
        "CREATE TABLE food_testing_tpe (",
        "  year INTEGER PRIMARY KEY,",
        "  total_tested INTEGER,",
        "  total_violations INTEGER,",
        "  violation_rate NUMERIC(5,2),",
        "  viol_labeling INTEGER,",
        "  viol_ad INTEGER,",
        "  viol_additive INTEGER,",
        "  viol_container INTEGER,",
        "  viol_microbe INTEGER,",
        "  viol_mycotoxin INTEGER,",
        "  viol_vetdrug INTEGER,",
        "  viol_chemical INTEGER,",
        "  viol_composition INTEGER,",
        "  viol_other INTEGER",
        ");",
        "",
        "DROP TABLE IF EXISTS food_factory_ntpc CASCADE;",
        "CREATE TABLE food_factory_ntpc (",
        "  id SERIAL PRIMARY KEY,",
        "  name VARCHAR(200),",
        "  address VARCHAR(300),",
        "  tax_id VARCHAR(50),",
        "  lng DOUBLE PRECISION,",
        "  lat DOUBLE PRECISION,",
        "  district VARCHAR(50)",
        ");",
        "",
        "DROP TABLE IF EXISTS food_restaurant_tpe CASCADE;",
        "CREATE TABLE food_restaurant_tpe (",
        "  id SERIAL PRIMARY KEY,",
        "  name VARCHAR(200),",
        "  address VARCHAR(300),",
        "  district VARCHAR(50),",
        "  grade VARCHAR(10),",
        "  lng DOUBLE PRECISION,",
        "  lat DOUBLE PRECISION",
        ");",
        "",
    ]

    # food_inspection_tpe
    lines.append("-- ── food_inspection_tpe ─────────────────────────────────────────────")
    lines.append("INSERT INTO food_inspection_tpe VALUES")
    vals = []
    for r in inspection_rows:
        vals.append(
            f"  ({r['year']},{r['total_inspections']},{r['restaurant_insp']},"
            f"{r['drink_shop_insp']},{r['street_vendor_insp']},{r['market_insp']},"
            f"{r['supermarket_insp']},{r['manufacturer_insp']},"
            f"{r['total_noncompliance']},{r['restaurant_nc']},{r['drink_shop_nc']},"
            f"{r['street_vendor_nc']},{r['market_nc']},{r['supermarket_nc']},"
            f"{r['manufacturer_nc']},{r['food_poisoning_cases']})"
        )
    lines.append(",\n".join(vals) + ";")
    lines.append("")

    # food_testing_tpe
    lines.append("-- ── food_testing_tpe ────────────────────────────────────────────────")
    lines.append("INSERT INTO food_testing_tpe VALUES")
    vals = []
    for r in testing_rows:
        vals.append(
            f"  ({r['year']},{r['total_tested']},{r['total_violations']},"
            f"{r['violation_rate']},"
            f"{r['viol_labeling']},{r['viol_ad']},{r['viol_additive']},"
            f"{r['viol_container']},{r['viol_microbe']},{r['viol_mycotoxin']},"
            f"{r['viol_vetdrug']},{r['viol_chemical']},{r['viol_composition']},"
            f"{r['viol_other']})"
        )
    lines.append(",\n".join(vals) + ";")
    lines.append("")

    # food_factory_ntpc
    lines.append("-- ── food_factory_ntpc ───────────────────────────────────────────────")
    if factory_rows:
        lines.append("INSERT INTO food_factory_ntpc (name, address, tax_id, lng, lat, district) VALUES")
        vals = []
        for r in factory_rows:
            try:
                lng = float(r.get("wgs84ax", 0))
                lat = float(r.get("wgs84ay", 0))
            except (ValueError, TypeError):
                continue
            if not (120 < lng < 122.5 and 24 < lat < 26):
                continue
            addr = r.get("address", "")
            # Extract district from address (新北市XX區...)
            district = ""
            m = re.search(r"新北市(\S+區)", addr)
            if m:
                district = m.group(1)
            vals.append(
                f"  ({esc(r.get('organizer', r.get('name_ins','')))}," \
                 f"{esc(addr)},"
                f"{esc(r.get('tax_id_number',''))},{lng},{lat},{esc(district)})"
            )
        lines.append(",\n".join(vals) + ";")
    else:
        lines.append("-- WARNING: No NTPC factory data available")
    lines.append("")

    # food_restaurant_tpe
    lines.append("-- ── food_restaurant_tpe ─────────────────────────────────────────────")
    lines.append("INSERT INTO food_restaurant_tpe (name, address, district, grade, lng, lat) VALUES")
    vals = []
    for r in restaurant_rows:
        code = r.get("行政區域代碼", "")
        centroid = TPE_DISTRICT.get(code, (121.5654, 25.0330, "其他"))
        lng, lat = geocode_or_fallback(r.get("地址", ""), centroid[0], centroid[1])
        vals.append(
            f"  ({esc(r.get('業者名稱店名',''))},"
            f"{esc(r.get('地址',''))},"
            f"{esc(centroid[2])},"
            f"{esc(r.get('評核結果',''))},"
            f"{round(lng, 6)},{round(lat, 6)})"
        )
    lines.append(",\n".join(vals) + ";")
    lines.append("")
    lines.append("-- Verify row counts")
    lines.append("SELECT 'food_inspection_tpe' AS tbl, COUNT(*) FROM food_inspection_tpe")
    lines.append("UNION ALL SELECT 'food_testing_tpe', COUNT(*) FROM food_testing_tpe")
    lines.append("UNION ALL SELECT 'food_factory_ntpc', COUNT(*) FROM food_factory_ntpc")
    lines.append("UNION ALL SELECT 'food_restaurant_tpe', COUNT(*) FROM food_restaurant_tpe;")

    return "\n".join(lines)


# ── GeoJSON generation ────────────────────────────────────────────────────────
def build_restaurant_geojson(restaurant_rows):
    features = []
    for r in restaurant_rows:
        code = r.get("行政區域代碼", "")
        centroid = TPE_DISTRICT.get(code, (121.5654, 25.0330, "其他"))
        lng, lat = geocode_or_fallback(r.get("地址", ""), centroid[0], centroid[1])
        grade = r.get("評核結果", "優")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]},
            "properties": {
                "name": r.get("業者名稱店名", ""),
                "grade": grade,
                "address": r.get("地址", ""),
                "district": centroid[2],
                "city": "taipei",
            },
        })
    return {"type": "FeatureCollection", "features": features}


def build_factory_geojson(factory_rows):
    features = []
    for r in factory_rows:
        try:
            lng = float(r.get("wgs84ax", 0))
            lat = float(r.get("wgs84ay", 0))
        except (ValueError, TypeError):
            continue
        if not (120 < lng < 122.5 and 24 < lat < 26):
            continue
        addr = r.get("address", "")
        district = ""
        m = re.search(r"新北市(\S+區)", addr)
        if m:
            district = m.group(1)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lng, 6), round(lat, 6)]},
            "properties": {
                "name": r.get("organizer", r.get("name_ins", "")),
                "address": addr,
                "district": district,
                "city": "newtaipei",
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    random.seed(42)
    _load_geocode_cache()

    print("\n=== Loading CSV files ===")
    restaurants = load_restaurants()
    print(f"  TPE restaurants: {len(restaurants)} rows")
    inspection = load_inspection_stats()
    print(f"  TPE inspection stats: {len(inspection)} rows")
    testing = load_testing_stats()
    print(f"  TPE testing stats: {len(testing)} rows")

    print("\n=== Fetching NTPC factories ===")
    try:
        factories = fetch_ntpc_factories()
        print(f"  NTPC factories: {len(factories)} rows")
    except Exception as e:
        print(f"  WARNING: Could not fetch NTPC factories: {e}")
        factories = []

    print("\n=== Geocoding TPE restaurants ===")
    batch_geocode([r.get("地址", "") for r in restaurants], label="TPE restaurants")

    print("\n=== Generating SQL ===")
    sql = build_sql(inspection, testing, factories, restaurants)
    SQL_OUT.write_text(sql, encoding="utf-8")
    print(f"  SQL written to {SQL_OUT} ({len(sql):,} bytes)")

    print("\n=== Generating GeoJSON ===")
    rest_geo = build_restaurant_geojson(restaurants)
    rest_path = MAPDATA_DIR / "food_restaurant_tpe.geojson"
    rest_path.write_text(json.dumps(rest_geo, ensure_ascii=False), encoding="utf-8")
    print(f"  food_restaurant_tpe.geojson: {len(rest_geo['features'])} features → {rest_path}")

    fact_geo = build_factory_geojson(factories)
    fact_path = MAPDATA_DIR / "food_factory_ntpc.geojson"
    fact_path.write_text(json.dumps(fact_geo, ensure_ascii=False), encoding="utf-8")
    print(f"  food_factory_ntpc.geojson: {len(fact_geo['features'])} features → {fact_path}")

    print("\n=== Done ===")
    print("Next steps:")
    print("  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/food_safety_data.sql")


if __name__ == "__main__":
    main()
