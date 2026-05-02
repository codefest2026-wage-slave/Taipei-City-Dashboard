import re
import sys
from pathlib import Path

import pandas as pd

INPUT_FILE = Path("食品查核及檢驗資訊平台2026-05-02.csv")
OUTPUT_FILE = Path("食品查核及檢驗資訊平台2026-05-02_台北新北.csv")
NORMALIZED_OUTPUT_FILE = Path("食品查核及檢驗資訊平台2026-05-02_台北新北_標準化.csv")
INDIVIDUAL_OUTPUT_FILE = Path("食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場.csv")
BUSINESS_OUTPUT_FILE = Path("食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者.csv")

TARGET_CITIES = ("台北市", "臺北市", "新北市")


# ============================================================
# 個人農場/小戶 vs 商業業者 判別規則
# ============================================================
# 判定條件（兩者都成立才視為個人農場）：
#   1. 業者地址僅含縣市/區，沒有具體路名街巷門牌
#   2. 業者名稱不含「公司/有限公司/超市/餐廳…」等商業字詞
# 兩條都過 = 個人 / 小型農戶 / 自家養殖戶之類

# 地址具體化標記（出現任一個 = 有具體門牌 = 非個人小戶）
DETAILED_ADDRESS_MARKERS = (
    "路", "街", "巷", "弄", "號", "段", "大道",
)

# 業者名稱中常見的商業/組織字詞
BUSINESS_NAME_KEYWORDS = (
    "公司", "有限", "股份", "企業", "集團", "合作社", "農會", "工會",
    "工廠", "工場", "工坊", "工作室", "事務所", "中心",
    "超市", "超商", "百貨", "賣場", "市集",
    "便利", "商店", "商行", "商號", "商社", "貿易", "批發",
    "餐廳", "餐飲", "食堂", "食坊", "食品", "美食", "小吃",
    "館", "堂", "軒", "屋", "坊", "店", "舖", "鋪", "閣", "苑",
    "烘焙", "烘培", "甜點", "蛋糕", "麵包", "飲料", "茶飲", "咖啡",
    "火鍋", "燒烤", "壽司", "便當", "雞排", "鹹酥雞", "鹽酥雞",
    "麵店", "麵館", "牛肉麵", "夜市", "攤",
    "市場", "農場", "牧場", "果園",
    "Cafe", "Café", "MART", "Mall", "STORE", "SHOP",
    "全聯", "家樂福", "迪卡儂", "迪卡農", "大潤發", "好市多",
    "全家", "萊爾富", "美廉社",
)


def is_individual(name: str, address: str) -> bool:
    """名稱像人名 + 地址無具體門牌 → 視為個人農場/小戶。"""
    name = (name or "").strip()
    address = (address or "").strip()
    if not name or not address:
        return False
    if any(marker in address for marker in DETAILED_ADDRESS_MARKERS):
        return False
    if any(kw in name for kw in BUSINESS_NAME_KEYWORDS):
        return False
    return True


# ============================================================
# 違反法條 標準化規則
# ============================================================
# 設計目標：把人為記載差異（食安法 vs 食品安全衛生管理法、頓號 vs 及、
# 標點符號等）統一成可分組的標準格式：
#   違反食安法第X條，依同法第Y條裁處
# 然後依條號做集合，去除「項/款」級別的差異（資料中重複度高、夠抓主要分類）。

# 法名正規化（同義詞 → 統一字串）
LAW_NAME_NORMALIZATION = {
    "食品安全衛生管理法": "食安法",
    "食品安全管理法": "食安法",  # 偶見之異稱（資料中筆誤）
}

# 特例覆寫：完全等於 key 才覆寫，會記入轉換日誌
SPECIAL_CASE_OVERRIDES = {
    "併同上案法式生菜沙拉辦理": "併案處理（參照前案）",
}

