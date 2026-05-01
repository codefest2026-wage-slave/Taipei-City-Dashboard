"""
L-04-1 ETL：將下列三組資料注入 dashboard DB
  1. 全國就業服務據點 → employment_service_centers_tpe / _ntpc（geocode 過的座標）
  2. 內政部村里人口 → village_population_tpe / _ntpc（每里總人口 + 年齡層）
  3. 台北家庭收支按行政區 → district_income_tpe（行政區所得）

資料來源：docs/assets/L-04-1/
  - employment_centers.csv （勞動部 47 雙北筆）
  - village_population.csv （內政部 7,753 全國，雙北 1,488 筆）
  - fi00101y15ac.csv （113 年台北 12 行政區家庭收支，Big5 編碼）

Run:
  python3 scripts/load_employment_accessibility.py
  docker exec -i postgres-data psql -U postgres -d dashboard < /tmp/employment_accessibility.sql
"""

import csv
import json
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(REPO, "docs/assets/L-04-1")
SQL_OUT = "/tmp/employment_accessibility.sql"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".geocode_cache.json")

ARCGIS_URL = (
    "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
)
_geocode_cache: dict = {}
_cache_lock = threading.Lock()


def esc(s):
    if s is None:
        return "NULL"
    s = str(s).strip()
    if s == "" or s.lower() == "nan" or s == "-":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


# ─── geocode helpers (same as scripts/generate_recheck_priority_geojson.py) ───
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
    with _cache_lock:
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
    with _cache_lock:
        _geocode_cache[clean] = result


def batch_geocode(addrs, label):
    unique = list({_clean_addr(a) for a in addrs if a and _clean_addr(a)})
    with _cache_lock:
        pending = [a for a in unique if a not in _geocode_cache]
    if not pending:
        print(f"  {label}: {len(unique)} addresses cached", file=sys.stderr)
        return
    print(f"  {label}: geocoding {len(pending)} new", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=20) as ex:
        list(as_completed([ex.submit(_fetch, a) for a in pending]))
    _save_cache()


def geocode(addr):
    clean = _clean_addr(addr)
    with _cache_lock:
        cached = _geocode_cache.get(clean)
    return cached if cached else [None, None]


# ─── 1. employment service centers ──────────────────────────────────
def parse_centers():
    rows_tpe, rows_ntpc = [], []
    path = os.path.join(ASSETS, "employment_centers.csv")
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            name = (r.get("名稱") or "").strip()
            addr = (r.get("地址") or "").strip()
            phone = (r.get("電話") or "").strip()
            hours = (r.get("服務時間") or "").strip()
            if not name or not addr:
                continue
            row = {"name": name, "address": addr, "phone": phone, "hours": hours}
            if addr.startswith("臺北市") or addr.startswith("台北市"):
                rows_tpe.append(row)
            elif addr.startswith("新北市"):
                rows_ntpc.append(row)
    return rows_tpe, rows_ntpc


def write_centers_sql(out, rows, table):
    out.write(f"\n-- ── {table}: {len(rows)} 雙北就服站 ──\n")
    out.write(f"DROP TABLE IF EXISTS {table};\n")
    out.write(
        f"""CREATE TABLE {table} (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    address VARCHAR(300),
    phone VARCHAR(50),
    hours VARCHAR(200),
    lng DOUBLE PRECISION,
    lat DOUBLE PRECISION
);
"""
    )
    if not rows:
        return
    vals = []
    for r in rows:
        lng, lat = geocode(r["address"])
        vals.append(
            "({n},{a},{p},{h},{lng},{lat})".format(
                n=esc(r["name"]),
                a=esc(r["address"]),
                p=esc(r["phone"]),
                h=esc(r["hours"]),
                lng=str(lng) if lng else "NULL",
                lat=str(lat) if lat else "NULL",
            )
        )
    out.write(f"INSERT INTO {table} (name, address, phone, hours, lng, lat) VALUES\n")
    out.write(",\n".join(vals))
    out.write(";\n")


# ─── 2. village population ──────────────────────────────────────────
AGE_KEYS = []  # filled at parse time


def parse_villages():
    """yield dicts: {site_id, district, village, hh, total, midage, elder} for 雙北 only."""
    path = os.path.join(ASSETS, "village_population.csv")
    rows_tpe, rows_ntpc = [], []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            district_full = r.get("區域別") or ""
            if not (district_full.startswith("臺北市") or district_full.startswith("新北市")):
                continue
            village = (r.get("村里") or "").strip()
            if not village:
                continue
            site_id = (r.get("區域別代碼") or "").strip()
            try:
                hh = int(r.get("戶數") or 0)
                total = int(r.get("人口數") or 0)
            except ValueError:
                continue
            if total == 0:
                continue
            # Sum 45-64 (中高齡) and 65+ (高齡)
            midage = 0
            elder = 0
            for age in range(45, 65):
                for sex in ("男", "女"):
                    try:
                        midage += int(r.get(f"{age}歲-{sex}", 0) or 0)
                    except ValueError:
                        pass
            for age in range(65, 100):
                for sex in ("男", "女"):
                    try:
                        elder += int(r.get(f"{age}歲-{sex}", 0) or 0)
                    except ValueError:
                        pass
            for sex in ("男", "女"):
                try:
                    elder += int(r.get(f"100歲以上-{sex}", 0) or 0)
                except (ValueError, TypeError):
                    pass
            # district = full district name (e.g. "臺北市中正區")
            # Strip city prefix to get just district
            if district_full.startswith("臺北市"):
                district = district_full[3:].strip()
                rows_tpe.append({
                    "site_id": site_id, "district": district, "village": village,
                    "hh": hh, "total": total, "midage": midage, "elder": elder,
                })
            elif district_full.startswith("新北市"):
                district = district_full[3:].strip()
                rows_ntpc.append({
                    "site_id": site_id, "district": district, "village": village,
                    "hh": hh, "total": total, "midage": midage, "elder": elder,
                })
    return rows_tpe, rows_ntpc


