"""
Fetch disaster resilience datasets and generate SQL + GeoJSON files.

Data sources:
  - TPE shelters: data.taipei CSV (pid 70a6216e, scraped rid)
  - NTPC shelters: data.ntpc (UUID 25e439ab, paginated size+page)
  - River water levels: wic.gov.taipei real-time API
  - Slope warnings: data.taipei CSV (rid afdd208e)
  - Old settlements: data.taipei CSV (rid b80ee1c2)

Run from repo root:
  python scripts/generate_disaster_sql.py
"""
import csv
import io
import json
import os
import re
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ── Geocoding (ArcGIS World Geocoder, free, no key required) ──────────────────
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
    """Strip floor/unit suffix before geocoding (e.g. '202號4樓' → '202號')."""
    addr = re.sub(r"\d+~?\d*樓.*$", "", str(addr))
    addr = re.sub(r"[Bb]\d+.*$", "", addr)
    return addr.strip()


def _fetch_geocode(clean_addr):
    """Geocode one pre-cleaned address; stores result in _geocode_cache."""
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
    """Geocode a list of raw addresses concurrently; saves results to disk cache."""
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
                if done % 500 == 0:
                    print(f"    {done}/{len(pending)} done...")
        _save_geocode_cache()
    else:
        print(f"  {label}: {len(unique)} addresses all cached")


def geocode_or_fallback(address, fallback_lng, fallback_lat):
    """Return ArcGIS-geocoded (lng, lat) or fall back to district centroid."""
    clean = _clean_addr(address)
    if clean:
        with _cache_lock:
            cached = _geocode_cache.get(clean)
        if cached:
            return cached[0], cached[1]
    return fallback_lng, fallback_lat



random.seed(42)

MAPDATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Taipei-City-Dashboard-FE", "public", "mapData")
)
SQL_OUT = "/tmp/disaster_data.sql"

# ── District/Village centroid tables ─────────────────────────────────────────

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
    "汐止區": (121.6566, 25.0657), "土城區": (121.4420, 24.9731),
    "蘆洲區": (121.4746, 25.0915), "五股區": (121.4359, 25.0787),
    "泰山區": (121.4227, 25.0563), "林口區": (121.3873, 25.0876),
    "八里區": (121.4062, 25.1595), "深坑區": (121.6153, 24.9905),
    "金山區": (121.6391, 25.2233), "萬里區": (121.6784, 25.1785),
    "烏來區": (121.5462, 24.8651), "坪林區": (121.7149, 24.9312),
    "平溪區": (121.7416, 25.0174), "瑞芳區": (121.8027, 25.1027),
}

# River water level station approximate coordinates (lng, lat)
# Based on known bridge/location names in Taipei city
RIVER_STATION_COORDS = {
    "001": (121.5056, 25.0756),  # 承德橋 — 淡水河
    "003": (121.5636, 25.0826),  # 陽光橋 — 基隆河
    "021": (121.5046, 25.1182),  # 磺捷橋 — 磺溪
    "022": (121.5299, 25.0543),  # 三合橋 — 大安溪
    "023": (121.4922, 25.1353),  # 大度路無名橋 — 北投
    "024": (121.5637, 25.0777),  # 民權橋 — 基隆河
    "025": (121.5594, 24.9930),  # 家驊橋 — 景美溪
    "026": (121.5760, 24.9820),  # 指南溪斷面5
    "027": (121.5509, 24.9934),  # 胡適橋 — 景美溪
    "028": (121.6073, 25.0523),  # 南港橋 — 基隆河
    "029": (121.6496, 25.0657),  # 汐湖二橋 — 汐止
    "030": (121.5437, 25.0502),  # 撫遠擋水牆 — 松山
    "031": (121.5490, 25.0584),  # 彩虹橋 — 基隆河
    "032": (121.5028, 25.1066),  # 濟賢橋 — 北投磺溪
    "033": (121.5243, 25.0940),  # 忠三街橋 — 士林
    "034": (121.6156, 25.0347),  # 雄獅橋 — 南港
    "035": (121.5489, 24.9710),  # 玉惜橋 — 新店
    "036": (121.4594, 25.1175),  # 關渡碼頭停車場
    "037": (121.5075, 25.0209),  # 華中橋 — 新店溪
    "038": (121.5037, 25.0980),  # 洲美大橋
    "039": (121.4959, 25.1103),  # 中港河上游 — 北投
    "040": (121.4939, 25.1050),  # 中港河下游
    "041": (121.5926, 25.0687),  # 東湖國中上游 — 內湖
    "042": (121.5930, 25.0680),  # 東湖國中下游
    "057": (121.6477, 24.9948),  # 南深橋 — 深坑
    "058": (121.5127, 25.0137),  # 婆婆橋 — 新店溪
    "059": (121.5168, 25.0081),  # 永和橋 — 永和
    "060": (121.5243, 25.1130),  # 薇閣 — 天母
    "401": (121.5590, 25.0350),  # 望星橋
    "403": (121.4990, 25.1220),  # 中和橋 — 磺溪
    "404": (121.5046, 25.1050),  # 磺溪橋
}