# 視為「無有效標示」的值
PLACEHOLDER_VALUES = {"-", "_", "", " ", "—", "－", "／", "/"}
LONE_NUMBER_RE = re.compile(r"^\d+$")  # 例如資料中的 "26", "17", "28"

# 其他法（非食安法）保留為獨立分類
OTHER_LAWS = {
    "臺北市食品安全自治條例": "違反臺北市食品安全自治條例",
    "台北市食品安全自治條例": "違反臺北市食品安全自治條例",
    "健康食品管理法": "違反健康食品管理法",
}

# 切分「違反條」與「裁處條」的關鍵字
SPLIT_BEFORE_PENALTY_RE = re.compile(
    r"(?:依同法|依食安法|爰依同法|爰依食安法|依違反食安法|，依|。依)"
)
ARTICLE_RE = re.compile(r"第\s*(\d+)\s*條")


# 展開「第X、Y條」、「第X及Y條」這類縮寫，讓 ARTICLE_RE 能抓到全部條號
COMPACT_ARTICLE_PATTERNS = [
    (re.compile(r"第\s*(\d+)\s*、\s*(\d+)\s*條"), r"第\1條、第\2條"),
    (re.compile(r"第\s*(\d+)\s*及\s*(\d+)\s*條"), r"第\1條及第\2條"),
    (re.compile(r"第\s*(\d+)\s*,\s*(\d+)\s*條"), r"第\1條,第\2條"),
]


def _expand_compact_articles(text: str) -> str:
    for pat, repl in COMPACT_ARTICLE_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _articles_from(text: str) -> list[str]:
    nums = sorted({int(m.group(1)) for m in ARTICLE_RE.finditer(text)})
    return [f"第{n}條" for n in nums]


def normalize_law(raw: str) -> tuple[str, str]:
    """回傳 (標準化後字串, 轉換說明)。

    轉換說明非空時代表這筆值有特別處理（特例 / 無效 / 無法解析），
    用來寫入轉換日誌供人工審視。
    """
    if raw is None:
        return "未明確標示", "空值"
    text = str(raw).strip().rstrip("。").strip()

    if text in SPECIAL_CASE_OVERRIDES:
        new = SPECIAL_CASE_OVERRIDES[text]
        return new, f"特例覆寫: {text!r} -> {new!r}"

    if text in PLACEHOLDER_VALUES or LONE_NUMBER_RE.match(text):
        return "未明確標示", f"無效標示: {text!r}"

    for keyword, label in OTHER_LAWS.items():
        if keyword in text:
            return label, ""

    body = text
    for orig, new in LAW_NAME_NORMALIZATION.items():
        body = body.replace(orig, new)
    body = _expand_compact_articles(body)

    parts = SPLIT_BEFORE_PENALTY_RE.split(body, maxsplit=1)
    violated_part = parts[0]
    penalty_part = parts[1] if len(parts) > 1 else ""

    violated = _articles_from(violated_part)
    penalty = _articles_from(penalty_part)

    if violated and penalty:
        canonical = (
            f"違反食安法{'、'.join(violated)}，依同法{'、'.join(penalty)}裁處"
        )
    elif violated:
        canonical = f"違反食安法{'、'.join(violated)}"
    elif penalty:
        canonical = f"依食安法{'、'.join(penalty)}裁處"
    else:
        return "未明確標示", f"無法解析: {text!r}"

    return canonical, ""


# ============================================================
# 違反條號 危害等級分級
# ============================================================
# 分級邏輯：
#   critical — 直接危害人體健康（毒物、致病菌、攙偽假冒、超量農藥/動藥）
#   high     — 間接危害健康（GHP衛生不良、添加物超量、宣稱醫療效能）
#   medium   — 影響消費者知情權（標示不全、誇大不實、器具標示）
#   low      — 技術性違規（散裝食品標示細節、字體大小）
#   info     — 無有效資訊或附帶處分（未明確標示、併案）
#
# 依據：食安法（食品安全衛生管理法）各條文規範對象與裁罰級距
#   - 第44條 罰 6萬–2億   → 對應第8/15/16條（食品本體與基礎衛生）
#   - 第45條 罰 4萬–400萬 → 對應第28條（標示廣告不實）
#   - 第47條 罰 3萬–300萬 → 對應第22/25/26/27條（標示）
#   - 第48條 罰 3萬–300萬 → 對應第17條（器具容器衛生）

SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
    "unknown": -1,
}

ARTICLE_SEVERITY: dict[int, dict[str, str]] = {
    8: {
        "level": "high",
        "title": "第8條 食品業者衛生管理（GHP）",
        "reason": "未符合食品良好衛生規範，可能滋生病原與交叉污染",
    },
    15: {
        "level": "critical",
        "title": "第15條 食品/添加物不得有特定情形",
        "reason": "攙偽假冒、致病菌、有毒、超量農藥/動物用藥等，直接危害人體健康",
    },
    16: {
        "level": "critical",
        "title": "第16條 器具容器包裝有毒",
        "reason": "材質有毒或致衛生危害，可能溶出進入食品",
    },
    17: {
        "level": "medium",
        "title": "第17條 器具容器包裝洗潔劑衛生標準",
        "reason": "與食品接觸物之衛生不符標準",
    },
    18: {
        "level": "high",
        "title": "第18條 食品添加物使用標準",
        "reason": "添加物超量或誤用，長期可能危害健康",
    },
    19: {
        "level": "low",
        "title": "第19條 食品衛生標準",
        "reason": "技術性衛生標準違規",
    },
    21: {
        "level": "high",
        "title": "第21條 查驗登記",
        "reason": "未經查驗登記擅自製造販售",
    },
    22: {
        "level": "medium",
        "title": "第22條 包裝食品標示應載事項",
        "reason": "品名、成分、有效日期、原產地等資訊缺失，影響消費判斷",
    },
    24: {
        "level": "medium",
        "title": "第24條 器具容器包裝標示",
        "reason": "材質、廠商等資訊缺失",
    },
    25: {
        "level": "low",
        "title": "第25條 散裝食品標示",
        "reason": "散裝食品品名、原產地等技術性標示違規",
    },
    26: {
        "level": "medium",
        "title": "第26條 器具容器包裝標示遵守事項",
        "reason": "材質、警語、字體大小等標示不符",
    },
    27: {
        "level": "medium",
        "title": "第27條 器具容器包裝販售規定",
        "reason": "未符合販售相關規定",
    },
    28: {
        "level": "high",
        "title": "第28條 標示廣告不實/誇張/醫療效能",
        "reason": "誤導消費者，宣稱醫療效能可能延誤就醫",
    },
    52: {
        "level": "info",
        "title": "第52條 沒入處分",
        "reason": "通常為附帶處分",
    },
}

# 沒帶違反條時，從裁處條反推嚴重度（保守推估）
PENALTY_INFERRED_SEVERITY = {
    44: ("high", "依第44條裁處 → 多源自第8/15/16條"),
    45: ("high", "依第45條裁處 → 多源自第28條"),
    47: ("medium", "依第47條裁處 → 多源自第22/25/26/27條"),
    48: ("medium", "依第48條裁處 → 多源自第17條"),
}

# 非食安法的標準化結果，個別對應
NON_FOODSAFETY_LAW_SEVERITY = {
    "違反健康食品管理法": ("high", "違反健康食品管理法（涉醫療效能宣稱）"),
    "違反臺北市食品安全自治條例": ("medium", "違反地方自治條例"),
    "未明確標示": ("info", "原始資料未提供有效法條資訊"),
    "併案處理（參照前案）": ("info", "附註型紀錄，非獨立違規"),
}


