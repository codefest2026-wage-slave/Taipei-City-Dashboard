"""
DIS-D2-1: 將雙北社區照顧關懷據點注入 dashboard DB
  TPE: docs/assets/DIS-D2-1/tpe_community_care.csv (514 筆，PDF 解析)
  NTPC: docs/assets/DIS-D2-1/ntpc_community_care.json (636 筆，data.ntpc API)

輸出表：
  community_care_centers_tpe (id, name, district, village, address, type, phone, lng, lat)
  community_care_centers_ntpc (同欄位)

Run:
  python3 scripts/load_community_care_centers.py
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/community_care.sql
"""
import csv
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(REPO, "docs/assets/DIS-D2-1")
SQL_OUT = "/tmp/community_care.sql"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".geocode_cache.json")
ARCGIS_URL = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
)

_geocode_cache = {}
_lock = threading.Lock()


def esc(s):
    if s is None:
        return "NULL"
    s = str(s).strip()
    if s == "" or s == "-":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _load_cache():
    global _geocode_cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            _geocode_cache = json.load(f)


def _save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_geocode_cache, f, ensure_ascii=False)


def _clean_addr(addr):
    addr = re.sub(r"\d+~?\d*樓.*$", "", str(addr or ""))
    addr = re.sub(r"[Bb]\d+.*$", "", addr)
    return addr.strip()


def _fetch(clean):
    with _lock:
        if clean in _geocode_cache:
            return
    result = None
    try:
        r = requests.get(
            ARCGIS_URL,
            params={"SingleLine": clean, "f": "json", "outSR": '{"wkid":4326}', "maxLocations": 1},
            timeout=10,
        )
        r.raise_for_status()
        cands = r.json().get("candidates", [])
        if cands and cands[0].get("score", 0) >= 80:
            loc = cands[0]["location"]
            result = [loc["x"], loc["y"]]
    except Exception:
        pass
    with _lock:
        _geocode_cache[clean] = result


def batch_geocode(addrs, label):
    unique = list({_clean_addr(a) for a in addrs if a and _clean_addr(a)})
    with _lock:
        pending = [a for a in unique if a not in _geocode_cache]
    if not pending:
        print(f"  {label}: {len(unique)} cached", file=sys.stderr)
        return
    print(f"  {label}: geocoding {len(pending)} new ({len(unique) - len(pending)} cached)", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=20) as ex:
        list(as_completed([ex.submit(_fetch, a) for a in pending]))
    _save_cache()


def geocode(addr):
    clean = _clean_addr(addr)
    with _lock:
        c = _geocode_cache.get(clean)
    return (c[0], c[1]) if c else (None, None)


def parse_tpe():
    rows = []
    path = os.path.join(ASSETS, "tpe_community_care.csv")
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            addr = (r.get("據點地址") or "").strip()
            if not addr:
                continue
            rows.append({
                "name": (r.get("據點名稱") or "").strip(),
                "district": (r.get("行政區") or "").strip(),
                "village": (r.get("里別") or "").strip(),
                "address": addr,
                "type": (r.get("據點類型") or "").replace(" ", "").replace("\n", "").strip(),
                "phone": (r.get("聯絡電話") or "").strip(),
            })
    return rows


def parse_ntpc():
    rows = []
    path = os.path.join(ASSETS, "ntpc_community_care.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for r in data:
        addr = (r.get("address") or "").strip()
        if not addr:
            continue
        rows.append({
            "name": (r.get("title") or "").strip(),
            "district": (r.get("town") or "").strip(),
            "village": "",   # NTPC API 無里別
            "address": addr,
            "type": "社區照顧關懷據點",
            "phone": "",
        })
    return rows


def write_sql(out, rows, table):
    out.write(f"\n-- ── {table}: {len(rows)} 據點 ──\n")
    out.write(f"DROP TABLE IF EXISTS {table};\n")
    out.write(
        f"""CREATE TABLE {table} (
    id SERIAL PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    district VARCHAR(20),
    village VARCHAR(50),
    address VARCHAR(400),
    type VARCHAR(100),
    phone VARCHAR(50),
    lng DOUBLE PRECISION,
    lat DOUBLE PRECISION
);
"""
    )
    if not rows:
        return
    BATCH = 200
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        vals = []
        for r in chunk:
            lng, lat = geocode(r["address"])
            vals.append(
                "({n},{d},{v},{a},{t},{p},{lng},{lat})".format(
                    n=esc(r["name"]), d=esc(r["district"]), v=esc(r["village"]),
                    a=esc(r["address"]), t=esc(r["type"]), p=esc(r["phone"]),
                    lng=str(lng) if lng else "NULL", lat=str(lat) if lat else "NULL",
                )
            )
        out.write(
            f"INSERT INTO {table} (name, district, village, address, type, phone, lng, lat) VALUES\n"
            + ",\n".join(vals) + ";\n"
        )
    out.write(f"CREATE INDEX idx_{table}_dv ON {table}(district, village);\n")


def main():
    _load_cache()
    print("Parsing TPE …", file=sys.stderr)
    tpe = parse_tpe()
    print(f"  TPE rows: {len(tpe)}", file=sys.stderr)

    print("Parsing NTPC …", file=sys.stderr)
    ntpc = parse_ntpc()
    print(f"  NTPC rows: {len(ntpc)}", file=sys.stderr)

    batch_geocode([r["address"] for r in tpe + ntpc], "community_care")

    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n")
        write_sql(f, tpe, "community_care_centers_tpe")
        write_sql(f, ntpc, "community_care_centers_ntpc")
        f.write("COMMIT;\n")
    print(f"\nWrote {SQL_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
