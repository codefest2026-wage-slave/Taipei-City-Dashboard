"""Stage 1: Build data/nutrition_kb.json containing foods + cooks scores.

Reads  : data/menus.parquet
Writes : data/nutrition_kb.json

- foods: every unique ingredient across all dishes, scored 0-5
- cooks: every cooking method token detected in dish names, scored 0-5

Resumable: items already present in an existing nutrition_kb.json are skipped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# allow running as a script (`python workflow\stage1_build_kb.py`)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import assert_env, chat_json  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MENUS_PARQUET = PROJECT_ROOT / "data" / "menus.parquet"
KB_PATH = PROJECT_ROOT / "data" / "nutrition_kb.json"
KB_PATH.parent.mkdir(exist_ok=True)

# Longest-first order so multi-character methods take precedence over their suffixes.
COOKING_METHODS = [
    "紅燒", "清蒸", "香煎", "油炸", "乾煎", "乾煸", "醬炒", "醬燒", "醬滷",
    "蜜汁", "焗烤", "白灼", "燒烤", "粉蒸", "鹽烤", "蔥燒", "麻辣", "三杯",
    "滷", "燉", "煮", "炒", "煎", "炸", "烤", "蒸", "拌", "燙", "燴",
    "燒", "煸", "煨", "燻", "焗", "熬", "焢", "煲", "悶", "爆", "烘",
    "汆", "灼", "燜", "炆",
]

BATCH_FOODS = 15
BATCH_COOKS = 15

FOOD_SYS_PROMPT_BASE = """你是台灣國中小學營養午餐健康評估專家。對輸入的食材清單，每個食材回傳：
- food_name: 與輸入完全一致的字串（不可改字、不可加註解）
- summary: 40~80 字繁體中文，依序提到「營養特點 / 潛在風險（過敏、加工、鈉糖油） / 推測小孩接受度」
- score: 整數 0~5（5=最健康，0=最不健康）

評分標準：
- 5：新鮮蔬菜、新鮮水果、原型未加工豆類、優質原型蛋白（魚、雞、蛋）
- 4：全穀、原型紅肉、輕加工但無添加（板豆腐、生豆包、糙米）
- 3：常見家常食材、中度加工（豆干、油豆腐、麵類、白米、香菇）
- 2：油炸或重醃加工品（炸物、醃菜、香腸、培根）
- 1：高鈉/高糖/重加工品（罐頭調味料、加工肉品、素料、湯圓）
- 0：高度加工或營養價值極低、添加物極多

只輸出合法 JSON，不得含任何註解或 markdown 程式碼框：
{"foods":[{"food_name":"...","summary":"...","score":0}, ...]}"""

COOK_SYS_PROMPT_BASE = """你是台灣國中小學營養午餐健康評估專家。對輸入的烹飪手法清單，每個手法回傳：
- cook_name: 與輸入完全一致的字串
- summary: 30~60 字繁體中文，提及「用油量 / 鈉糖添加 / 營養保留度」
- score: 整數 0~5（5=最健康，0=最不健康）

評分標準：
- 5：蒸、煮、燙、汆、白灼（少油少添加）
- 4：拌、滷（少油但鹽糖多）
- 3：炒、煎、煨、燉、烤（中度油溫）
- 2：紅燒、燴、燒、爆、三杯（油與糖醬較多）
- 1：油炸、乾煎、香煎、煸、燻（高油或高溫）
- 0：高度油炸或極重糖醬