def jitter(lng, lat, radius=0.006):
    return (
        lng + random.uniform(-radius, radius),
        lat + random.uniform(-radius, radius),
    )


def district_coords(district, city="taipei"):
    table = TPE_DISTRICTS if city == "taipei" else NTPC_DISTRICTS
    if not district:
        return jitter(121.5654, 25.0330) if city == "taipei" else jitter(121.4634, 25.0136)
    if district in table:
        return jitter(*table[district])
    for k, v in table.items():
        if district in k or k in district:
            return jitter(*v)
    return jitter(121.5654, 25.0330) if city == "taipei" else jitter(121.4634, 25.0136)


def q(s):
    """Escape single quotes for SQL string."""
    return str(s or "").replace("'", "''")


def bool_val(s):
    return "TRUE" if str(s).strip() in ("是", "1", "true", "True", "Y") else "FALSE"




# ── 1. TPE Shelters (臺北市防空避難處所清冊) ──────────────────────────────────
# API: https://data.taipei/api/v1/dataset/ffad9f86-a4f9-4743-8f18-632557d2e887
# Fields: 地址, 面積(m²), 容留人數, 是否優先緊急避難
# Note: no disaster-type suitability fields; no separate name field (use address)
# District parsed from address "臺北市{district}{rest}"

def build_shelter_tpe():
    print("Fetching TPE shelters (臺北市防空避難處所清冊, paginated)...")
    base_url = "https://data.taipei/api/v1/dataset/ffad9f86-a4f9-4743-8f18-632557d2e887"
    rows = []
    offset = 0
    limit = 1000
    while True:
        resp = requests.get(
            base_url,
            params={"scope": "resourceAquire", "limit": limit, "offset": offset},
            timeout=30,
        ).json()
        batch = resp["result"]["results"]
        rows.extend(batch)
        print(f"  offset={offset}: {len(batch)} records (total {len(rows)})")
        if len(batch) < limit:
            break
        offset += limit
    print(f"  Total TPE shelters: {len(rows)}")
    batch_geocode([r.get("地址", "") for r in rows], label="TPE shelters")

    sql_rows = []
    features = []
    for r in rows:
        address = r.get("地址", "")
        m = re.search(r"臺北市(\w+區)", address)
        district = m.group(1) if m else ""

        person = round(float(str(r.get("容留人數") or "0").strip() or 0))
        indoor = float(str(r.get("面積") or "0").strip() or 0)
        standing = bool_val(r.get("是否優先緊急避難", ""))
        suit_weak = bool_val(r.get("是否依建築物無障礙設施設計規範檢討", ""))

        lng, lat = geocode_or_fallback(address, *district_coords(district, "taipei"))

        sql_rows.append(
            f"('{q(address)}','{q(district)}','','{q(address)}'"
            f",{person},{indoor}"
            f",FALSE,FALSE,FALSE,FALSE,{suit_weak},{standing}"
            f",{lat},{lng},NOW())"
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": address,
                "district": district,
                "village": "",
                "address": address,
                "person": person,
                "suit_flood": False,
                "suit_earthquake": False,
                "suit_mudflow": False,
                "suit_tsunami": False,
                "suit_weak": suit_weak == "TRUE",
                "standing": standing == "TRUE",
                "primary_type": "general",
                "city": "taipei",
            }
        })

    sql = "TRUNCATE TABLE disaster_shelter_tpe;\n"
    sql += "INSERT INTO disaster_shelter_tpe (name,district,village,address,person,indoor_area,suit_flood,suit_mudflow,suit_earthquake,suit_tsunami,suit_weak,standing_shelter,lat,lng,data_time) VALUES\n"
    sql += ",\n".join(sql_rows) + ";\n"
    return sql, features


