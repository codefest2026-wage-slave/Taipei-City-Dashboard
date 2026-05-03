"""Stage 3: Per-meal aggregation + LLM summary.

Reads:
  data/dish_scores.csv

Writes:
  data/meal_scores.csv

Strategy:
  1. For each (school_name, meal_date), pick the "default meal" — i.e. the
     omnivore version when one exists. Concretely: within each category, if any
     is_veg=False dish exists, drop the is_veg=True dishes in that category.
     Categories that only have vegetarian options keep them.
  2. Score = weighted average over the selected dishes (deterministic, no LLM):
        主菜=2.0, 主食=1.5, 副菜=1.0, 蔬菜=1.0, 湯品=1.0, 附餐=0.5
  3. Summary = LLM. Prompt feeds the dish list (category, name, score, dish-summary)
     plus the deterministic weighted score, asks for <150 字 evaluation.
  4. SQLite cache (in llm_client) makes the run resumable; identical menus across
     different schools share the same cache hit because the prompt only depends on
     the dish list, not on school name or date.

Optional flags:
  --limit N        only summarise the first N unique meals (for testing)
  --concurrency K  parallel LLM calls (default 5)
  --max-tokens M   max_new_tokens per call (default 800)
  --no-llm         skip the LLM step, leave summary empty (sanity-check the math)
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
DISH_SCORES_CSV = PROJECT_ROOT / "data" / "dish_scores.csv"
OUTPUT_CSV = PROJECT_ROOT / "data" / "meal_scores.csv"

# Weights for the deterministic meal score.
CATEGORY_WEIGHTS = {
    "主菜": 2.0,
    "主食": 1.5,
    "副菜": 1.0,
    "蔬菜": 1.0,
    "湯品": 1.0,
    "附餐": 0.5,
}

# Order used when listing dishes in the LLM prompt (deterministic for cache).
CATEGORY_ORDER = ["主食", "主菜", "副菜", "蔬菜", "湯品", "附餐"]
CATEGORY_RANK = {c: i for i, c in enumerate(CATEGORY_ORDER)}


SYS_PROMPT = """你是台灣國中小學營養午餐健康評估專家。
針對輸入「一餐料理清單(已含每道菜的分數與短評)」與「該餐加權平均分數」，撰寫一段繁體中文健康總結。

回傳:
- summary: 少於 150 字繁體中文，依序提及:
  1. 整體營養均衡度（主食/主蛋白/蔬菜/湯品是否齊全）
  2. 亮點（優質食材、清淡手法、Omega-3、纖維等）
  3. 隱憂（高鈉、油炸、加工肉品、缺蔬菜、糖分高等）

只輸出合法 JSON: {"summary":"..."}

範例：

輸入:
加權平均分數: 4
料理:
- 主食 黑芝麻飯 (4): 白米加黑芝麻同煮,補充鈣與好油脂
- 主菜 虱目魚排 (5): 白肉魚清蒸保留蛋白與omega-3
- 副菜 醬炒干片 (3): 豆製品加瘦肉蛋白足,醬汁鈉糖偏多
- 副菜 高麗粉絲 (3): 高麗菜搭冬粉,纖維尚可但鹽糖視調味
- 蔬菜 油菜 (5): 原型葉菜清燙,纖維與礦物質保留度佳
- 湯品 冬瓜湯 (4): 冬瓜清淡湯品,水分纖維足
- 附餐 藍莓 (5): 莓果抗氧化高

輸出:
{"summary":"本餐主食、主蛋白、蔬菜、湯品與水果齊全，搭配均衡。亮點為清蒸虱目魚提供omega-3，藍莓抗氧化、冬瓜湯與燙油菜清淡解膩；副菜豆干肉絲補充植物與動物蛋白來源。隱憂為兩道副菜以醬炒手法烹調，鈉與糖醬可能略偏高，建議減少醬汁分量。整體屬均衡偏健康的一餐。"}