def write_villages_sql(out, rows, table):
    out.write(f"\n-- ── {table}: {len(rows)} 里 ──\n")
    out.write(f"DROP TABLE IF EXISTS {table};\n")
    out.write(
        f"""CREATE TABLE {table} (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(20),
    district VARCHAR(20) NOT NULL,
    village VARCHAR(50) NOT NULL,
    households INTEGER,
    total_pop INTEGER,
    midage_pop INTEGER,    -- 45-64 中高齡
    elder_pop INTEGER      -- 65+ 高齡
);
"""
    )
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        vals = [
            "({sid},{d},{v},{hh},{t},{m},{e})".format(
                sid=esc(r["site_id"]), d=esc(r["district"]), v=esc(r["village"]),
                hh=r["hh"], t=r["total"], m=r["midage"], e=r["elder"],
            )
            for r in chunk
        ]
        out.write(
            f"INSERT INTO {table} (site_id, district, village, households, total_pop, midage_pop, elder_pop) VALUES\n"
            + ",\n".join(vals) + ";\n"
        )
    out.write(f"CREATE INDEX idx_{table}_dv ON {table}(district, village);\n")


# ─── 3. district income (Taipei only, Big5 file) ────────────────────
def parse_district_income():
    """Parse fi00101y15ac.csv (113 年, Big5)."""
    path = os.path.join(ASSETS, "fi00101y15ac.csv")
    rows = []
    with open(path, encoding="big5", errors="ignore") as f:
        reader = csv.DictReader(f)
        # header keys: 年別, 行政區, 家庭戶數[戶], 每戶人數, 每戶成年人數,
        # 每戶就業人數, 每戶所得收入者人數, [一]所得收入總計[NT], …, 可支配所得[NT], …
        for r in reader:
            year = (r.get("年別") or "").strip()
            district = (r.get("行政區") or "").strip()
            if not district or district == "總計":
                continue
            if not year.endswith("年"):
                continue
            try:
                households = int((r.get("家庭戶數[戶]") or "0").replace(",", ""))
                pop_per_hh = float(r.get("每戶人數") or 0)
                worker_per_hh = float(r.get("每戶就業人數") or 0)
                disposable = int((r.get("可支配所得[NT]") or "0").replace(",", ""))
                consumption = int((r.get("消費支出[NT]") or "0").replace(",", ""))
                income_total = int((r.get("所得總額[NT]") or "0").replace(",", ""))
            except ValueError:
                continue
            avg_disposable_per_hh = disposable / households if households else 0
            rows.append({
                "year": year, "district": district, "households": households,
                "pop_per_hh": pop_per_hh, "worker_per_hh": worker_per_hh,
                "avg_disposable_per_hh": int(avg_disposable_per_hh),
                "disposable_total": disposable, "consumption_total": consumption,
                "income_total": income_total,
            })
    return rows


def write_district_income_sql(out, rows):
    out.write(f"\n-- ── district_income_tpe: {len(rows)} 行政區 ──\n")
    out.write("DROP TABLE IF EXISTS district_income_tpe;\n")
    out.write(
        """CREATE TABLE district_income_tpe (
    id SERIAL PRIMARY KEY,
    year VARCHAR(10),
    district VARCHAR(20) NOT NULL,
    households INTEGER,
    pop_per_household NUMERIC(5,2),
    worker_per_household NUMERIC(5,2),
    avg_disposable_per_household BIGINT,
    disposable_total BIGINT,
    consumption_total BIGINT,
    income_total BIGINT
);
"""
    )
    if not rows:
        return
    vals = [
        "({y},{d},{hh},{pph},{wph},{adph},{dt},{ct},{it})".format(
            y=esc(r["year"]), d=esc(r["district"]), hh=r["households"],
            pph=r["pop_per_hh"], wph=r["worker_per_hh"],
            adph=r["avg_disposable_per_hh"], dt=r["disposable_total"],
            ct=r["consumption_total"], it=r["income_total"],
        )
        for r in rows
    ]
    out.write(
        "INSERT INTO district_income_tpe (year, district, households, pop_per_household, "
        "worker_per_household, avg_disposable_per_household, disposable_total, "
        "consumption_total, income_total) VALUES\n"
        + ",\n".join(vals) + ";\n"
    )


def main():
    _load_cache()

    print("1) Parsing employment centers …", file=sys.stderr)
    centers_tpe, centers_ntpc = parse_centers()
    print(f"   TPE={len(centers_tpe)}, NTPC={len(centers_ntpc)}", file=sys.stderr)
    batch_geocode([c["address"] for c in centers_tpe + centers_ntpc], "centers")

    print("2) Parsing village population …", file=sys.stderr)
    villages_tpe, villages_ntpc = parse_villages()
    print(f"   TPE villages={len(villages_tpe)}, NTPC villages={len(villages_ntpc)}", file=sys.stderr)

    print("3) Parsing district income (TPE only) …", file=sys.stderr)
    district_rows = parse_district_income()
    print(f"   TPE districts={len(district_rows)}", file=sys.stderr)

    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n")
        write_centers_sql(f, centers_tpe, "employment_service_centers_tpe")
        write_centers_sql(f, centers_ntpc, "employment_service_centers_ntpc")
        write_villages_sql(f, villages_tpe, "village_population_tpe")
        write_villages_sql(f, villages_ntpc, "village_population_ntpc")
        write_district_income_sql(f, district_rows)
        f.write("COMMIT;\n")
    print(f"\nWrote → {SQL_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