def assess_severity(canonical: str) -> tuple[str, str]:
    """從標準化法條字串回傳 (危害等級, 判斷依據說明)。"""
    if canonical in NON_FOODSAFETY_LAW_SEVERITY:
        return NON_FOODSAFETY_LAW_SEVERITY[canonical]

    violated_part = canonical.split("，")[0] if canonical.startswith("違反") else ""
    violated_nums = sorted(
        {int(m.group(1)) for m in ARTICLE_RE.finditer(violated_part)}
    )

    if violated_nums:
        levels: list[str] = []
        titles: list[str] = []
        unknown: list[int] = []
        for n in violated_nums:
            meta = ARTICLE_SEVERITY.get(n)
            if meta:
                levels.append(meta["level"])
                titles.append(meta["title"])
            else:
                unknown.append(n)
        if levels:
            highest = max(levels, key=lambda lv: SEVERITY_RANK[lv])
            note = "；".join(titles)
            if unknown:
                note += f"（其他未定義條: {unknown}）"
            return highest, note

    # 沒有違反條 → 用裁處條反推
    all_nums = sorted({int(m.group(1)) for m in ARTICLE_RE.finditer(canonical)})
    for n in all_nums:
        if n in PENALTY_INFERRED_SEVERITY:
            level, note = PENALTY_INFERRED_SEVERITY[n]
            return level, note

    return "unknown", f"無法判讀條號（{canonical!r}）"