輸入:
加權平均分數: 2
料理:
- 主食 油麵 (2): 油麵製程加鹼水並過油
- 主菜 炸雞排 (1): 雞肉雖優質但油炸吸油
- 副菜 培根高麗 (2): 培根加工肉,鈉與飽和脂肪偏高
- 湯品 玉米濃湯 (2): 玉米加奶油勾芡,糖油偏高

輸出:
{"summary":"本餐缺乏新鮮蔬菜，蛋白質主要來自油炸雞排與加工培根，鈉、油與飽和脂肪明顯偏高；主食選用油麵並非全穀，纖維低；湯品為勾芡濃湯，糖分與油脂均偏高。整體屬高熱量、高鈉、低纖維的偏不健康餐次，建議至少替換一道為清燙蔬菜並減少油炸頻率。"}

輸入:
加權平均分數: 5
料理:
- 主食 糙米飯 (5): 全穀糙米富含纖維與B群
- 主菜 番茄燉牛肉 (4): 蔬菜搭原型紅肉慢燉
- 副菜 涼拌豆腐 (5): 板豆腐涼拌少油少鹽
- 蔬菜 燙青江菜 (5): 深綠葉菜清燙
- 湯品 蛤蜊湯 (5): 蛤蜊湯含鋅與優質蛋白
- 附餐 蘋果 (5): 水果纖維果膠

