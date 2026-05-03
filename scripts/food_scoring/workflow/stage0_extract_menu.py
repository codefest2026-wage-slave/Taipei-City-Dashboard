"""Stage 0: Normalize dish.csv into a deduplicated per-dish-instance parquet.

Input  : dish.csv
Output : data/menus.parquet

Transformations:
  1. Strip trailing 8-digit date suffix from dish_name  (e.g. 醬炒干片20260302 -> 醬炒干片)
  2. Strip leading "(素)" prefix and set is_veg=True
  3. Group by (school_name, meal_date, dish_category, dish_name, is_veg)
     -> ingredients: sorted unique list[str]

Optional date filtering (for incremental / test runs):
  --latest N         keep only the latest N unique meal_dates
  --date YYYY-MM-DD  keep only this single meal_date  (repeatable)
  --from YYYY-MM-DD  keep meal_dates >= this date
  --to   YYYY-MM-DD  keep meal_dates <= this date
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "dish.csv"
OUTPUT_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_PARQUET = OUTPUT_DIR / "menus.parquet"

DATE_SUFFIX_RE = re.compile(r"\d{8}$")
VEG_PREFIX_RE = re.compile(r"^\s*\(\s*素\s*\)\s*")


def normalize_dish_name(raw: str):
    if not isinstance(raw, str):
        return "", False
    s = raw.strip()
    is_veg = bool(VEG_PREFIX_RE.match(s))
    if is_veg:
        s = VEG_PREFIX_RE.sub("", s, count=1)
    s = DATE_SUFFIX_RE.sub("", s).strip()
    return s, is_veg


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--latest", type=int, metavar="N", help="keep only the latest N unique meal_dates")
    p.add_argument("--date", action="append", metavar="YYYY-MM-DD",
                   help="keep only this meal_date (can repeat to specify multiple)")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                   help="keep meal_dates >= this date (inclusive)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                   help="keep meal_dates <= this date (inclusive)")
    return p.parse_args()


def apply_date_filter(df: pd.DataFrame, args) -> pd.DataFrame:
    """Apply --latest / --date / --from / --to filters in order, with logging."""
    if args.latest is not None:
        latest_dates = sorted(df["meal_date"].dropna().unique(), reverse=True)[: args.latest]
        kept = sorted(latest_dates)
        df = df[df["meal_date"].isin(latest_dates)]
        print(f"  --latest {args.latest}: kept dates = {[str(d.date()) for d in kept]}")
    if args.date:
        wanted = pd.to_datetime(args.date, errors="coerce")
        wanted = wanted[~wanted.isna()]
        df = df[df["meal_date"].isin(wanted)]
        print(f"  --date: kept dates = {[d.strftime('%Y-%m-%d') for d in wanted]}")
    if args.date_from:
        cutoff = pd.to_datetime(args.date_from)
        df = df[df["meal_date"] >= cutoff]
        print(f"  --from {args.date_from}: kept rows where meal_date >= {cutoff.date()}")
    if args.date_to:
        cutoff = pd.to_datetime(args.date_to)
        df = df[df["meal_date"] <= cutoff]
        print(f"  --to {args.date_to}: kept rows where meal_date <= {cutoff.date()}")
    return df


def main():
    args = parse_args()

    if not INPUT_CSV.exists():
        raise SystemExit(f"missing input: {INPUT_CSV}")

    print(f"reading {INPUT_CSV} ...")
    df = pd.read_csv(
        INPUT_CSV,
        usecols=[
            "school_name",
            "meal_date",
            "dish_category",
            "dish_name",
            "ingredient_name",
        ],
        dtype="string",
    )
    print(f"  loaded {len(df):,} rows")

    df = df.dropna(subset=["dish_name", "ingredient_name", "school_name", "meal_date"])
    df["meal_date"] = pd.to_datetime(df["meal_date"], errors="coerce")
    df = df.dropna(subset=["meal_date"])

    available = sorted(df["meal_date"].dt.date.unique())
    print(f"  available dates ({len(available)}): {available[0]} .. {available[-1]}")

    df = apply_date_filter(df, args)
    if df.empty:
        raise SystemExit("date filter removed all rows; nothing to write")
    print(f"  rows after date filter   : {len(df):,}")

    norm = df["dish_name"].map(normalize_dish_name)
    df["dish_name_norm"] = [n for n, _ in norm]
    df["is_veg"] = [v for _, v in norm]
    df["ingredient_name"] = df["ingredient_name"].str.strip()
    df = df[df["dish_name_norm"] != ""]
    df = df[df["ingredient_name"] != ""]

    grouped = (
        df.groupby(
            ["school_name", "meal_date", "dish_category", "dish_name_norm", "is_veg"],
            dropna=False,
        )["ingredient_name"]
        .apply(lambda s: sorted(set(s.dropna().tolist())))
        .reset_index()
        .rename(
            columns={"ingredient_name": "ingredients", "dish_name_norm": "dish_name"}
        )
    )

    grouped["meal_date"] = grouped["meal_date"].dt.strftime("%Y-%m-%d")
    grouped["ingredient_count"] = grouped["ingredients"].map(len)
    grouped["ingredients_key"] = grouped["ingredients"].map(lambda xs: "|".join(xs))

    print()
    print(f"  dish instances           : {len(grouped):,}")
    print(f"  unique schools           : {grouped['school_name'].nunique():,}")
    print(f"  unique dates             : {grouped['meal_date'].nunique():,}")
    print(f"  unique (school, date)    : {grouped[['school_name','meal_date']].drop_duplicates().shape[0]:,}")
    print(f"  unique normalized dishes : {grouped['dish_name'].nunique():,}")

    unique_recipes = grouped[["dish_name", "ingredients_key", "is_veg"]].drop_duplicates()
    print(f"  unique (dish, ingredients): {len(unique_recipes):,}   <- LLM calls in Stage 2")

    all_ings: set[str] = set()
    for ings in grouped["ingredients"]:
        all_ings.update(ings)
    print(f"  unique ingredients       : {len(all_ings):,}   <- LLM calls in Stage 1 (foods)")

    print(f"  category distribution    :")
    for cat, n in grouped["dish_category"].value_counts().items():
        print(f"     {cat:<6} {n:,}")

    grouped.to_parquet(OUTPUT_PARQUET, index=False)
    print()
    print(f"wrote {OUTPUT_PARQUET} ({OUTPUT_PARQUET.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
