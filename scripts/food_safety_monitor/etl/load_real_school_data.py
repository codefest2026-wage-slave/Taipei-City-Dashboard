#!/usr/bin/env python3
"""ETL: real school + caterer + supply chain + audit data from cloud DB.

Source:
  - DB.dashboard.school_meal_ingredient_records (school × caterer × ingredient)
  - DB.dashboard.food_safety_inspection_metrotaipei (audit / inspection records)
  - public/mapData/metrotaipei_town.geojson (district polygons → centroids)
  - scripts/food_safety_monitor/snapshots/{meal,dish}_scores.csv (nutrition AI)

Target (校內食安地圖 / Phase-1 real-data integration):
  Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/
    schools.geojson, suppliers.geojson, supply_chain.geojson,
    supplier_audits.json, school_nutrition.json
  Taipei-City-Dashboard-FE/public/mapData/
    fsm_schools.geojson, fsm_suppliers.geojson, fsm_supply_chain.geojson

Identity:
  - school.id = real school_name (full, e.g. '新北市三峽區三峽國中')
  - supplier.id = caterer_tax_id (cleaned, e.g. '53685810')
  - supply_chain edges link by (school_id=name, supplier_id=tax_id)
  - audits keyed by caterer_tax_id

Caterer name normalization:
  caterer_name in records often has the form '統鮮美食股份有限公司(新北北大國小)'.
  We strip the trailing parenthesis ('(...)') for the canonical name AND
  use that canonical to MATCH (substring) against
  food_safety_inspection_metrotaipei.business_name.

Self-cater filter: if caterer_name == school_name OR caterer_tax_id begins
with 'F' (school code), the caterer is the school itself — skipped.

Coordinates: derived from district centroids (metrotaipei_town.geojson) +
deterministic per-feature jitter. Not a real geocoder; the supply-chain
visual concept is what matters for the demo.

Re-run after schema/data refresh:
  python3 scripts/food_safety_monitor/etl/load_real_school_data.py
"""
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT / "scripts/food_safety_monitor/.env.script"
DST_MOCK = ROOT / "Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor"
DST_MAP = ROOT / "Taipei-City-Dashboard-FE/public/mapData"
TOWN_GEOJSON = DST_MAP / "metrotaipei_town.geojson"
MEAL_CSV = ROOT / "scripts/food_safety_monitor/snapshots/meal_scores.csv"
DISH_CSV = ROOT / "scripts/food_safety_monitor/snapshots/dish_scores.csv"


def get_db():
    """Read .env.script and return psycopg2 connection to DB_DASHBOARD."""
    result = subprocess.run(
        ["bash", "-c", f"set -a; source {ENV_FILE}; env"],
        capture_output=True, text=True, check=True,
    )
    env = dict(line.split("=", 1) for line in result.stdout.split("\n") if "=" in line)
    return psycopg2.connect(
        host=env["DB_DASHBOARD_HOST"], port=env["DB_DASHBOARD_PORT"],
        user=env["DB_DASHBOARD_USER"], password=env["DB_DASHBOARD_PASSWORD"],
        dbname=env["DB_DASHBOARD_DBNAME"], sslmode=env["DB_DASHBOARD_SSLMODE"],
        connect_timeout=20,
    )


def clean_tax_id(raw):
    """Strip Excel-style ="..." wrapper from caterer_tax_id."""
    if not raw:
        return None
    m = re.match(r'\s*=?"?([0-9A-Za-z]+)"?\s*$', str(raw))
    return m.group(1) if m else str(raw).strip()


def canonical_caterer_name(raw):
    """Strip trailing '(...)' suffix from caterer_name."""
    if not raw:
        return ""
    return re.sub(r"\s*[(（][^)）]*[)）]\s*$", "", str(raw)).strip()


def school_type(name):
    if "國小" in name:
        return "elementary"
    if "國中" in name:
        return "junior_high"
    if "高中" in name or "高級中學" in name:
        return "high"
    return "other"


