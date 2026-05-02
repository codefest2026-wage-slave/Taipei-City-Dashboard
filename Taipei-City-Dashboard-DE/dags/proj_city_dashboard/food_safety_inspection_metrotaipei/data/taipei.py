import importlib.util
import sys
from pathlib import Path

import pandas as pd

# ── 路徑常數 ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

RAW_FILES = [BASE_DIR / "111.csv", BASE_DIR / "112.csv", BASE_DIR / "113.csv"]

TAIPEI_CSV = BASE_DIR / "taipei.csv"
FARM_CSV   = BASE_DIR / "taipei_farm.csv"
BUS_CSV    = BASE_DIR / "taipei_bus.csv"

PLATFORM_FARM = BASE_DIR / "食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場.csv"
PLATFORM_BUS  = BASE_DIR / "食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者.csv"

OUTPUT_FARM = BASE_DIR / "食品查核及檢驗資訊平台2026-05-02_台北新北_個人農場_v2.csv"
OUTPUT_BUS  = BASE_DIR / "食品查核及檢驗資訊平台2026-05-02_台北新北_商業業者_v2.csv"

# ── 郵遞區號白名單 ────────────────────────────────────────────────────────────
TAIPEI_CODES = {100, 103, 104, 105, 106, 108, 110, 111, 112, 114, 115, 116}
NEW_TAIPEI_CODES = {
    207, 208, 220, 221, 222, 223, 224, 226, 227, 228,
    231, 232, 233, 234, 235, 236, 237, 238, 239,
    241, 242, 243, 244, 247, 248, 249, 251, 252, 253,
}
ALLOWED_CODES = TAIPEI_CODES | NEW_TAIPEI_CODES

# ── 平台欄位順序（不含 rank，與平台 CSV 保持相容）────────────────────────────
PLATFORM_COLS = [
    "項次", "業者名稱(市招)", "業者地址", "產品名稱",
    "稽查日期", "稽查/檢驗項目", "稽查/檢驗結果",
    "違反之食安法條及相關法", "裁罰金額", "備註",
    "違反之食安法條及相關法_標準化", "危害等級", "危害判斷依據",
]

OUTPUT_COLS = PLATFORM_COLS

DEDUP_KEYS = ["業者名稱(市招)", "業者地址", "稽查日期"]

# ── 違規類型分類：不符合規定原因 → (標準化法條, 危害等級, 判斷依據) ───────────
#
# 分類邏輯（依 main.py 之條文對照表）：
#
#   食安法第15條 → critical
#     農藥殘留：殺蟲劑, 殺菌劑, 殺草劑, 殺蟎劑, 生長調節劑
#     重金屬：鎘, 鉛, 汞, 砷, 重金屬
#     致病菌：腸桿菌, 大腸桿菌, 沙門氏, 李斯特, 金黃葡萄球菌
#     禁用物質：過氧化氫（漂白/殺菌劑陽性）, 輻射
#     攙偽假冒：攙偽, 假冒, 素摻葷, 真菌毒素, 黃麴毒素
#
#   食安法第16條 → critical
#     容器具有毒物質溶出：塑化劑, DEHP, DBP, 溶出量
#
#   食安法第18條 → high
#     食品添加物超量/誤用：苯甲酸, 己二烯酸, 去水醋酸, 亞硫酸鹽,
#                         防腐劑, 色素, 甜味劑, 糖精
#
#   食安法第26條 → medium
#     容器具包裝標示：分類為「食品容器具」且含「標示」
#
#   食安法第22條 → medium
#     包裝食品標示：含「標示」或「反式脂肪」

_CRITICAL_15_KW = (
    # 農藥
    "殺蟲劑", "殺草劑", "殺蟎劑", "生長調節劑", "殺菌劑",
    # 重金屬
    "重金屬", "鎘", "汞", "砷",
    # 致病菌
    "腸桿菌", "大腸桿菌", "沙門氏", "李斯特", "金黃葡萄球菌",
    # 禁用
    "過氧化氫", "輻射",
    # 攙偽/毒素
    "攙偽", "假冒", "素摻葷", "真菌毒素", "黃麴毒素", "脫氧雪腐",
)