def build_shelter():
    print("Fetching NTPC shelters (paginated)...")
    uuid = "25e439ab-49e7-4e5e-85ce-a25c13fd2770"
    records = []
    page = 0
    page_size = 30
    while True:
        batch = requests.get(
            f"https://data.ntpc.gov.tw/api/datasets/{uuid}/json",
            params={"size": page_size, "page": page},
            timeout=30
        ).json()
        if not batch:
            break
        records.extend(batch)
        print(f"  Page {page}: {len(batch)} records (total {len(records)})")
        if len(batch) < page_size:
            break
        page += 1
    print(f"  Total NTPC shelters: {len(records)}")
    batch_geocode([r.get("address", "") for r in records], label="NTPC shelters")

    sql_rows = []
    features = []
    for r in records:
        district = r.get("district", "")
        village = r.get("village", "")
        lng, lat = geocode_or_fallback(r.get("address", ""), *district_coords(district, "newtaipei"))
        person = round(float(r.get("person") or 0))
        indoor = float("".join(c for c in str(r.get("floorspacebuildingothers_area") or "0") if c.isdigit() or c == ".") or 0)

        sql_rows.append(
            f"('{q(r.get('name',''))}','{q(district)}','{q(village)}',"
            f"'{q(r.get('address',''))}',{person},{indoor},"
            f"{bool_val(r.get('suit_for_flood'))},{bool_val(r.get('suit_for_mudflow'))},"
            f"{bool_val(r.get('suit_for_eqrthquake'))},{bool_val(r.get('suit_for_tsunami'))},"
            f"{bool_val(r.get('suit_for_weak'))},{bool_val(r.get('standing_shelter'))},"
            f"{lat},{lng},NOW())"
        )
        # disaster type label for map color
        types = []
        if r.get("suit_for_flood") == "是": types.append("flood")
        if r.get("suit_for_eqrthquake") == "是": types.append("earthquake")
        if r.get("suit_for_mudflow") == "是": types.append("mudflow")
        if r.get("suit_for_tsunami") == "是": types.append("tsunami")
        primary_type = types[0] if types else "general"

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": r.get("name", ""),
                "district": district,
                "village": village,
                "address": r.get("address", ""),
                "person": person,
                "indoor_area": indoor,
                "suit_flood": r.get("suit_for_flood") == "是",
                "suit_earthquake": r.get("suit_for_eqrthquake") == "是",
                "suit_mudflow": r.get("suit_for_mudflow") == "是",
                "suit_tsunami": r.get("suit_for_tsunami") == "是",
                "suit_weak": r.get("suit_for_weak") == "是",
                "standing": r.get("standing_shelter") == "是",
                "primary_type": primary_type,
                "city": "newtaipei",
            }
        })

    sql = "TRUNCATE TABLE disaster_shelter_ntpc;\n"
    sql += "INSERT INTO disaster_shelter_ntpc (name,district,village,address,person,indoor_area,suit_flood,suit_mudflow,suit_earthquake,suit_tsunami,suit_weak,standing_shelter,lat,lng,data_time) VALUES\n"
    sql += ",\n".join(sql_rows) + ";\n"
    return sql, features


# ── 3. River Water Level ──────────────────────────────────────────────────────

def build_river():
    print("Fetching river water levels...")
    url = "https://wic.gov.taipei/OpenData/API/Water/Get?stationNo=&loginId=river&dataKey=9E2648AA"
    data = requests.get(url, timeout=30).json()
    records = data.get("data", [])
    print(f"  Got {len(records)} stations")

    sql_rows = []
    features = []
    for r in records:
        sno = r.get("stationNo", "")
        sname = r.get("stationName", "")
        level = float(r.get("levelOut") or 0)
        rec_time = r.get("recTime", "")

        # Get hardcoded coordinates
        coords = RIVER_STATION_COORDS.get(sno.lstrip("0").zfill(3), None)
        if coords is None:
            coords = RIVER_STATION_COORDS.get(sno, None)
        if coords is None:
            coords = (121.5654, 25.0330)  # Taipei center fallback

        lng, lat = coords

        sql_rows.append(
            f"('{q(sno)}','{q(sname)}',{level},'{q(rec_time)}',{lat},{lng},NOW())"
        )

        # Classify alert level
        if level < 0:
            alert = "low"
        elif level < 3:
            alert = "normal"
        elif level < 6:
            alert = "watch"
        elif level < 10:
            alert = "warning"
        else:
            alert = "danger"

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "station_no": sno,
                "name": sname,
                "level_out": level,
                "rec_time": rec_time,
                "alert": alert,
                "city": "taipei",
            }
        })

    sql = "TRUNCATE TABLE river_water_level_tpe;\n"
    sql += "INSERT INTO river_water_level_tpe (station_no,station_name,level_out,rec_time,lat,lng,data_time) VALUES\n"
    sql += ",\n".join(sql_rows) + ";\n"
    return sql, features


# ── 4. Slope Warnings ────────────────────────────────────────────────────────