def main() -> None:
    if not INPUT_FILE.exists():
        print(f"ERROR: 找不到檔案 {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    print(f"讀取: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")
    total = len(df)
    print(f"原始筆數: {total:,}")

    addr_col = "業者地址"
    name_col = "業者名稱(市招)"

    if addr_col not in df.columns or name_col not in df.columns:
        print(f"ERROR: CSV 欄位不符，目前欄位 = {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    addr = df[addr_col].str.strip()
    mask = addr.str.startswith(TARGET_CITIES)
    filtered = df[mask].copy()
    kept = len(filtered)
    print(f"台北市/新北市 命中筆數: {kept:,}（過濾掉 {total - kept:,} 筆）")

    filtered = filtered.sort_values(
        by=name_col,
        key=lambda s: s.str.strip(),
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    print(f"已依「{name_col}」排序")

    filtered.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"已輸出: {OUTPUT_FILE}")

    print("-" * 40)
    print("各城市分布:")
    city_prefix = filtered[addr_col].str.strip().str[:3]
    print(city_prefix.value_counts().to_string())

    print("-" * 40)
    unique_names = filtered[name_col].str.strip().replace("", pd.NA).dropna().unique()
    print(f"不重複業者名稱數量: {len(unique_names):,}")

    sample = list(unique_names)[:20]
    print("前 20 個業者名稱範例:")
    for n in sample:
        print(f"  - {n}")

    name_list_file = Path("業者名稱清單_台北新北.txt")
    name_list_file.write_text(
        "\n".join(sorted(unique_names)),
        encoding="utf-8",
    )
    print(f"已輸出完整清單: {name_list_file}")

    print("-" * 40)
    law_col = "違反之食安法條及相關法"
    if law_col in filtered.columns:
        laws = filtered[law_col].str.strip().replace("", pd.NA).dropna()
        law_counts = laws.value_counts()
        print(f"不重複違反法條數量: {len(law_counts):,}（不含空值，共 {len(laws):,} 筆有違規記錄）")
        print("各違反法條分布:")
        for val, cnt in law_counts.items():
            print(f"  [{cnt:>6,}]  {val}")

        law_file = Path("違反法條清單_台北新北.txt")
        law_file.write_text(
            "\n".join(law_counts.index.astype(str)),
            encoding="utf-8",
        )
        print(f"已輸出法條清單: {law_file}")

        print("-" * 40)
        print("套用法條標準化規則…")
        normalized_col = f"{law_col}_標準化"
        conversion_log: list[tuple[str, str, str]] = []  # (原值, 標準化, 說明)

        def _apply(raw: str) -> str:
            canonical, note = normalize_law(raw)
            if note:
                conversion_log.append((raw, canonical, note))
            return canonical

        filtered[normalized_col] = filtered[law_col].fillna("").map(_apply)

        severity_col = "危害等級"
        severity_reason_col = "危害判斷依據"
        severity_pairs = filtered[normalized_col].map(
            lambda c: assess_severity(c) if c else ("info", "原始資料未提供有效法條資訊")
        )
        filtered[severity_col] = severity_pairs.map(lambda p: p[0])
        filtered[severity_reason_col] = severity_pairs.map(lambda p: p[1])

        filtered.to_csv(
            NORMALIZED_OUTPUT_FILE, index=False, encoding="utf-8-sig"
        )
        print(f"已輸出標準化版本 CSV: {NORMALIZED_OUTPUT_FILE}")

        print("-" * 40)
        print("分離個人農場/小戶 vs 商業業者（含標準化欄位）…")
        individual_mask = filtered.apply(
            lambda r: is_individual(r[name_col], r[addr_col]), axis=1
        )
        individuals = filtered[individual_mask].copy()
        businesses = filtered[~individual_mask].copy()
        print(f"個人農場/小戶: {len(individuals):,} 筆")
        print(f"商業業者    : {len(businesses):,} 筆")

        individuals.to_csv(
            INDIVIDUAL_OUTPUT_FILE, index=False, encoding="utf-8-sig"
        )
        businesses.to_csv(
            BUSINESS_OUTPUT_FILE, index=False, encoding="utf-8-sig"
        )
        print(f"已輸出個人農場 CSV: {INDIVIDUAL_OUTPUT_FILE}")
        print(f"已輸出商業業者 CSV: {BUSINESS_OUTPUT_FILE}")

        if not individuals.empty:
            print("個人農場/小戶 樣本（前 15 筆）:")
            for _, row in individuals.head(15).iterrows():
                print(f"  {row[name_col]}  @  {row[addr_col]}")

        norm_counts = (
            filtered[normalized_col]
            .replace("", pd.NA)
            .dropna()
            .value_counts()
        )
        print(
            f"標準化後不重複法條數量: {len(norm_counts):,}"
            f"（原始 {len(law_counts):,} → 縮減 {len(law_counts) - len(norm_counts):,}）"
        )
        print("各標準化法條分布:")
        for val, cnt in norm_counts.items():
            print(f"  [{cnt:>6,}]  {val}")

        print("-" * 40)
        print("危害等級分布（依違反條判定）:")
        sev_order = ["critical", "high", "medium", "low", "info", "unknown"]
        sev_counts = filtered[severity_col].value_counts()
        for level in sev_order:
            cnt = int(sev_counts.get(level, 0))
            if cnt:
                print(f"  [{cnt:>6,}]  {level}")

        print("-" * 40)
        print("各危害等級下，命中最多的標準化法條（前 5）:")
        for level in sev_order:
            sub = filtered[filtered[severity_col] == level]
            if sub.empty:
                continue
            top = sub[normalized_col].value_counts().head(5)
            print(f"  [{level}] 共 {len(sub):,} 筆")
            for law, cnt in top.items():
                print(f"      [{cnt:>5,}]  {law}")

        if conversion_log:
            log_lines = ["原始值\t標準化\t說明"]
            seen: set[tuple[str, str, str]] = set()
            for raw, canonical, note in conversion_log:
                key = (raw, canonical, note)
                if key in seen:
                    continue
                seen.add(key)
                log_lines.append(f"{raw}\t{canonical}\t{note}")
            log_file = Path("法條轉換日誌_台北新北.tsv")
            log_file.write_text("\n".join(log_lines), encoding="utf-8")
            print(
                f"已輸出轉換日誌（特例/無效/無法解析）: {log_file}"
                f"（共 {len(seen):,} 筆獨立規則）"
            )
    else:
        print(f"WARNING: 找不到欄位 {law_col}")


if __name__ == "__main__":
    main()