_CRITICAL_16_KW = ("塑化劑", "DEHP", "DBP", "溶出量")

_HIGH_18_KW = (
    "苯甲酸", "己二烯酸", "去水醋酸", "亞硫酸", "防腐劑",
    "色素", "染料", "糖精", "甜味劑",
)

_MEDIUM_KW = ("標示", "反式脂肪")


# ── 從 main.py 載入 is_individual 與 assess_severity ─────────────────────────
def _load_main_fns():
    spec = importlib.util.spec_from_file_location("main", BASE_DIR / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.is_individual, mod.assess_severity


is_individual, _assess_severity = _load_main_fns()



def classify_violation(reason: str, category: str = "") -> tuple[str, str, str]:
    """
    依不符合規定原因（與可選的分類欄位）推斷違反法條、危害等級、判斷依據。

    回傳 (標準化法條, 危害等級, 判斷依據)
    """
    r = str(reason).strip()
    cat = str(category).strip()

    if any(kw in r for kw in _CRITICAL_15_KW):
        law = "違反食安法第15條"
    elif any(kw in r for kw in _CRITICAL_16_KW):
        law = "違反食安法第16條"
    elif any(kw in r for kw in _HIGH_18_KW):
        law = "違反食安法第18條"
    elif any(kw in r for kw in _MEDIUM_KW):
        if "容器" in cat or "器具" in cat or "美耐皿" in cat:
            law = "違反食安法第26條"
        else:
            law = "違反食安法第22條"
    elif r:
        law = "未明確標示"
    else:
        law = "未明確標示"

    severity, rationale = _assess_severity(law)
    return law, severity, rationale


# ── 日期轉換：YYYYMMDD → ROC YYY/M/D ─────────────────────────────────────────
def _to_roc_date(raw: str) -> str:
    s = str(raw).strip()
    if len(s) == 8 and s.isdigit():
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:])
        return f"{y - 1911}/{m}/{d}"
    return s


# ── 解析抽驗地點 ──────────────────────────────────────────────────────────────
def _parse_location(loc: str):
    loc = str(loc).strip()
    if "/" in loc:
        idx = loc.index("/")
        return loc[:idx].strip(), loc[idx + 1:].strip()
    return loc, ""


# ── 欄位對映 ──────────────────────────────────────────────────────────────────
def _map_to_platform(df: pd.DataFrame) -> pd.DataFrame:
    names, addrs = zip(*df["抽驗地點"].map(_parse_location)) if len(df) else ([], [])

    notes = df.apply(
        lambda r: (
            f"[{r['專案名稱']}] {r['不符合規定原因']}"
            if r["專案名稱"] and r["不符合規定原因"]
            else r["專案名稱"] or r["不符合規定原因"] or ""
        ),
        axis=1,
    )

    # 違規分類（依不符合規定原因 + 分類欄位）
    classified = df.apply(
        lambda r: classify_violation(r["不符合規定原因"], r.get("分類", "")),
        axis=1,
    )
    law_std   = classified.map(lambda t: t[0])
    severity  = classified.map(lambda t: t[1])
    reason_note = classified.map(lambda t: t[2])

    out = pd.DataFrame({
        "項次":                        range(1, len(df) + 1),
        "業者名稱(市招)":               list(names),
        "業者地址":                    list(addrs),
        "產品名稱":                    df["檢體名稱"].values,
        "稽查日期":                    df["抽驗日期"].map(_to_roc_date).values,
        "稽查/檢驗項目":               df["分類"].values,
        "稽查/檢驗結果":               df["檢驗結果"].values,
        "違反之食安法條及相關法":        law_std.values,
        "裁罰金額":                    "",
        "備註":                       notes.values,
        "違反之食安法條及相關法_標準化": law_std.values,
        "危害等級":                    severity.values,
        "危害判斷依據":                reason_note.values,
    })

    _REQUIRED = [
        "業者名稱(市招)", "業者地址", "產品名稱", "稽查日期",
        "稽查/檢驗項目", "稽查/檢驗結果",
        "違反之食安法條及相關法", "違反之食安法條及相關法_標準化",
        "危害等級", "危害判斷依據",
    ]
    for col in _REQUIRED:
        out[col] = out[col].replace("", "（未記載）")

    return out[OUTPUT_COLS]