def build_slope():
    print("Fetching slope warnings...")
    url = "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=afdd208e-fc71-4c07-a489-eaa9c742b27a"
    text = requests.get(url, timeout=30).text.lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"  Got {len(rows)} slope records")

    sql_rows = []
    features = []
    for r in rows:
        district = r.get("行政區", "")
        village = r.get("村里", "")
        yellow = int(r.get("黃色警戒雨量值（mm／24hr）") or 0)
        red = int(r.get("紅色警戒雨量值（mm／24hr）") or 0)
        lng, lat = district_coords(district, "taipei")

        sql_rows.append(
            f"('{q(r.get('列管邊坡編號',''))}','{q(district)}','{q(village)}',"
            f"'{q(r.get('列管邊坡位名稱',''))}',{yellow},{red},"
            f"'{q(r.get('參考雨量站',''))}',{lat},{lng},NOW())"
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "slope_id": r.get("列管邊坡編號", ""),
                "name": r.get("列管邊坡位名稱", ""),
                "district": district,
                "village": village,
                "yellow_threshold": yellow,
                "red_threshold": red,
                "reference_station": r.get("參考雨量站", ""),
                "person_count": 0,
                "risk_type": "slope",
                "city": "taipei",
            }
        })

    sql = "TRUNCATE TABLE slope_warning_tpe;\n"
    sql += "INSERT INTO slope_warning_tpe (slope_id,district,village,name,yellow_threshold,red_threshold,reference_station,lat,lng,data_time) VALUES\n"
    sql += ",\n".join(sql_rows) + ";\n"
    return sql, features


# ── 5. Old Settlements ───────────────────────────────────────────────────────

def build_settlement():
    print("Fetching old settlement warnings...")
    url = "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=b80ee1c2-5af7-4f6e-9cae-6813f19608f0"
    text = requests.get(url, timeout=30).text.lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"  Got {len(rows)} settlement records")

    sql_rows = []
    features = []
    for r in rows:
        district = r.get("行政區", "")
        village = r.get("村里", "")
        person = int(r.get("保全住戶人數") or 0)
        household = int(r.get("保全住戶戶數") or 0)
        yellow = int(r.get("黃色警戒雨量值（mm／24hr）") or 0)
        red = int(r.get("紅色警戒雨量值（mm／24hr）") or 0)
        lng, lat = district_coords(district, "taipei")

        sql_rows.append(
            f"('{q(district)}','{q(village)}',"
            f"'{q(r.get('山坡地老舊聚落編號及名稱',''))}','{q(r.get('參考雨量站',''))}'"
            f",{person},{household},{yellow},{red},{lat},{lng},NOW())"
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name": r.get("山坡地老舊聚落編號及名稱", ""),
                "district": district,
                "village": village,
                "person_count": person,
                "household_count": household,
                "yellow_threshold": yellow,
                "red_threshold": red,
                "risk_type": "settlement",
                "city": "taipei",
            }
        })

    sql = "TRUNCATE TABLE old_settlement_tpe;\n"
    sql += "INSERT INTO old_settlement_tpe (district,village,name,reference_station,person_count,household_count,yellow_threshold,red_threshold,lat,lng,data_time) VALUES\n"
    sql += ",\n".join(sql_rows) + ";\n"
    return sql, features


# ── GeoJSON export ────────────────────────────────────────────────────────────

def export_geojson(features, filename):
    path = os.path.join(MAPDATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
    print(f"  -> {filename}: {len(features)} features")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Generating Disaster Resilience SQL + GeoJSON ===")
    _load_geocode_cache()

    shelter_tpe_sql, shelter_tpe_features = build_shelter_tpe()
    shelter_ntpc_sql, shelter_ntpc_features = build_shelter()
    river_sql, river_features = build_river()
    slope_sql, slope_features = build_slope()
    settlement_sql, settlement_features = build_settlement()

    # Write combined SQL
    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("-- Disaster Resilience Data Injection\n")
        f.write("-- Run: docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/disaster_data.sql\n\n")
        f.write(shelter_tpe_sql + "\n")
        f.write(shelter_ntpc_sql + "\n")
        f.write(river_sql + "\n")
        f.write(slope_sql + "\n")
        f.write(settlement_sql + "\n")
        f.write("SELECT 'Disaster data injected successfully' AS result;\n")
    print(f"\nSQL written to {SQL_OUT}")

    # Write GeoJSON files
    print("\nWriting GeoJSON files...")
    # disaster_shelter.geojson: TPE-only (loaded by taipei city view)
    # disaster_shelter_ntpc.geojson: NTPC-only (loaded by metrotaipei city view)
    export_geojson(shelter_tpe_features, "disaster_shelter.geojson")
    export_geojson(shelter_ntpc_features, "disaster_shelter_ntpc.geojson")
    export_geojson(river_features, "river_water_level.geojson")
    # Combine slope + settlement into one map layer
    slope_risk_features = slope_features + settlement_features
    export_geojson(slope_risk_features, "slope_risk_tpe.geojson")

    print("\nDone. Next steps:")
    print("  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/disaster_data.sql")