輸出:
{"summary":"本餐六大類別全到位，主食用全穀糙米提供B群與纖維，主菜燉牛肉搭蔬菜營養釋出佳。亮點包含涼拌豆腐少油補充植物蛋白、燙青江菜保留礦物質、蛤蜊湯提供鋅與omega-3、蘋果補充果膠纖維。烹調以燉、燙、涼拌為主，幾乎無油炸或重醬，鈉與糖控制良好。整體屬高度均衡且清淡的一餐。"}
"""


def parse_bool(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    s = str(x).strip().lower()
    return s in ("true", "1", "yes", "t", "y")


def select_default_meal(group: pd.DataFrame) -> pd.DataFrame:
    """Within a (school, date) group, drop is_veg=True dishes for any category
    that also has an omnivore option.
    """
    cat_has_omni = group.groupby("dish_category")["is_veg"].transform(lambda s: (~s).any())
    keep = ~(cat_has_omni & group["is_veg"])
    return group[keep]


def compute_meal_score(dishes: list[dict]) -> int:
    total_w = 0.0
    total_score = 0.0
    for d in dishes:
        w = CATEGORY_WEIGHTS.get(d["dish_category"], 1.0)
        total_w += w
        total_score += float(d["score"]) * w
    if total_w == 0:
        return 0
    return int(round(total_score / total_w))


def build_meal_prompt(dishes: list[dict], weighted_score: int) -> str:
    sorted_d = sorted(
        dishes,
        key=lambda d: (CATEGORY_RANK.get(d["dish_category"], 99), d["dish_name"]),
    )
    lines = [
        f"- {d['dish_category']} {d['dish_name']} ({int(d['score'])}): {d['summary']}"
        for d in sorted_d
    ]
    return (
        f"輸入:\n"
        f"加權平均分數: {weighted_score}\n"
        f"料理:\n"
        + "\n".join(lines)
        + "\n\n輸出："
    )


def make_meal_key(school_name: str, meal_date: str) -> str:
    return f"{school_name}|{meal_date}"


def validate_response(resp) -> str:
    if not isinstance(resp, dict):
        raise ValueError(f"response is not a dict: {type(resp).__name__}")
    summary = str(resp.get("summary", "")).strip()
    if not summary:
        raise ValueError("empty summary")
    return summary


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, help="only summarise the first N unique meals (for testing)")
    p.add_argument("--concurrency", type=int, default=5, help="parallel LLM calls (default 5)")
    p.add_argument("--max-tokens", type=int, default=800, help="max_new_tokens per call (default 800)")
    p.add_argument("--no-llm", action="store_true", help="skip the LLM step, leave summary empty")
    return p.parse_args()


def main():
    args = parse_args()

    if not DISH_SCORES_CSV.exists():
        raise SystemExit(f"missing {DISH_SCORES_CSV}; run stage2 first")

    print(f"loading {DISH_SCORES_CSV.name} ...")
    df = pd.read_csv(DISH_SCORES_CSV, encoding="utf-8-sig")
    print(f"  {len(df):,} dish rows")

    df["is_veg"] = df["is_veg"].map(parse_bool)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["score", "dish_category", "dish_name", "summary"])

    print("filtering each meal to default (omnivore-preferred) version ...")
    before = len(df)
    df = (
        df.groupby(["school_name", "meal_date"], group_keys=False)
        .apply(select_default_meal)
        .reset_index(drop=True)
    )
    print(f"  {len(df):,} dish rows after filter (dropped {before - len(df):,} duplicate veg entries)")

    print("\naggregating into meals ...")
    meals: list[dict] = []
    for (school, date), g in df.groupby(["school_name", "meal_date"], sort=False):
        dishes = g[["dish_category", "dish_name", "score", "summary"]].to_dict("records")
        if not dishes:
            continue
        weighted_score = compute_meal_score(dishes)
        meals.append(
            {
                "school_name": school,
                "meal_date": date,
                "dishes": dishes,
                "weighted_score": weighted_score,
            }
        )
    print(f"  {len(meals):,} unique meals")

    if args.limit:
        meals = meals[: args.limit]
        print(f"  limited to {len(meals):,} for this run")

    if args.no_llm:
        print("\n--no-llm: skipping LLM, summary will be empty")
        rows = [
            {
                "school_name": m["school_name"],
                "meal_date": m["meal_date"],
                "score": m["weighted_score"],
                "summary": "",
                "dish_count": len(m["dishes"]),
                "dishes": json.dumps([d["dish_name"] for d in m["dishes"]], ensure_ascii=False),
            }
            for m in meals
        ]
    else:
        assert_env()

        tasks: list[tuple[str, str, str]] = []
        for m in meals:
            key = make_meal_key(m["school_name"], m["meal_date"])
            prompt = build_meal_prompt(m["dishes"], m["weighted_score"])
            tasks.append((key, SYS_PROMPT, prompt))

        print(f"\ncalling LLM ({len(tasks):,} meals, concurrency={args.concurrency}) ...")
        raw_results = batch_chat_json(
            tasks,
            max_workers=args.concurrency,
            max_tokens=args.max_tokens,
            temperature=0.3,
        )

        print("\nvalidating responses ...")
        summaries: dict[str, str] = {}
        fail_count = 0
        sample_failures: list[str] = []
        for key, result in raw_results.items():
            if isinstance(result, Exception):
                fail_count += 1
                if len(sample_failures) < 3:
                    sample_failures.append(f"{key}: {result}")
                continue
            try:
                summaries[key] = validate_response(result)
            except Exception as e:
                fail_count += 1
                if len(sample_failures) < 3:
                    sample_failures.append(f"{key}: {e}")

        print(f"  ok     : {len(summaries):,}")
        print(f"  failed : {fail_count:,}")
        for s in sample_failures:
            print(f"     - {s}", file=sys.stderr)

        rows = []
        for m in meals:
            key = make_meal_key(m["school_name"], m["meal_date"])
            rows.append(
                {
                    "school_name": m["school_name"],
                    "meal_date": m["meal_date"],
                    "score": m["weighted_score"],
                    "summary": summaries.get(key, ""),
                    "dish_count": len(m["dishes"]),
                    "dishes": json.dumps([d["dish_name"] for d in m["dishes"]], ensure_ascii=False),
                }
            )

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nwrote {OUTPUT_CSV}  ({len(out_df):,} rows)")
    print(f"  score distribution:")
    for s, n in out_df["score"].value_counts().sort_index().items():
        print(f"     {s}: {n:,}")
    if not args.no_llm:
        n_with_summary = (out_df["summary"].str.len() > 0).sum()
        print(f"  rows with summary  : {n_with_summary:,} / {len(out_df):,}")


if __name__ == "__main__":
    main()