# ── 合併並去重 ─────────────────────────────────────────────────────────────────
def _merge_and_dedup(platform_path: Path, new_df: pd.DataFrame, output_path: Path, label: str):
    platform = pd.read_csv(platform_path, dtype=str).fillna("")
    before_platform = len(platform)

    combined = pd.concat([platform, new_df.astype(str)], ignore_index=True)
    before_dedup = len(combined)

    combined = combined.drop_duplicates(subset=DEDUP_KEYS, keep="first")
    dropped = before_dedup - len(combined)

    # ── 欄位確保 + NaN/"nan" 正規化 ─────────────────────────────────
    std_col     = "違反之食安法條及相關法_標準化"
    raw_law_col = "違反之食安法條及相關法"
    for col in ("危害等級", "危害判斷依據", std_col, raw_law_col):
        if col not in combined.columns:
            combined[col] = ""
        combined[col] = (
            combined[col].fillna("").astype(str)
            .replace({"nan": "", "NaN": "", "None": ""})
        )

    # ── 把空白的「危害等級」依多級 fallback 補回 ────────────────────
    #   優先順序：標準化法條 → 原始法條欄 → ("info", "原始資料未提供有效法條資訊")
    def _infer_severity(row) -> tuple[str, str]:
        std = row[std_col].strip()
        if std:
            lvl, note = _assess_severity(std)
            if lvl:
                return lvl, note

        raw = row[raw_law_col].strip()
        if raw:
            # 直接拿原始法條字串當 canonical 試一次
            lvl, note = _assess_severity(raw)
            if lvl and lvl != "unknown":
                return lvl, note
            # 再退一步用 classify_violation 從文字關鍵字推
            _, lvl2, note2 = classify_violation(raw, "")
            if lvl2:
                return lvl2, note2

        return "info", "原始資料未提供有效法條資訊"

    missing_mask = combined["危害等級"].str.strip() == ""
    if missing_mask.any():
        filled = combined.loc[missing_mask].apply(_infer_severity, axis=1)
        combined.loc[missing_mask, "危害等級"]   = filled.map(lambda p: p[0])
        combined.loc[missing_mask, "危害判斷依據"] = filled.map(lambda p: p[1])

    # ── 最終兜底：保證寫出之前絕無空值 ────────────────────────────
    still_empty = combined["危害等級"].str.strip() == ""
    if still_empty.any():
        combined.loc[still_empty, "危害等級"]   = "info"
        combined.loc[still_empty, "危害判斷依據"] = "原始資料未提供有效法條資訊"

    combined = combined.reset_index(drop=True)
    combined["項次"] = range(1, len(combined) + 1)
    combined[OUTPUT_COLS].to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"  {label}: 平台既有 {before_platform:,} 筆 + 新增 {len(new_df):,} 筆 → 合併後 {before_dedup:,} 筆")
    print(f"  去重捨棄: {dropped:,} 筆 → 最終輸出: {len(combined):,} 筆")
    sev_counts = combined["危害等級"].value_counts()
    for level in ["critical", "high", "medium", "low", "info", "unknown"]:
        cnt = int(sev_counts.get(level, 0))
        if cnt:
            print(f"    {level:8}: {cnt:>5,} 筆")
    print(f"  已輸出: {output_path.name}")


