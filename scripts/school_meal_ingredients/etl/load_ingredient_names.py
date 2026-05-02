#!/usr/bin/env python3
"""Aggregate unique 食材名稱 across all snapshot CSVs into school_meal_ingredient_names.

Reads scripts/school_meal_ingredients/snapshots/*.csv (CSVs only — no
HTTP), detects the 食材名稱 column per file, aggregates name -> {count,
first_ym, last_ym, counties_set}, and writes the result via TRUNCATE +
INSERT into the dashboard DB.

Dual-city compliance (CLAUDE.md): aborts if either 臺北市 or 新北市 is
missing from the aggregated source_counties.
"""
import csv
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _db import db_kwargs  # noqa: E402

SMI_ROOT      = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = SMI_ROOT / "snapshots"

INGREDIENT_HEADER = "食材名稱"
FALLBACK_HEADERS  = ("品名", "食材", "菜色")  # warn when used

INSERT_SQL = """
INSERT INTO school_meal_ingredient_names
    (name, occurrence, first_seen_ym, last_seen_ym, source_counties)
VALUES %s
"""

CITY_FROM_PREFIX = {"tpe": "臺北市", "ntpc": "新北市", "nation": "全國"}


def parse_filename(path: Path):
    """Return (year, month, county) — strings; (None, None, None) for one-shot."""
    name = path.name
    if name == "food_chinese_names.csv":
        return None, None, None
    m = re.match(r"^(tpe|ntpc|nation)_(\d{4})(\d{2})(?:_[^_]+)?_.+\.csv$", name)
    if not m:
        return None, None, None
    prefix, yyyy, mm = m.group(1), m.group(2), m.group(3)
    return yyyy, mm, CITY_FROM_PREFIX.get(prefix)


def detect_ingredient_column(reader_fieldnames, path):
    """Return the field name in this CSV that holds 食材名稱, or None.

    Resolution order (first wins):
      1. Exact match for INGREDIENT_HEADER ('食材名稱').
      2. Exact match for any FALLBACK_HEADER ('品名' / '食材' / '菜色').
      3. Suffix match (clean.endswith(fb)) — catches '食材品名', '料理菜色'
         while rejecting '供應商食材分類' or '食材來源縣市'.
      4. Otherwise None — caller will skip the file.
    """
    if not reader_fieldnames:
        return None
    fnmap = {f.strip(): f for f in reader_fieldnames if f}

    if INGREDIENT_HEADER in fnmap:
        return fnmap[INGREDIENT_HEADER]

    for fb in FALLBACK_HEADERS:
        if fb in fnmap:
            print(f"  ⚠️  {path.name}: using fallback column {fb!r} (exact, no '食材名稱')",
                  file=sys.stderr)
            return fnmap[fb]

    for fb in FALLBACK_HEADERS:
        for clean, original in fnmap.items():
            if clean.endswith(fb):
                print(f"  ⚠️  {path.name}: using fallback column {original!r} "
                      f"(endswith {fb!r}, no '食材名稱')", file=sys.stderr)
                return original

    return None


def aggregate():
    agg = {}  # name -> [count, first_ym, last_ym, counties_set]
    skipped = []
    file_count = 0
    row_count = 0

    csv_files = sorted(SNAPSHOTS_DIR.glob("*.csv"))
    if not csv_files:
        print("❌ no snapshot CSVs found — run snapshot_apis.py first.", file=sys.stderr)
        sys.exit(1)

    for path in csv_files:
        year, month, county = parse_filename(path)
        ym = f"{year}-{month}" if (year and month) else None

        try:
            with path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                col = detect_ingredient_column(reader.fieldnames, path)
                if col is None:
                    skipped.append((path.name, "no ingredient column"))
                    continue
                file_count += 1
                for row in reader:
                    raw = row.get(col)
                    name = (raw or "").strip()
                    if not name:
                        continue
                    if len(name) > 200:
                        skipped.append((path.name,
                                        f"name truncated to 200 chars: {name[:40]}…"))
                        name = name[:200]  # match VARCHAR(200)
                    rec = agg.get(name)
                    if rec is None:
                        rec = [0, ym, ym, set()]
                        agg[name] = rec
                    rec[0] += 1
                    if ym:
                        if rec[1] is None or ym < rec[1]:
                            rec[1] = ym
                        if rec[2] is None or ym > rec[2]:
                            rec[2] = ym
                    if county and county != "全國":
                        rec[3].add(county)
                    row_count += 1
        except (OSError, csv.Error, UnicodeDecodeError) as e:
            skipped.append((path.name, f"read error: {e}"))
            continue

    return agg, skipped, file_count, row_count


def main():
    print("=== load_ingredient_names ===")
    agg, skipped, file_count, row_count = aggregate()

    print(f"  files used:   {file_count}")
    print(f"  rows seen:    {row_count:,}")
    print(f"  unique names: {len(agg):,}")
    if skipped:
        print(f"  skipped files: {len(skipped)}")
        for fn, reason in skipped[:10]:
            print(f"    {fn} — {reason}")
        if len(skipped) > 10:
            print(f"    … and {len(skipped) - 10} more")

    if not agg:
        print("❌ no ingredient names aggregated", file=sys.stderr)
        sys.exit(1)

    # Dual-city enforcement (CLAUDE.md)
    all_counties = set()
    for v in agg.values():
        all_counties |= v[3]
    print(f"  counties seen: {sorted(all_counties)}")
    if "臺北市" not in all_counties or "新北市" not in all_counties:
        print("❌ dual-city requirement not met — both 臺北市 AND 新北市 must appear in source_counties",
              file=sys.stderr)
        sys.exit(1)

    rows = []
    for name, (count, first_ym, last_ym, counties) in agg.items():
        rows.append((name, count, first_ym, last_ym, sorted(counties)))

    with psycopg2.connect(**db_kwargs()) as conn, conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("TRUNCATE school_meal_ingredient_names RESTART IDENTITY")
        execute_values(cur, INSERT_SQL, rows, page_size=500)
        cur.execute("COMMIT")

    print(f"✅ {len(rows):,} rows → school_meal_ingredient_names")

    # Top 20 by occurrence
    top = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)[:20]
    print("\n── top 20 by occurrence ──")
    for name, (count, *_rest) in top:
        print(f"  {count:>6,}  {name}")


if __name__ == "__main__":
    main()