只輸出合法 JSON：
{"cooks":[{"cook_name":"...","summary":"...","score":0}, ...]}"""

# Calibration anchors: representative items spanning the 0-5 score range.
# Used as few-shot examples so the LLM matches the existing KB's tone & scoring.
FOOD_ANCHORS = [
    "高麗菜", "雞胸肉", "蘋果",          # 5
    "板豆腐", "地瓜", "雞腿",             # 4
    "白米", "豆干", "雞翅", "香菇",       # 3
    "油豆腐", "菜脯", "甜不辣",           # 2
    "培根", "油麵", "素肉", "奶皇包",     # 1
]

COOK_ANCHORS = [
    "蒸", "燙",                # 5
    "拌", "滷", "燉",          # 4
    "炒", "煎", "烤",          # 3
    "紅燒", "燴", "三杯",      # 2
    "油炸", "煙燻", "乾煸",    # 1
]


def _build_prompt_with_anchors(base_prompt: str, kb_items: list, anchors: list[str], name_field: str) -> str:
    """Inject a few-shot calibration block from the existing KB into the system prompt.

    The block shows score-anchored examples so the LLM mimics the established tone
    and keeps relative scoring consistent with what's already in the KB.
    """
    by_name = {x[name_field]: x for x in kb_items}
    picked: list[dict] = []
    for name in anchors:
        item = by_name.get(name)
        if item is not None:
            picked.append({name_field: name, "summary": item["summary"], "score": item["score"]})
    if not picked:
        return base_prompt

    # Sort by score desc so high-quality anchors come first
    picked.sort(key=lambda x: -x["score"])
    examples = json.dumps({name_field.split("_")[0] + "s": picked}, ensure_ascii=False, indent=2)
    return (
        base_prompt
        + "\n\n以下是已建立的部分評分範例。請嚴格遵循相同的 summary 句法結構（用「分號」分節，"
        "依序「營養特點/潛在風險/接受度」）、相近字數，並維持與這些範例相對一致的評分標準：\n"
        + examples
    )


def extract_cooking_methods(dish_name: str) -> list[str]:
    """Return cooking method tokens found in dish_name, deduped, longer matches preferred."""
    if not isinstance(dish_name, str):
        return []
    found: list[str] = []
    for m in COOKING_METHODS:  # already longest-first
        if m in dish_name:
            # skip if already covered by a longer match
            if any(m != other and m in other for other in found):
                continue
            if m not in found:
                found.append(m)
    return found


def load_kb() -> dict:
    if KB_PATH.exists():
        try:
            return json.loads(KB_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ! existing {KB_PATH} is corrupt; starting fresh", file=sys.stderr)
    return {"foods": [], "cooks": []}


def save_kb(kb: dict) -> None:
    tmp = KB_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(KB_PATH)


def _validate(items: list, name_field: str, requested: list[str]) -> list[dict]:
    by_name = {x.get(name_field, ""): x for x in items if isinstance(x, dict)}
    valid: list[dict] = []
    for name in requested:
        x = by_name.get(name)
        if not x:
            print(f"  ! missing '{name}' in response", file=sys.stderr)
            continue
        score = x.get("score")
        if not isinstance(score, int) or not 0 <= score <= 5:
            try:
                score = int(score)
                if not 0 <= score <= 5:
                    raise ValueError
            except (ValueError, TypeError):
                print(f"  ! invalid score for '{name}': {x.get('score')!r}", file=sys.stderr)
                continue
        valid.append(
            {
                name_field: name,
                "summary": str(x.get("summary", "")).strip(),
                "score": score,
            }
        )
    return valid


def score_foods(items: list[str], sys_prompt: str) -> list[dict]:
    user = "請評估以下食材清單：\n" + "\n".join(f"- {x}" for x in items)
    resp = chat_json(sys_prompt, user, max_tokens=4096, temperature=0.3)
    return _validate(resp.get("foods", []), "food_name", items)


def score_cooks(items: list[str], sys_prompt: str) -> list[dict]:
    user = "請評估以下烹飪手法清單：\n" + "\n".join(f"- {x}" for x in items)
    resp = chat_json(sys_prompt, user, max_tokens=2048, temperature=0.3)
    return _validate(resp.get("cooks", []), "cook_name", items)


def chunked(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main():
    assert_env()
    if not MENUS_PARQUET.exists():
        raise SystemExit(f"missing {MENUS_PARQUET}; run stage0 first")

    df = pd.read_parquet(MENUS_PARQUET)
    print(f"loaded {len(df):,} dish instances from {MENUS_PARQUET.name}")

    all_ings: set[str] = set()
    for ings in df["ingredients"]:
        all_ings.update(ings)
    all_ings = {x for x in all_ings if isinstance(x, str) and x.strip()}
    print(f"  unique ingredients          : {len(all_ings):,}")

    all_dishes = df["dish_name"].dropna().unique().tolist()
    all_cooks: set[str] = set()
    for dn in all_dishes:
        for m in extract_cooking_methods(dn):
            all_cooks.add(m)
    print(f"  unique cooking methods      : {len(all_cooks):,}")
    print(f"  detected methods            : {sorted(all_cooks)}")

    kb = load_kb()
    done_foods = {f["food_name"] for f in kb["foods"]}
    done_cooks = {c["cook_name"] for c in kb["cooks"]}

    todo_foods = sorted(all_ings - done_foods)
    todo_cooks = sorted(all_cooks - done_cooks)

    food_sys_prompt = _build_prompt_with_anchors(
        FOOD_SYS_PROMPT_BASE, kb["foods"], FOOD_ANCHORS, "food_name"
    )
    cook_sys_prompt = _build_prompt_with_anchors(
        COOK_SYS_PROMPT_BASE, kb["cooks"], COOK_ANCHORS, "cook_name"
    )
    food_anchor_hits = sum(1 for n in FOOD_ANCHORS if n in done_foods)
    cook_anchor_hits = sum(1 for n in COOK_ANCHORS if n in done_cooks)

    print()
    print(f"foods to score: {len(todo_foods):,}  (skipping {len(done_foods):,} already done)")
    print(f"  -> using {food_anchor_hits}/{len(FOOD_ANCHORS)} calibration anchors from existing KB")
    print(f"cooks to score: {len(todo_cooks):,}  (skipping {len(done_cooks):,} already done)")
    print(f"  -> using {cook_anchor_hits}/{len(COOK_ANCHORS)} calibration anchors from existing KB")

    # ---------------- foods ----------------
    food_batches = list(chunked(todo_foods, BATCH_FOODS))
    for i, batch in enumerate(food_batches, 1):
        print(f"  [foods {i}/{len(food_batches)}] scoring {len(batch)} items ...")
        try:
            scored = score_foods(batch, food_sys_prompt)
        except Exception as e:
            print(f"    FAILED batch: {e}", file=sys.stderr)
            continue
        existing = {f["food_name"] for f in kb["foods"]}
        for s in scored:
            if s["food_name"] not in existing:
                kb["foods"].append(s)
                existing.add(s["food_name"])
        save_kb(kb)
        print(f"    -> {len(scored)}/{len(batch)} valid (KB total foods: {len(kb['foods'])})")

    # ---------------- cooks ----------------
    cook_batches = list(chunked(todo_cooks, BATCH_COOKS))
    for i, batch in enumerate(cook_batches, 1):
        print(f"  [cooks {i}/{len(cook_batches)}] scoring {len(batch)} items ...")
        try:
            scored = score_cooks(batch, cook_sys_prompt)
        except Exception as e:
            print(f"    FAILED batch: {e}", file=sys.stderr)
            continue
        existing = {c["cook_name"] for c in kb["cooks"]}
        for s in scored:
            if s["cook_name"] not in existing:
                kb["cooks"].append(s)
                existing.add(s["cook_name"])
        save_kb(kb)
        print(f"    -> {len(scored)}/{len(batch)} valid (KB total cooks: {len(kb['cooks'])})")

    print()
    print(f"final KB: {len(kb['foods'])} foods, {len(kb['cooks'])} cooks")
    print(f"wrote {KB_PATH}")


if __name__ == "__main__":
    main()
