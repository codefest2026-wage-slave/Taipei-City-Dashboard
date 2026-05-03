"""Stage 2: Per-dish LLM scoring using the foods + cooks KB.

Reads:
  data/menus.parquet
  data/nutrition_kb.json

Writes:
  data/dish_scores.csv

Strategy:
  1. Group menus.parquet on (dish_name, ingredients, is_veg) -> unique recipes.
  2. For each unique recipe, look up every ingredient and every detected cooking
     method in nutrition_kb.json to get pre-scored summaries.
  3. Build an LLM prompt that lists all components with their pre-scores, ask for
     a final {summary, score, reference} for the dish.
  4. SQLite cache (in llm_client) makes the run resumable; recipes already scored
     in a previous run hit the cache instantly.
  5. Join the unique-recipe scores back to all dish instances and write CSV.

Optional flags:
  --limit N         only score the first N unique recipes (for testing)
  --concurrency K   parallel LLM calls (default 5)
  --max-tokens M    max_new_tokens per call (default 512)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import assert_env, batch_chat_json  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MENUS_PARQUET = PROJECT_ROOT / "data" / "menus.parquet"
KB_PATH = PROJECT_ROOT / "data" / "nutrition_kb.json"
OUTPUT_CSV = PROJECT_ROOT / "data" / "dish_scores.csv"

# Same set as stage1 (kept here so this script is self-contained)
COOKING_METHODS = [
    "紅燒", "清蒸", "香煎", "油炸", "乾煎", "乾煸", "醬炒", "醬燒", "醬滷",
    "蜜汁", "焗烤", "白灼", "燒烤", "粉蒸", "鹽烤", "蔥燒", "麻辣", "三杯",
    "滷", "燉", "煮", "炒", "煎", "炸", "烤", "蒸", "拌", "燙", "燴",
    "燒", "煸", "煨", "燻", "焗", "熬", "焢", "煲", "悶", "爆", "烘",
    "汆", "灼", "燜", "炆",
]

# When the dish name has no detectable cooking method, fall back to a sensible
# default for that category. None means "let the LLM judge from name + ingredients".
CATEGORY_DEFAULT_COOK = {
    "蔬菜": "燙",
    "主食": "煮",
    "湯品": "煮",
    "主菜": None,
    "副菜": None,
    "附餐": None,
}


SYS_PROMPT = """你是台灣國中小學營養午餐健康評估專家。
針對輸入「料理名稱 + 類型 + 食材清單(已預先評分) + 烹飪手法(已預先評分)」評估這道料理整體健康度。

回傳:
- summary: 少於 30 字繁體中文，總結這道料理的健康亮點或風險
- score: 整數 0~5（5=最健康，0=最不健康）
- reference: 此次評估有實際參考的食材或手法名稱(list of string)

評分原則：
- 食材分數的加權平均為 baseline；烹飪手法可加減 0~2 分
- 若主蛋白為加工肉(培根、香腸、貢丸、素料)，整體下調
- 若手法為油炸、紅燒、煙燻、三杯等高油糖手法，整體下調 1~2
- 若手法為蒸、煮、燙等清淡手法，整體上調 0~1
- 不要只取最低分；綜合判斷

只輸出合法 JSON：{"summary":"","score":0,"reference":[]}

範例：

輸入:
料理：清蒸鯛魚
類型：主菜（葷食）
食材：鯛魚(5)、薑(5)、青蔥(5)
手法：清蒸(5)

輸出:
{"summary":"白肉魚清蒸保留蛋白與omega-3，用油極少","score":5,"reference":["鯛魚","清蒸"]}

輸入:
料理：番茄燉牛肉
類型：主菜（葷食）
食材：牛肉(4)、番茄(5)、洋蔥(5)、馬鈴薯(4)
手法：燉(4)

輸出:
{"summary":"蔬菜搭原型紅肉慢燉，營養保留度佳","score":4,"reference":["牛肉","番茄","燉"]}

輸入:
料理：醬炒豆干肉絲
類型：副菜（葷食）
食材：豆干(3)、肉絲(豬後腿)(4)、青椒(5)、洋蔥(5)
手法：醬炒(3)

輸出:
{"summary":"豆製品加瘦肉蛋白足，醬汁鈉糖偏多","score":3,"reference":["豆干","肉絲(豬後腿)","醬炒"]}

輸入:
料理：紅燒五花肉
類型：主菜（葷食）
食材：五花肉(3)、醬油(2)
手法：紅燒(2)