def jitter(seed_str, dx_max=0.005, dy_max=0.004):
    h = hashlib.md5(seed_str.encode("utf-8")).digest()
    rx = (h[0] / 255 - 0.5) * 2 * dx_max
    ry = (h[1] / 255 - 0.5) * 2 * dy_max
    return rx, ry


def polygon_centroid(coords):
    """Average of vertices of the (outer ring of the) first polygon."""
    if not coords:
        return None
    ring = coords[0]
    if not ring:
        return None
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def district_centroids():
    geo = json.loads(TOWN_GEOJSON.read_text())
    out = {}
    for f in geo["features"]:
        p = f["properties"]
        c = polygon_centroid(f["geometry"]["coordinates"])
        if c:
            out[(p["PNAME"], p["TNAME"])] = c
    return out


def address_district(address):
    """Extract (city, district) from a street address string."""
    if not address:
        return None
    m = re.search(r"(臺北市|新北市|台北市)\s*([^區市\s]{1,4}區)", address)
    if not m:
        return None
    city = m.group(1)
    if city == "台北市":
        city = "臺北市"
    return city, m.group(2)


def main():
    print("connecting to DB...")
    conn = get_db()
    cur = conn.cursor()

    # ── 1. SCHOOLS ────────────────────────────────────────────
    cur.execute("""
        SELECT DISTINCT county, district, school_name
        FROM school_meal_ingredient_records
        WHERE county IN ('臺北市','新北市')
          AND school_name IS NOT NULL
        ORDER BY county, district, school_name
    """)
    schools_rows = cur.fetchall()
    print(f"  schools: {len(schools_rows)}")

    # ── 2. CATERERS — distinct (tax_id) external (commercial) only ────
    cur.execute("""
        SELECT caterer_tax_id, caterer_name
        FROM school_meal_ingredient_records
        WHERE county IN ('臺北市','新北市')
          AND caterer_tax_id IS NOT NULL
          AND caterer_name IS NOT NULL
          AND caterer_name <> school_name
    """)
    caterer_rows = cur.fetchall()

    caterers = {}  # tax_id → {tax_id, name, raw_name}
    for tax_raw, name_raw in caterer_rows:
        tid = clean_tax_id(tax_raw)
        if not tid or tid.startswith("F"):
            continue
        canonical = canonical_caterer_name(name_raw)
        if not canonical:
            continue
        existing = caterers.get(tid)
        if existing is None or len(canonical) > len(existing["name"]):
            caterers[tid] = {"tax_id": tid, "name": canonical, "raw_name": name_raw}
    print(f"  caterers (商業 only): {len(caterers)}")

    # ── 3. SUPPLY CHAIN edges (distinct school × caterer_tax_id) ────
    cur.execute("""
        SELECT DISTINCT school_name, caterer_tax_id
        FROM school_meal_ingredient_records
        WHERE county IN ('臺北市','新北市')
          AND caterer_tax_id IS NOT NULL
          AND caterer_name IS NOT NULL
          AND caterer_name <> school_name
    """)
    edge_rows = cur.fetchall()
    edges = []
    for school_name, tax_raw in edge_rows:
        tid = clean_tax_id(tax_raw)
        if not tid or tid not in caterers:
            continue
        edges.append((school_name, tid))
    print(f"  supply chain edges: {len(edges)}")

    # ── 4. AUDITS — load all 商業業者 inspections ────
    cur.execute("""
        SELECT business_name, address, city, district, inspection_date,
               inspection_result, hazard_level, fine_amount,
               violated_law_standardized, note, inspection_item
        FROM food_safety_inspection_metrotaipei
        WHERE business_type = '商業業者'
          AND business_name IS NOT NULL
          AND inspection_date IS NOT NULL
        ORDER BY inspection_date DESC
    """)
    audits_raw = cur.fetchall()
    print(f"  audits (商業業者): {len(audits_raw)}")
    cur.close()
    conn.close()

    # ── 5. Match audits → caterer via CONTAINS ──────────────
    audits_by_caterer = {tid: [] for tid in caterers}
    canonical_to_tax = {c["name"]: tid for tid, c in caterers.items() if c["name"]}
    canonical_names = sorted(canonical_to_tax.keys(), key=lambda s: -len(s))

    matched = 0
    for biz, addr, city, dist, date, result, level, fine, law_std, note, item in audits_raw:
        biz_str = biz or ""
        for cn in canonical_names:
            if cn and cn in biz_str:
                tid = canonical_to_tax[cn]
                is_fail = result in ("不合格", "不符合規定")
                # severity: capitalize hazard_level for FAIL; "Pass" otherwise
                sev_raw = (level or "info").lower()
                if is_fail:
                    sev = sev_raw.capitalize() if sev_raw in ("critical", "high", "medium", "low") else "Medium"
                else:
                    sev = "Pass"
                audits_by_caterer[tid].append({
                    "date": date.strftime("%Y/%m/%d"),
                    "status": "FAIL" if is_fail else "PASS",
                    "severity": sev,
                    "issue": (law_std or note or item or result or "").strip()[:120],
                    "fine_amount": float(fine) if fine is not None else None,
                    "address": addr,
                    "city": city,
                    "district": dist,
                    "result_raw": result,
                    "hazard_level": level,
                })
                matched += 1
                break
    print(f"  audits matched to caterer: {matched}")

    # Sort audits desc per caterer (ORDER BY in SQL already desc; preserve)
    for tid in audits_by_caterer:
        audits_by_caterer[tid].sort(key=lambda r: r["date"], reverse=True)

    # ── 6. recent_alert per caterer ────
    # Real-data observation: school caterers are large compliant firms — the
    # "latest 3 audits any FAIL" rule (mock-era) doesn't trigger. We loosen
    # to "any historical FAIL match" so the demo surfaces actual problem
    # caterers from the public inspection record.
    caterer_alert = {}
    for tid, audits in audits_by_caterer.items():
        caterer_alert[tid] = "red" if any(a["status"] == "FAIL" for a in audits) else "normal"

    # ── 7. school recent_alert: any connected caterer red ────
    school_caterers = {}
    for sn, tid in edges:
        school_caterers.setdefault(sn, set()).add(tid)
    school_alert = {}
    for sn in [r[2] for r in schools_rows]:
        related = school_caterers.get(sn, set())
        school_alert[sn] = "red" if any(caterer_alert.get(t) == "red" for t in related) else "normal"

    # ── 8. Coordinates ───────────────────────────────────────
    centroids = district_centroids()

    def fallback_centroid(city):
        return (121.50, 25.04) if city == "臺北市" else (121.49, 25.01)

    # School features
    school_features = []
    school_coords = {}
    for c, d, s in schools_rows:
        cx, cy = centroids.get((c, d), fallback_centroid(c))
        jx, jy = jitter(s)
        coord = [cx + jx, cy + jy]
        school_coords[s] = coord
        sup_ids = sorted(school_caterers.get(s, set()))
        school_features.append({
            "type": "Feature",
            "properties": {
                "id": s,
                "name": s,
                "city": c,
                "district": d,
                "type": school_type(s),
                "supplier_ids": sup_ids,
                "recent_alert": school_alert.get(s, "normal"),
            },
            "geometry": {"type": "Point", "coordinates": coord},
        })

    # Caterer features (use audit address district when available)
    sup_features = []
    sup_coords = {}
    for tid, c in caterers.items():
        addr_audits = audits_by_caterer.get(tid, [])
        addr = ""
        cd = None
        for a in addr_audits:
            if a.get("address"):
                addr = a["address"]
                cd = address_district(addr) or (a.get("city"), a.get("district"))
                break
        if cd is None:
            cd = ("臺北市", "中正區")  # last resort
        cx, cy = centroids.get(cd, fallback_centroid(cd[0]))
        jx, jy = jitter(tid)
        coord = [cx + jx, cy + jy]
        sup_coords[tid] = coord
        served = sorted({sn for sn, t in edges if t == tid})
        sup_features.append({
            "type": "Feature",
            "properties": {
                "id": tid,
                "name": c["name"],
                "raw_name": c["raw_name"],
                "city": cd[0],
                "district": cd[1],
                "address": addr,
                "served_school_ids": served,
                "recent_alert": caterer_alert.get(tid, "normal"),
            },
            "geometry": {"type": "Point", "coordinates": coord},
        })

    # Supply-chain LineStrings
    chain_features = []
    for sn, tid in edges:
        if sn not in school_coords or tid not in sup_coords:
            continue
        risk = "high" if caterer_alert.get(tid) == "red" else "low"
        chain_features.append({
            "type": "Feature",
            "properties": {"school_id": sn, "supplier_id": tid, "risk": risk},
            "geometry": {"type": "LineString",
                         "coordinates": [school_coords[sn], sup_coords[tid]]},
        })

    # ── 9. school_nutrition (re-bake from CSVs keyed by real school_name) ────
    nutrition = bake_nutrition({s["properties"]["id"] for s in school_features})

    # ── 10. Write outputs ───────────────────────────────────
    schools_geo = {"type": "FeatureCollection", "features": school_features}
    sup_geo = {"type": "FeatureCollection", "features": sup_features}
    chain_geo = {"type": "FeatureCollection", "features": chain_features}

    DST_MOCK.mkdir(parents=True, exist_ok=True)
    DST_MAP.mkdir(parents=True, exist_ok=True)

    for path in (DST_MOCK / "schools.geojson", DST_MAP / "fsm_schools.geojson"):
        path.write_text(json.dumps(schools_geo, ensure_ascii=False))
    for path in (DST_MOCK / "suppliers.geojson", DST_MAP / "fsm_suppliers.geojson"):
        path.write_text(json.dumps(sup_geo, ensure_ascii=False))
    for path in (DST_MOCK / "supply_chain.geojson", DST_MAP / "fsm_supply_chain.geojson"):
        path.write_text(json.dumps(chain_geo, ensure_ascii=False))
    (DST_MOCK / "supplier_audits.json").write_text(json.dumps(audits_by_caterer, ensure_ascii=False))
    (DST_MOCK / "school_nutrition.json").write_text(json.dumps(nutrition, ensure_ascii=False))

    red_s = sum(1 for f in school_features if f["properties"]["recent_alert"] == "red")
    red_c = sum(1 for f in sup_features if f["properties"]["recent_alert"] == "red")
    print()
    print(f"✅ Wrote schools={len(school_features)} suppliers={len(sup_features)} edges={len(chain_features)}")
    print(f"   recent_alert: schools {red_s} red / suppliers {red_c} red")
    print(f"   nutrition records: {len(nutrition)} schools")


def bake_nutrition(real_school_set):
    with MEAL_CSV.open(encoding="utf-8-sig") as f:
        meals = list(csv.DictReader(f))
    with DISH_CSV.open(encoding="utf-8-sig") as f:
        dishes = list(csv.DictReader(f))
    dishes_by_school = {}
    for d in dishes:
        dishes_by_school.setdefault(d["school_name"], []).append(d)
    nutrition = {}
    for r in meals:
        sn = r["school_name"]
        if sn not in real_school_set:
            continue
        ds = dishes_by_school.get(sn, [])
        try:
            menu_list = json.loads(r["dishes"])
        except Exception:
            menu_list = []
        nutrition[sn] = [{
            "date": r["meal_date"].replace("-", "/"),
            "score": int(r["score"]),
            "menu": "、".join(menu_list),
            "dish_count": int(r["dish_count"]),
            "ai_review": r["summary"],
            "dishes": [
                {
                    "category": d["dish_category"],
                    "name": d["dish_name"],
                    "is_veg": d["is_veg"] == "True",
                    "ingredients": d["ingredients"],
                    "score": int(d["score"]),
                    "summary": d["summary"],
                } for d in ds
            ],
        }]
    return nutrition


if __name__ == "__main__":
    main()
