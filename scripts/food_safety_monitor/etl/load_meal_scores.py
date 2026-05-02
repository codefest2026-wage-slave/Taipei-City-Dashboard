#!/usr/bin/env python3
"""ETL: ingest meal_scores.csv + dish_scores.csv → school_nutrition.json + rename
mock schools to real CSV school names.

Source:
  scripts/food_safety_monitor/snapshots/meal_scores.csv
  scripts/food_safety_monitor/snapshots/dish_scores.csv

Target:
  Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/schools.geojson
    (renames `name` field on each feature to a real CSV school)
  Taipei-City-Dashboard-FE/public/mapData/fsm_schools.geojson
    (mirrored copy for Mapbox layer)
  Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/school_nutrition.json
    (keyed by mock school id; each value is an array with the latest meal record
     and a dishes[] breakdown derived from dish_scores.csv)

Sampling rule:
  - Match the existing mock distribution: 16 TPE-EL / 14 TPE-JH / 18 NTPC-EL / 14 NTPC-JH
  - Pick deterministically (random.seed(42)) so re-running the ETL yields the
    same name-id mapping.

Re-run after the CSVs are refreshed:
  python3 scripts/food_safety_monitor/etl/load_meal_scores.py
"""
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "scripts/food_safety_monitor/snapshots"
DST_MOCK = ROOT / "Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor"
DST_MAP = ROOT / "Taipei-City-Dashboard-FE/public/mapData"

MEAL_CSV = SRC / "meal_scores.csv"
DISH_CSV = SRC / "dish_scores.csv"
SCHOOLS_GEOJSON = DST_MOCK / "schools.geojson"
NUTRITION_JSON = DST_MOCK / "school_nutrition.json"
SCHOOLS_MIRROR = DST_MAP / "fsm_schools.geojson"


def classify(name: str) -> str:
    if name.endswith("國小"):
        return "elementary"
    if name.endswith("國中"):
        return "junior_high"
    return "other"


def city_of(name: str) -> str:
    if name.startswith("臺北市"):
        return "臺北市"
    if name.startswith("新北市") or name.startswith("新北巿"):
        return "新北市"
    return "other"


def district_of(name: str) -> str:
    """Extract '○○區' substring from the school name. Best-effort."""
    head = name[3:]  # strip 臺北市 / 新北市
    if "區" in head:
        idx = head.index("區")
        return head[: idx + 1]
    return ""


def main():
    # ── 1. Read meal_scores ─────────────────────────────────────
    with MEAL_CSV.open(encoding="utf-8-sig") as f:
        meals = list(csv.DictReader(f))

    # Bucket by (city, type)
    buckets: dict[tuple[str, str], list[dict]] = {}
    for r in meals:
        key = (city_of(r["school_name"]), classify(r["school_name"]))
        if key[0] == "other" or key[1] == "other":
            continue
        buckets.setdefault(key, []).append(r)

    print(f"meal_scores.csv: {len(meals)} rows")
    for k, v in sorted(buckets.items()):
        print(f"  {k}: {len(v)} candidates")

    # ── 2. Read dish_scores indexed by school_name ─────────────
    with DISH_CSV.open(encoding="utf-8-sig") as f:
        dish_rows = list(csv.DictReader(f))
    dishes_by_school: dict[str, list[dict]] = {}
    for r in dish_rows:
        dishes_by_school.setdefault(r["school_name"], []).append(r)
    print(f"dish_scores.csv: {len(dish_rows)} rows; {len(dishes_by_school)} schools")

    # ── 3. Load mock schools.geojson ───────────────────────────
    geo = json.loads(SCHOOLS_GEOJSON.read_text())
    features = geo["features"]

    # Group mock features by (city, type) preserving order
    mock_buckets: dict[tuple[str, str], list[dict]] = {}
    for f in features:
        p = f["properties"]
        mock_buckets.setdefault((p["city"], p["type"]), []).append(f)

    # ── 4. Sample real CSV schools and assign 1:1 to mock features ─
    rng = random.Random(42)
    name_to_id: dict[str, str] = {}
    for key, mock_list in mock_buckets.items():
        candidates = buckets.get(key, [])
        if len(candidates) < len(mock_list):
            print(f"WARN: not enough CSV candidates for {key} — have {len(candidates)}, need {len(mock_list)}")
            picked = candidates  # use all
        else:
            picked = rng.sample(candidates, len(mock_list))
        for mock_feat, csv_row in zip(mock_list, picked):
            real_name = csv_row["school_name"]
            mock_feat["properties"]["name"] = real_name
            # also refresh district so it matches the real name's prefix
            d = district_of(real_name)
            if d:
                mock_feat["properties"]["district"] = d
            name_to_id[real_name] = mock_feat["properties"]["id"]

    print(f"Sampled {len(name_to_id)} real school names → mock IDs")

    # ── 5. Build school_nutrition.json keyed by mock id ────────
    nutrition: dict[str, list[dict]] = {}
    for r in meals:
        if r["school_name"] not in name_to_id:
            continue
        sid = name_to_id[r["school_name"]]
        # Dish list for this school
        ds = dishes_by_school.get(r["school_name"], [])
        dishes_array = [
            {
                "category": d["dish_category"],
                "name": d["dish_name"],
                "is_veg": d["is_veg"] == "True",
                "ingredients": d["ingredients"],
                "score": int(d["score"]),
                "summary": d["summary"],
            }
            for d in ds
        ]
        # Menu string: join dish names for backward-compat with FE template
        try:
            menu_list = json.loads(r["dishes"])
        except Exception:
            menu_list = []
        record = {
            "date": r["meal_date"].replace("-", "/"),
            "score": int(r["score"]),
            "menu": "、".join(menu_list),
            "dish_count": int(r["dish_count"]),
            "dishes": dishes_array,
            # ai_review keeps the same key the FE template currently reads
            "ai_review": r["summary"],
        }
        nutrition[sid] = [record]

    print(f"school_nutrition: {len(nutrition)} schools with meal data")

    # ── 6. Write outputs ───────────────────────────────────────
    SCHOOLS_GEOJSON.write_text(json.dumps(geo, ensure_ascii=False))
    SCHOOLS_MIRROR.write_text(json.dumps(geo, ensure_ascii=False))
    NUTRITION_JSON.write_text(json.dumps(nutrition, ensure_ascii=False))

    print(f"\n✅ Wrote:")
    print(f"  {SCHOOLS_GEOJSON}")
    print(f"  {SCHOOLS_MIRROR}")
    print(f"  {NUTRITION_JSON}")


if __name__ == "__main__":
    main()