輸出:
{"summary":"高脂肉以重油糖紅燒，鈉糖油偏高","score":2,"reference":["五花肉","紅燒"]}

輸入:
料理：炸雞排
類型：主菜（葷食）
食材：雞排(3)
手法：油炸(1)

輸出:
{"summary":"雞肉雖優質但油炸吸油，熱量飆高","score":1,"reference":["雞排","油炸"]}

輸入:
料理：燙青菜
類型：蔬菜
食材：油菜(5)
手法：燙(5)

輸出:
{"summary":"原型葉菜清燙，纖維與礦物質保留度佳","score":5,"reference":["油菜","燙"]}

輸入:
料理：(素)滷肉飯
類型：主食（素食）
食材：白米(3)、素肉(1)、香菇(5)、麵輪(2)
手法：滷(4)

輸出:
{"summary":"白飯配高加工素料，缺優質蛋白且鈉偏高","score":2,"reference":["素肉","麵輪","滷"]}
"""


def extract_cooking_methods(dish_name: str) -> list[str]:
    found: list[str] = []
    for m in COOKING_METHODS:  # already longest-first
        if m in dish_name:
            if any(m != other and m in other for other in found):
                continue
            if m not in found:
                found.append(m)
    return found


def load_kb() -> tuple[dict, dict]:
    data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    foods = {f["food_name"]: f for f in data.get("foods", [])}
    cooks = {c["cook_name"]: c for c in data.get("cooks", [])}
    return foods, cooks


def build_recipe_prompt(
    dish_name: str,
    dish_category: str,
    is_veg: bool,
    ingredients: list[str],
    foods: dict,
    cooks: dict,
) -> tuple[str, list[str], list[str], list[str]]:
    """Return (prompt_text, refs_available, missing_ings, missing_cooks)."""
    veg_label = "素食" if is_veg else "葷食"

    ing_lines: list[str] = []
    refs_available: list[str] = []
    missing_ings: list[str] = []
    for ing in ingredients:
        f = foods.get(ing)
        if f is not None:
            ing_lines.append(f"{ing}({f['score']})")
            refs_available.append(ing)
        else:
            ing_lines.append(f"{ing}(?)")
            missing_ings.append(ing)

    methods = extract_cooking_methods(dish_name)
    if not methods:
        default = CATEGORY_DEFAULT_COOK.get(dish_category)
        if default and default in cooks:
            methods = [default]

    cook_lines: list[str] = []
    missing_cooks: list[str] = []
    for m in methods:
        c = cooks.get(m)
        if c is not None:
            cook_lines.append(f"{m}({c['score']})")
            refs_available.append(m)
        else:
            cook_lines.append(f"{m}(?)")
            missing_cooks.append(m)

    prompt = (
        f"輸入:\n"
        f"料理：{dish_name}\n"
        f"類型：{dish_category}（{veg_label}）\n"
        f"食材：{'、'.join(ing_lines) if ing_lines else '無'}\n"
        f"手法：{'、'.join(cook_lines) if cook_lines else '無明顯烹飪手法'}\n"
        f"\n輸出："
    )
    return prompt, refs_available, missing_ings, missing_cooks


def make_recipe_key(dish_name: str, ingredients_key: str, is_veg: bool) -> str:
    return f"{dish_name}|{int(bool(is_veg))}|{ingredients_key}"


def validate_response(resp) -> dict:
    if not isinstance(resp, dict):
        raise ValueError(f"response is not a dict: {type(resp).__name__}")

    summary = str(resp.get("summary", "")).strip()
    if not summary:
        raise ValueError("empty summary")

    raw_score = resp.get("score")
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        raise ValueError(f"non-integer score: {raw_score!r}")
    if not 0 <= score <= 5:
        raise ValueError(f"score out of range: {score}")

    reference = resp.get("reference", [])
    if not isinstance(reference, list):
        reference = []
    reference = [str(x).strip() for x in reference if isinstance(x, (str, int, float)) and str(x).strip()]

    return {"summary": summary, "score": score, "reference": reference}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, help="only score the first N unique recipes (for testing)")
    p.add_argument("--concurrency", type=int, default=5, help="parallel LLM calls (default 5)")
    p.add_argument("--max-tokens", type=int, default=512, help="max_new_tokens per call (default 512)")
    return p.parse_args()


def main():
    args = parse_args()
    assert_env()

    if not MENUS_PARQUET.exists():
        raise SystemExit(f"missing {MENUS_PARQUET}; run stage0 first")
    if not KB_PATH.exists():
        raise SystemExit(f"missing {KB_PATH}; run stage1 first")

    print(f"loading {MENUS_PARQUET.name} ...")
    menus = pd.read_parquet(MENUS_PARQUET)
    print(f"  {len(menus):,} dish instances")

    print(f"loading {KB_PATH.name} ...")
    foods, cooks = load_kb()
    print(f"  {len(foods):,} foods, {len(cooks):,} cooks")

    # vectorised recipe_key
    menus["recipe_key"] = (
        menus["dish_name"].astype(str)
        + "|"
        + menus["is_veg"].astype(int).astype(str)
        + "|"
        + menus["ingredients_key"].astype(str)
    )

    unique_recipes = menus.drop_duplicates(subset="recipe_key").copy()
    print(f"  {len(unique_recipes):,} unique recipes")

    if args.limit:
        unique_recipes = unique_recipes.head(args.limit).copy()
        print(f"  limited to {len(unique_recipes):,} for this run")

    print("\nbuilding prompts ...")
    tasks: list[tuple[str, str, str]] = []
    refs_by_key: dict[str, list[str]] = {}
    missing_ing_total = 0
    missing_cook_total = 0
    for _, row in unique_recipes.iterrows():
        prompt, refs, miss_i, miss_c = build_recipe_prompt(
            row["dish_name"],
            row["dish_category"],
            bool(row["is_veg"]),
            list(row["ingredients"]),
            foods,
            cooks,
        )
        missing_ing_total += len(miss_i)
        missing_cook_total += len(miss_c)
        tasks.append((row["recipe_key"], SYS_PROMPT, prompt))
        refs_by_key[row["recipe_key"]] = refs

    if missing_ing_total or missing_cook_total:
        print(
            f"  ! KB lookup misses: {missing_ing_total} ingredient slot(s), "
            f"{missing_cook_total} cook slot(s)  (filled with '?')"
        )

    print(f"\ncalling LLM ({len(tasks):,} unique recipes, concurrency={args.concurrency}) ...")
    raw_results = batch_chat_json(
        tasks,
        max_workers=args.concurrency,
        max_tokens=args.max_tokens,
        temperature=0.3,
    )

    print("\nvalidating responses ...")
    scored: dict[str, dict] = {}
    fail_count = 0
    sample_failures: list[str] = []
    for key, result in raw_results.items():
        if isinstance(result, Exception):
            fail_count += 1
            if len(sample_failures) < 3:
                sample_failures.append(f"{key}: {result}")
            continue
        try:
            scored[key] = validate_response(result)
        except Exception as e:
            fail_count += 1
            if len(sample_failures) < 3:
                sample_failures.append(f"{key}: {e}")

    print(f"  ok     : {len(scored):,}")
    print(f"  failed : {fail_count:,}")
    for s in sample_failures:
        print(f"     - {s}", file=sys.stderr)

    if not scored:
        raise SystemExit("no recipes successfully scored; aborting")

    # Build a small dataframe of scored recipes and merge back to all instances.
    scored_df = pd.DataFrame(
        [
            {
                "recipe_key": k,
                "summary": v["summary"],
                "score": v["score"],
                "reference": json.dumps(v["reference"], ensure_ascii=False),
            }
            for k, v in scored.items()
        ]
    )

    print("\njoining scores back to all instances ...")
    out_df = menus.merge(scored_df, on="recipe_key", how="inner")
    out_df["ingredients_str"] = out_df["ingredients"].map(lambda xs: "、".join(xs))

    out_cols = [
        "school_name",
        "meal_date",
        "dish_category",
        "dish_name",
        "is_veg",
        "ingredients_str",
        "ingredient_count",
        "summary",
        "score",
        "reference",
    ]
    out_df = out_df[out_cols].rename(columns={"ingredients_str": "ingredients"})

    # utf-8-sig so Excel opens Chinese correctly
    out_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nwrote {OUTPUT_CSV}  ({len(out_df):,} rows)")
    print(f"  unique recipes scored : {len(scored):,} / {len(unique_recipes):,}")
    print(f"  score distribution    :")
    for s, n in out_df["score"].value_counts().sort_index().items():
        print(f"     {s}: {n:,}")


if __name__ == "__main__":
    main()
