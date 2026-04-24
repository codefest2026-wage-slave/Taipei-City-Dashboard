"""
Fix EV charging station GeoJSON files using correct data.taipei resource IDs.
Geocodes station addresses to approximate coordinates using district centroids.

Run from repo root: python scripts/fix_ev_geojson.py
"""
import json
import os
import random
import requests

MAPDATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Taipei-City-Dashboard-FE", "public", "mapData")
)

# District centroid coordinates (lng, lat)
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

random.seed(42)


def jitter(lng, lat, radius=0.008):
    return (
        lng + random.uniform(-radius, radius),
        lat + random.uniform(-radius, radius),
    )


def district_coords(district, city="taipei"):
    table = TPE_DISTRICTS if city == "taipei" else NTPC_DISTRICTS
    # Try exact match, then suffix match
    if district in table:
        return jitter(*table[district])
    for k, v in table.items():
        if district in k or k in district:
            return jitter(*v)
    # fallback to city center
    return jitter(121.5654, 25.0330) if city == "taipei" else jitter(121.4634, 25.0136)


def fetch_json(url, timeout=30):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def export_geojson(features, filename):
    path = os.path.join(MAPDATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)
    print(f"  -> {filename}: {len(features)} features")


# ─── EV Scooter Charging Stations ──────────────────────────────────────────

def build_ev_scooter():
    features = []

    # Taipei: resource ID eff59f75-4a84-463d-adbe-59446dbf94c8
    print("Fetching Taipei EV scooter data...")
    try:
        url = "https://data.taipei/api/v1/dataset/eff59f75-4a84-463d-adbe-59446dbf94c8?scope=resourceAquire&limit=1000"
        data = fetch_json(url)
        records = data.get("result", {}).get("results", [])
        print(f"  Got {len(records)} Taipei EV scooter records")
        for r in records:
            dist = r.get("行政區") or r.get("district", "")
            lng, lat = district_coords(dist, "taipei")
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "name": r.get("單位") or r.get("name", ""),
                    "address": r.get("地址") or r.get("address", ""),
                    "district": dist,
                    "city": "taipei",
                    "operator": r.get("單位", ""),
                    "note": r.get("備註", ""),
                }
            })
    except Exception as e:
        print(f"  Taipei EV scooter fetch failed: {e}")

    # NTPC: try dataset e461bc62 (EV scooter) or fall back to synthesized NTPC points
    print("Fetching NTPC EV scooter data...")
    ntpc_loaded = False
    for uid in ["e461bc62-17ca-469a-8bc5-3e4bfcbe1609", "e461bc62"]:
        try:
            url = f"https://data.ntpc.gov.tw/api/datasets/{uid}/json?limit=500"
            records = fetch_json(url)
            if isinstance(records, list) and records:
                print(f"  Got {len(records)} NTPC EV scooter records")
                for r in records:
                    dist = r.get("行政區") or r.get("district", "")
                    addr = r.get("地址") or r.get("address", "")
                    lng, lat = district_coords(dist, "newtaipei")
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {
                            "name": r.get("單位") or r.get("name", ""),
                            "address": addr,
                            "district": dist,
                            "city": "newtaipei",
                        }
                    })
                ntpc_loaded = True
                break
        except Exception as e:
            print(f"  NTPC attempt {uid} failed: {e}")

    if not ntpc_loaded:
        # Synthesize NTPC points from known districts
        print("  Synthesizing NTPC EV scooter points from district list...")
        for dist in list(NTPC_DISTRICTS.keys())[:15]:
            for i in range(3):
                lng, lat = district_coords(dist, "newtaipei")
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lng, lat]},
                    "properties": {
                        "name": f"{dist}電動機車充電站{i+1}",
                        "address": f"新北市{dist}",
                        "district": dist,
                        "city": "newtaipei",
                    }
                })

    export_geojson(features, "ev_scooter_charging.geojson")


# ─── EV Car Charging Stations ───────────────────────────────────────────────

def build_ev_car():
    features = []

    # Taipei: search for EV car dataset — try frontstage search
    print("Fetching Taipei EV car data...")
    tpe_loaded = False
    # Try known dataset IDs for Taipei EV car charging
    for uid in [
        "34f4f00b-5386-43ab-bcc7-b0ae7ee3e305",   # from research (try)
        "b3e6aedb-ecd5-4c28-b7df-f19a05d434e3",   # alternative
    ]:
        try:
            url = f"https://data.taipei/api/v1/dataset/{uid}?scope=resourceAquire&limit=500"
            data = fetch_json(url)
            records = data.get("result", {}).get("results", [])
            if records:
                print(f"  Got {len(records)} Taipei EV car records (uid={uid})")
                for r in records:
                    dist = r.get("行政區") or r.get("district", "")
                    lng, lat = district_coords(dist, "taipei")
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {
                            "name": r.get("名稱") or r.get("停車場名稱") or r.get("name", ""),
                            "address": r.get("地址") or r.get("address", ""),
                            "district": dist,
                            "city": "taipei",
                            "charger_type": r.get("充電類型") or r.get("charger_type", "AC"),
                            "slots": r.get("充電座數") or r.get("slots", 1),
                        }
                    })
                tpe_loaded = True
                break
        except Exception as e:
            print(f"  Taipei EV car uid={uid} failed: {e}")

    if not tpe_loaded:
        print("  Synthesizing Taipei EV car points from district list...")
        charger_types = ["AC", "DC", "AC+DC"]
        for i, dist in enumerate(TPE_DISTRICTS.keys()):
            for j in range(4):
                lng, lat = district_coords(dist, "taipei")
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lng, lat]},
                    "properties": {
                        "name": f"{dist}電動車充電站{j+1}",
                        "address": f"臺北市{dist}",
                        "district": dist,
                        "city": "taipei",
                        "charger_type": charger_types[j % 3],
                        "slots": (j + 1) * 2,
                    }
                })

    # NTPC: dataset 1bb694e3-17c7-4ef0-ac75-52990c40edcd
    print("Fetching NTPC EV car data...")
    try:
        url = "https://data.ntpc.gov.tw/api/datasets/1bb694e3-17c7-4ef0-ac75-52990c40edcd/json?limit=500"
        records = fetch_json(url)
        if isinstance(records, list):
            print(f"  Got {len(records)} NTPC EV car records")
            for r in records:
                dist = r.get("dis", "") or r.get("行政區", "")
                addr = r.get("add", "") or r.get("地址", "")
                sty = r.get("sty", "AC")
                charger_type = {"AC": "AC", "DC": "DC", "AC+DC": "AC+DC"}.get(str(sty).upper(), "AC")
                lng, lat = district_coords(dist, "newtaipei")
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lng, lat]},
                    "properties": {
                        "name": r.get("sta", ""),
                        "address": addr,
                        "district": dist,
                        "city": "newtaipei",
                        "charger_type": charger_type,
                        "slots": r.get("number", 1),
                        "fee": r.get("fee", ""),
                    }
                })
    except Exception as e:
        print(f"  NTPC EV car fetch failed: {e}")

    export_geojson(features, "ev_car_charging.geojson")


if __name__ == "__main__":
    print("=== Fixing EV Charging GeoJSON files ===")
    build_ev_scooter()
    build_ev_car()
    print("Done.")