# ── 主流程 ─────────────────────────────────────────────────────────────────────
def main():
    # ── 步驟 1：合併三年抽驗資料並過濾 ──────────────────────────────────────
    print("=" * 60)
    print("步驟 1：讀取並合併 111.csv / 112.csv / 113.csv")
    frames = []
    for f in RAW_FILES:
        if not f.exists():
            print(f"  ERROR: 找不到 {f}", file=sys.stderr)
            sys.exit(1)
        tmp = pd.read_csv(f, dtype=str).fillna("")
        print(f"  {f.name}: {len(tmp):,} 筆")
        frames.append(tmp)
    raw = pd.concat(frames, ignore_index=True)
    print(f"  合併後總筆數: {len(raw):,}")

    def _to_int(v):
        try:
            return int(str(v).strip())
        except ValueError:
            return -1

    raw["_code"] = raw["抽驗行政郵遞區號"].map(_to_int)
    invalid_mask = raw["_code"] == -1
    if invalid_mask.any():
        print(f"  警告：無效郵遞區號 {invalid_mask.sum():,} 筆（已排除）")

    filtered = raw[raw["_code"].isin(ALLOWED_CODES)].drop(columns=["_code"]).reset_index(drop=True)
    excluded = len(raw) - len(filtered) - int(invalid_mask.sum())
    print(f"  過濾後（台北市+新北市）: {len(filtered):,} 筆（排除其他縣市 {excluded:,} 筆）")

    filtered.to_csv(TAIPEI_CSV, index=False, encoding="utf-8-sig")
    print(f"  已輸出: {TAIPEI_CSV.name}")

    # ── 步驟 2：欄位對映 + 違規分類 ─────────────────────────────────────────
    print("=" * 60)
    print("步驟 2：欄位對映 + 違規危害等級分類")
    mapped = _map_to_platform(filtered)
    print(f"  對映完成: {len(mapped):,} 筆")

    sev_counts = mapped["危害等級"].value_counts()
    for level in ["critical", "high", "medium", "low", "info", "unknown"]:
        cnt = int(sev_counts.get(level, 0))
        if cnt:
            print(f"    {level:8}: {cnt:>5,} 筆")

    # ── 步驟 3：個人農場 / 商業業者分流 ─────────────────────────────────────
    print("=" * 60)
    print("步驟 3：個人農場 / 商業業者分流")
    farm_mask = mapped.apply(
        lambda r: is_individual(r["業者名稱(市招)"], r["業者地址"]), axis=1
    )
    farm_df = mapped[farm_mask].reset_index(drop=True)
    bus_df  = mapped[~farm_mask].reset_index(drop=True)
    farm_df["項次"] = range(1, len(farm_df) + 1)
    bus_df["項次"]  = range(1, len(bus_df) + 1)

    farm_df.to_csv(FARM_CSV, index=False, encoding="utf-8-sig")
    bus_df.to_csv(BUS_CSV, index=False, encoding="utf-8-sig")
    print(f"  個人農場: {len(farm_df):,} 筆 → {FARM_CSV.name}")
    print(f"  商業業者: {len(bus_df):,} 筆 → {BUS_CSV.name}")

    # ── 步驟 4：合併個人農場資料 ─────────────────────────────────────────────
    print("=" * 60)
    print("步驟 4：合併 個人農場")
    _merge_and_dedup(PLATFORM_FARM, farm_df, OUTPUT_FARM, "個人農場")

    # ── 步驟 5：合併商業業者資料 ─────────────────────────────────────────────
    print("=" * 60)
    print("步驟 5：合併 商業業者")
    _merge_and_dedup(PLATFORM_BUS, bus_df, OUTPUT_BUS, "商業業者")

    print("=" * 60)
    print("完成！")


if __name__ == "__main__":
    main()
