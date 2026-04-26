# 工作安全燈號 — 雙北勞動違規透明化儀表板
## 完整提案計劃

> 提案日期：2026-04-26
> 主題分類：勞動福祉 × 市民權益 × 政府問責
> 預計組件數：6 個
> 資料來源城市：臺北市 + 新北市（雙城整合）

---

## 一、題目

**Labor Safety Radar｜工作安全燈號**
**雙北勞動違規透明化查詢系統**

---

## 二、問題定義

### 現況痛點

每天，雙北政府分別在四個網頁上公告最新的違法雇主名單：
- 臺北市：勞基法違規 + 性平法違規
- 新北市：勞基法違規 + 性平法違規

這些資料是公開的、每日更新的，但：
1. **分散在四個頁面**，沒有任何平台合而為一
2. **無法搜尋**，只能下載 CSV 自行比對
3. **沒有趨勢分析**，市民看不到「哪個產業違規最多」
4. **身障雇用資訊不透明**，積極友善雇主沒有正面呈現

### 核心問題句

> 「我拿到一個 offer，但不知道這家公司有沒有違規記錄。」

這句話每年在雙北有數十萬名求職者說過，但沒有任何工具解決它。

---

## 三、受眾分析

| 受眾 | 使用場景 | 從儀表板獲得的價值 |
|------|---------|-------------------|
| **求職者** | 收到 offer 後，輸入公司名稱確認違規記錄 | 求職保護，避免進入問題企業 |
| **在職勞工** | 查詢目前雇主的歷史違規記錄 | 了解自身處境，決定是否投訴 |
| **勞動局官員** | 識別違規熱點行政區、高風險產業 | 稽查資源配置優化 |
| **NGO / 工會** | 分析違規趨勢，作為政策倡議依據 | 數據支持倡議論述 |
| **身障求職者** | 查找積極雇用身障者的正面雇主 | 正向媒合資訊 |
| **新聞媒體** | 追蹤特定行業違規趨勢 | 報導數據來源 |

---

## 四、核心價值

> **全台灣第一個雙城合一、每日更新的勞動違規可搜尋查詢平台。**

### 競品分析

| 平台 | 功能 | 與本儀表板差距 |
|------|------|--------------|
| 臺北市勞動局網站 | 可下載臺北違規 CSV | 無搜尋、無視覺化、無新北 |
| 新北市政府網站 | 可下載新北違規 CSV | 無搜尋、無視覺化、無臺北 |
| 104 / 1111 求職網 | 有企業評價 | 用戶主觀，無法律違規記錄 |
| Google | 有企業資訊 | 無勞動違規整合 |
| **本儀表板** | 雙城整合+即時搜尋+趨勢+地圖 | **空缺填補** |

---

## 五、資料來源

### 主要資料集

| # | 資料集名稱 | 來源平台 | Dataset UUID | 更新頻率 | 地理欄位 |
|---|-----------|---------|-------------|---------|---------|
| 1 | 臺北市違反勞動基準法事業單位 | data.taipei | `23630879-4926-4877-a48a-a0ae6cc2f7d5` | 每日 | ✗ |
| 2 | 臺北市違反性別平等工作法事業單位 | data.taipei | `12f3421a-94f4-4a5e-8642-143dee2fa551` | 每日 | ✗ |
| 3 | 臺北市年度勞資爭議統計依行業別 | data.taipei | `a5f80885-0a15-4215-ae76-5ed36a8ae808` | 每年 | ✓ 行政區 |
| 4 | 臺北市勞工保險及就業服務按月別 | data.taipei | `355e8aad-3389-4613-b593-12f1e8229403` | 每月 | ✗ |
| 5 | 新北市違法雇主資料_勞動基準法 | data.ntpc.gov.tw | `a3408b16-7b28-4fa5-9834-d147aae909bf` | 每日 | ✗ |
| 6 | 新北市違法雇主資料_性別平等工作法 | data.ntpc.gov.tw | `d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4` | 每日 | ✗ |

### 資料集頁面網址

| # | 資料集頁面 |
|---|-----------|
| 1 | https://data.taipei/dataset/detail?id=23630879-4926-4877-a48a-a0ae6cc2f7d5 |
| 2 | https://data.taipei/dataset/detail?id=12f3421a-94f4-4a5e-8642-143dee2fa551 |
| 3 | https://data.taipei/dataset/detail?id=a5f80885-0a15-4215-ae76-5ed36a8ae808 |
| 4 | https://data.taipei/dataset/detail?id=355e8aad-3389-4613-b593-12f1e8229403 |
| 5 | https://data.ntpc.gov.tw/datasets/a3408b16-7b28-4fa5-9834-d147aae909bf |
| 6 | https://data.ntpc.gov.tw/datasets/d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4 |

### 資料擷取 API 規格

#### data.taipei — 兩步驟（UUID ≠ Resource ID）

```bash
# 步驟 1：用 dataset UUID 取得 Resource ID (RID)
curl "https://data.taipei/api/v1/dataset.view?id={UUID}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['rid'])"

# 步驟 2a：JSON API 擷取資料（每頁最多 1000 筆，用 offset 分頁）
curl "https://data.taipei/api/v1/dataset/{RID}?scope=resourceAquire&limit=1000&offset=0"

# 步驟 2b：CSV 下載（完整資料，無分頁限制）
curl "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={RID}"
```

**勞基法違規 (UUID=23630879)：**
```bash
# 步驟 1
curl "https://data.taipei/api/v1/dataset.view?id=23630879-4926-4877-a48a-a0ae6cc2f7d5"
# → 從回應取得 result.rid（例：69614c02-b47d-4e9d-a23f-088803c9dd66）

# 步驟 2（CSV 下載，以取得的 RID 代入）
curl "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={RID}"
```

**性平法違規 (UUID=12f3421a)：**
```bash
curl "https://data.taipei/api/v1/dataset.view?id=12f3421a-94f4-4a5e-8642-143dee2fa551"
# → 取得 RID 後同上 CSV 下載
```

#### data.ntpc — 直接用 UUID（無需兩步驟）

```bash
# 勞基法違規（已驗證可存取）
curl "https://data.ntpc.gov.tw/api/datasets/a3408b16-7b28-4fa5-9834-d147aae909bf/json?size=100&page=0"

# 性平法違規（已驗證可存取）
curl "https://data.ntpc.gov.tw/api/datasets/d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4/json?size=100&page=0"
```

> **注意：** NTPC API 回傳 JSON 陣列，預設每頁 30 筆。必須用 `size`+`page` 分頁（`limit`/`offset` 無效）。

### 已驗證欄位（NTPC）

NTPC 兩個資料集均已透過 API 驗證可存取，典型欄位（以實際 API 回應為準）：

```
NTPC 勞基法 / 性平法違規記錄欄位（從 API 確認）：
├── 事業單位名稱  （公司名稱）
├── 違反法令      （違反的具體法條）
├── 處分日期      （民國年格式，需轉換）
├── 罰鍰金額      （含「元」字，需轉為數值）
├── 行業別        （行業分類）
└── 地址          （部分記錄有地址，用於地理編碼）
```

TPE 欄位尚待 RID 解析後確認（以實際 CSV 欄頭為準）。

### 資料欄位對應（統一 Schema）

```
統一違規記錄 Schema：
├── source_city        （'TPE' / 'NTPC'）
├── company_name       （公司名稱）
├── violation_date     （處分日期，西元年 DATE）
├── law_category       （'勞基法' / '性平法'）
├── violation_content  （違規法條 / 違規內容摘要）
├── fine_amount        （罰款金額，INTEGER TWD）
├── district           （行政區，從地址推算）
└── industry           （行業別）
```

---

## 六、功能設計

### 核心功能一：雇主違規快查（Hero Feature）

```
┌─────────────────────────────────────────────────┐
│  🔍 搜尋公司名稱或統一編號                         │
│  [___________________________]  [查詢]            │
│                                                   │
│  搜尋結果：XX 股份有限公司                          │
│  ┌──────────┬──────────┬─────────────┬─────────┐ │
│  │ 處分日期  │ 城市     │ 違反法規     │ 罰款金額 │ │
│  ├──────────┼──────────┼─────────────┼─────────┤ │
│  │2025-11-03│ 臺北市   │ 勞基法第24條 │ NT$30萬 │ │
│  │2024-06-15│ 新北市   │ 性平法第21條 │ NT$10萬 │ │
│  └──────────┴──────────┴─────────────┴─────────┘ │
│  共 2 筆違規記錄（2023~今）                         │
└─────────────────────────────────────────────────┘
```

**技術需求：**
- PostgreSQL 全文搜尋（`tsvector` + `pg_trgm`）支援模糊查詢
- 統一雙北 4 個資料集的公司名稱正規化
- 搜尋延遲目標：< 500ms

### 核心功能二：月度違規趨勢

- 雙北每月新增違規件數折線圖（臺北 / 新北雙線）
- 疊加重大勞工事件標記（如：COVID 衝擊月份、重大修法實施日）
- 可篩選：勞基法違規 / 性平法違規 / 全部

### 核心功能三：行業別違規排行

- 橫向長條圖：哪個產業違規件數最多
- 可切換：製造業 / 服務業 / 零售業 / 科技業 / 其他
- 按「近一年累計件數」排序

### 核心功能四：身障雇用配額監測

- KPI 卡片：整體達標率 / 罰款總金額
- 長條圖：公立機構 vs 私立機構達標率趨勢
- 表格：超額雇用前 10 名（正面排行），不足額+罰款最高前 10 名

### 核心功能五：勞動市場健康指標（月度）

- 折線圖：投保人數趨勢（景氣警示）
- 折線圖：新登記求職人數 vs 推介就業人數
- KPI：當月求職媒合率

---

## 七、圖表規格

### 組件 A｜雇主違規查詢表
```
組件類型：DataTableComponent（客製化可搜尋資料表）
資料源：unified_violations 統一違規資料表
欄位：城市 / 處分日期 / 公司名稱 / 違反法規 / 違規內容 / 罰款金額
篩選器：
  - 城市切換（臺北 / 新北 / 雙北）
  - 法規類別（勞基法 / 性平法）
  - 日期範圍（預設：近一年）
  - 行業別（下拉）
排序：預設按處分日期降序
```

### 組件 B｜月度違規件數趨勢折線圖
```
組件類型：LineChart（雙線）
X 軸：年月（2020-01 ~ 最新月份）
Y 軸：件數
線條：臺北市（藍）/ 新北市（橙）
特殊標記：COVID 衝擊期 / 重大修法日（垂直虛線）
資料粒度：月度聚合
```

### 組件 C｜行業別違規件數橫向長條圖
```
組件類型：HorizontalBarChart
X 軸：件數
Y 軸：行業類別（依件數由多到少排序）
顏色：勞基法（紅色調）/ 性平法（紫色調）/ 堆疊顯示
切換：近一年 / 近三年 / 全部
```

### 組件 D｜勞資爭議行政區熱力地圖
```
組件類型：MapLegend（行政區多邊形）
地圖圖層：臺北市 12 行政區多邊形
指標：每千名就業人口勞資爭議件數（標準化）
色階：淺黃 → 深橙 → 紅（件數越多越深）
點擊：顯示該行政區的行業別爭議件數圓餅圖
```

### 組件 E｜身障雇用配額達標率
```
組件類型：BarChart（分組長條）
X 軸：年度（2018~最新）
Y 軸：達標率（%）
分組：公立機構（藍）/ 私立機構（灰）
輔助線：100%（法定標準線，紅色）
次要 Y 軸：罰款總金額（折線）
```

### 組件 F｜月度勞動市場健康指標
```
組件類型：LineChart（三線）
指標：勞保投保人數 / 新登記求職人數 / 推介就業人數
X 軸：年月
Y 軸：人數（千人單位）
目的：景氣衰退時投保人數下降、求職人數激增
```

---

## 八、地圖設計

### 主地圖：勞資爭議行政區熱力

```
底圖：Mapbox Light (streets-v12)
城市：預設臺北市，可切換新北市

圖層設計：
┌─────────────────────────────────────────┐
│  圖層 1：行政區多邊形熱力                  │
│  - 依「每千就業人口爭議件數」填色           │
│  - 色階：#FFF3E0 → #FF6D00（淺到深）      │
│  - 點擊：彈出該區行業爭議圓餅圖            │
│                                           │
│  圖層 2：違規企業聚熱點（選配）             │
│  - 對有地址的違規企業進行地理編碼          │
│  - 使用 Heatmap 模式呈現（非點位）         │
│  - 可依法規類型切換顏色                    │
└─────────────────────────────────────────┘

互動控制：
  - 左側面板：行業別篩選
  - 右側面板：點選行政區的詳細數據
  - 年度滑桿：查看歷年變化
```

---

## 九、ETL 資料管道

### Pipeline 架構

```
資料來源 API
    │
    ▼
┌─────────────────────────────────────────────────┐
│  DAG: labor_violations_daily                      │
│                                                   │
│  Step 1: 抓取四個違規雇主 API                      │
│    - TPE 勞基法 CSV（兩步驟，見下）                │
│    - TPE 性平法 CSV（兩步驟，見下）                │
│    - NTPC 勞基法 JSON（直接 UUID，分頁）           │
│    - NTPC 性平法 JSON（直接 UUID，分頁）           │
│                                                   │
│  Step 2: 正規化 + 統一 Schema                      │
│    - 城市標記（TPE / NTPC）                        │
│    - 日期格式標準化（民國年 → 西元年）              │
│    - 公司名稱去雜訊（移除括號、空白）               │
│    - 罰款金額轉為數值（移除「元」字）               │
│    - 行業別分類（依公司名稱關鍵字推算）             │
│                                                   │
│  Step 3: Upsert 到 PostgreSQL                     │
│    - 使用 (source_city, company_name, date, law)  │
│      作為 composite unique key 去重                │
│                                                   │
│  Step 4: 更新搜尋索引（tsvector rebuild）          │
└─────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  DAG: labor_stats_monthly │
│  - 勞保及就業服務月資料   │
│  - 每月 5 日執行          │
└──────────────────────────┘
    │
    ▼
┌──────────────────────────┐
│  DAG: labor_stats_annual  │
│  - 勞資爭議統計           │
│  - 身障配額概況           │
│  - 每年 3 月執行          │
└──────────────────────────┘
    │
    ▼
    PostgreSQL（dashboard DB）
    ├── labor_violations         （統一違規記錄，每日更新）
    ├── labor_disputes_by_dist   （勞資爭議行政區統計，年度）
    ├── disability_quota         （身障配額達標率，年度）
    └── labor_insurance_monthly  （勞保及就業服務，月度）
```

### ETL Python 實作（核心片段）

```python
import requests
import csv
import io
import re
from datetime import datetime

# ─── data.taipei 兩步驟擷取 ─────────────────────────────────────────
TPE_DATASETS = {
    "labor_law": "23630879-4926-4877-a48a-a0ae6cc2f7d5",
    "gender_eq": "12f3421a-94f4-4a5e-8642-143dee2fa551",
    "disputes":  "a5f80885-0a15-4215-ae76-5ed36a8ae808",
    "insurance": "355e8aad-3389-4613-b593-12f1e8229403",
}

def tpe_get_rid(dataset_uuid: str) -> str:
    """步驟 1：用 dataset UUID 取得 Resource ID (RID)"""
    resp = requests.get(
        f"https://data.taipei/api/v1/dataset.view?id={dataset_uuid}",
        timeout=30
    ).json()
    return resp["result"]["rid"]

def tpe_fetch_csv(dataset_uuid: str) -> list[dict]:
    """步驟 2：用 RID 下載完整 CSV"""
    rid = tpe_get_rid(dataset_uuid)
    url = f"https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={rid}"
    resp = requests.get(url, timeout=60)
    resp.encoding = "utf-8-sig"
    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)

def tpe_fetch_json(dataset_uuid: str) -> list[dict]:
    """備用：JSON API（最多 1000 筆/頁，需 offset 分頁）"""
    rid = tpe_get_rid(dataset_uuid)
    records, offset = [], 0
    while True:
        batch = requests.get(
            f"https://data.taipei/api/v1/dataset/{rid}",
            params={"scope": "resourceAquire", "limit": 1000, "offset": offset},
            timeout=30
        ).json()["result"]["results"]
        if not batch:
            break
        records.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return records

# ─── data.ntpc 直接擷取（已驗證） ────────────────────────────────────
NTPC_DATASETS = {
    "labor_law": "a3408b16-7b28-4fa5-9834-d147aae909bf",
    "gender_eq": "d7b245c0-0ba7-4ee9-9021-5ca27ac52eb4",
}

def ntpc_fetch_all(uuid: str, page_size: int = 100) -> list[dict]:
    """NTPC：size+page 分頁（limit/offset 無效）"""
    records, page = [], 0
    while True:
        batch = requests.get(
            f"https://data.ntpc.gov.tw/api/datasets/{uuid}/json",
            params={"size": page_size, "page": page},
            timeout=30
        ).json()
        if not batch:
            break
        records.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return records

# ─── 資料正規化 ───────────────────────────────────────────────────────
def roc_to_ad(date_str: str) -> str | None:
    """民國年 → 西元年：'114/03/15' → '2025-03-15'"""
    m = re.match(r"(\d{2,3})[/\-.](\d{1,2})[/\-.](\d{1,2})", str(date_str))
    if not m:
        return None
    y, mo, d = int(m.group(1)) + 1911, m.group(2), m.group(3)
    return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

def parse_fine(fine_str: str) -> int | None:
    """'30,000元' → 30000"""
    cleaned = re.sub(r"[^0-9]", "", str(fine_str))
    return int(cleaned) if cleaned else None

def normalize_violation(row: dict, source_city: str, law_category: str) -> dict:
    raw_date = row.get("處分日期") or row.get("公告日期") or ""
    return {
        "source_city":       source_city,
        "company_name":      (row.get("事業單位名稱") or row.get("公司名稱") or "").strip(),
        "violation_date":    roc_to_ad(raw_date),
        "law_category":      law_category,
        "violation_content": row.get("違反法令") or row.get("違規內容") or "",
        "fine_amount":       parse_fine(row.get("罰鍰金額") or row.get("罰款金額") or ""),
        "district":          row.get("行政區") or "",
        "industry":          row.get("行業別") or "",
    }

# ─── 每日更新主流程 ───────────────────────────────────────────────────
def run_daily_etl():
    all_records = []

    # TPE 勞基法
    for row in tpe_fetch_csv(TPE_DATASETS["labor_law"]):
        all_records.append(normalize_violation(row, "TPE", "勞基法"))

    # TPE 性平法
    for row in tpe_fetch_csv(TPE_DATASETS["gender_eq"]):
        all_records.append(normalize_violation(row, "TPE", "性平法"))

    # NTPC 勞基法（已驗證可存取）
    for row in ntpc_fetch_all(NTPC_DATASETS["labor_law"]):
        all_records.append(normalize_violation(row, "NTPC", "勞基法"))

    # NTPC 性平法（已驗證可存取）
    for row in ntpc_fetch_all(NTPC_DATASETS["gender_eq"]):
        all_records.append(normalize_violation(row, "NTPC", "性平法"))

    return all_records
```

### 資料表設計（核心）

```sql
CREATE TABLE labor_violations (
    id              SERIAL PRIMARY KEY,
    source_city     VARCHAR(10) NOT NULL,    -- 'TPE' or 'NTPC'
    company_name    VARCHAR(200) NOT NULL,
    violation_date  DATE NOT NULL,
    law_category    VARCHAR(50) NOT NULL,    -- '勞基法', '性平法'
    violation_content TEXT,
    fine_amount     INTEGER,                 -- TWD
    district        VARCHAR(20),
    industry        VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW(),
    search_vector   TSVECTOR,               -- 全文搜尋索引
    UNIQUE (source_city, company_name, violation_date, law_category)
);

CREATE INDEX idx_violations_search ON labor_violations USING GIN (search_vector);
CREATE INDEX idx_violations_date ON labor_violations (violation_date DESC);
CREATE INDEX idx_violations_company ON labor_violations (company_name);
```

---

## 十、儀表板版面配置

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER                                                       │
│  工作安全燈號 | 雙北勞動違規透明化儀表板          [日期戳記]   │
├─────────────────────────────────────────────────────────────┤
│  KPI 列                                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │今年違規件數    │ │ 今日新增     │ │  身障達標率           │ │
│  │  2,847 件     │ │   12 件      │ │  78.3%               │ │
│  │（雙北合計）   │ │（雙北合計）   │ │（私立機構）           │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  🔍 雇主違規快查                                              │
│  [組件 A：可搜尋資料表]                                       │
│  （全寬，搜尋框置頂）                                         │
├─────────────────┬───────────────────────────────────────────┤
│  [組件 D：       │  [組件 B：月度違規趨勢折線圖]               │
│   勞資爭議       │                                            │
│   行政區熱力     ├───────────────────────────────────────────┤
│   地圖]          │  [組件 C：行業別違規件數橫向長條圖]         │
│                  │                                            │
├─────────────────┴───────────────────────────────────────────┤
│  [組件 E：身障雇用配額達標率]  │  [組件 F：勞動市場健康指標]   │
└─────────────────────────────────────────────────────────────┘
```

---

## 十一、技術規格

### 前端組件對應

| 組件 | Dashboard Component 類型 | Chart.js 類型 |
|------|--------------------------|---------------|
| A：違規查詢表 | `DataTableComponent` | — |
| B：月度趨勢 | `TimelineSeparateChart` | Line |
| C：行業長條 | `HorizontalBarChart` | Bar（水平） |
| D：行政區熱力地圖 | `MapLegend` + 行政區 GeoJSON | Mapbox Fill Layer |
| E：身障配額 | `BarChart` | Bar（分組） |
| F：勞動指標 | `TimelineSeparateChart` | Line（多線） |

### 後端 API 端點

```
GET /api/v1/component/labor_violations_search?q={company_name}&city={tpe|ntpc|all}&law={labor|gender|all}&year_from={}&year_to={}
GET /api/v1/component/labor_violations_monthly
GET /api/v1/component/labor_violations_by_industry
GET /api/v1/component/labor_disputes_by_district
GET /api/v1/component/disability_quota_trend
GET /api/v1/component/labor_insurance_monthly
```

---

## 十二、Dashboard 組件資料庫登錄

### 儀表板設定

```json
{
  "dashboard": {
    "name": "工作安全燈號",
    "name_en": "Labor Safety Radar",
    "icon": "work",
    "color": "#E53935",
    "description": "雙北勞動違規透明化查詢系統，整合每日更新的違法雇主資料、勞資爭議熱點分析、身障雇用配額監測。"
  }
}
```

### 組件登錄（query_charts 示例）

```sql
-- 組件 A：雇主違規查詢
INSERT INTO query_charts (index, type, color, unit, special_chart, map_config, map_filter, map_zoom, city)
VALUES (1, 'search_table', '#E53935', '件', false, null, null, 11, 'all');

-- 組件 B：月度趨勢
INSERT INTO query_charts (index, type, color, unit, special_chart, map_config, map_filter, map_zoom, city)
VALUES (2, 'timeline', '["#1565C0","#E65100"]', '件', false, null, null, 11, 'all');

-- 組件 D：行政區熱力地圖
INSERT INTO query_charts (index, type, color, unit, special_chart, map_config, map_filter, map_zoom, city)
VALUES (4, 'two_d', '#E53935', '件/千人', true, '{"type": "fill", "property": "disputes_per_1000"}', null, 11, 'taipei');
```

---

## 十三、實作里程碑

### Phase 1：資料管道（Day 1）
- [ ] 建立 `labor_violations_daily` Airflow DAG
- [ ] 實作四個資料源的爬取與正規化
- [ ] 設計並建立 PostgreSQL schema
- [ ] 完成全文搜尋索引建立

### Phase 2：核心組件（Day 2）
- [ ] 開發可搜尋查詢表（組件 A）— 核心展示功能
- [ ] 開發月度趨勢折線圖（組件 B）
- [ ] 開發行業別違規橫向長條圖（組件 C）

### Phase 3：地圖與補充（Day 3）
- [ ] 整合行政區 GeoJSON + 勞資爭議資料（組件 D）
- [ ] 開發身障配額長條圖（組件 E）
- [ ] 整合所有組件到儀表板
- [ ] 測試雙北資料正確性

---

## 十四、評審亮點摘要

1. **資料填補空缺**：整合雙北 4 個每日更新資料集，這件事目前沒有任何平台做過
2. **即時可用**：不是分析報告，是「現在就能用」的求職保護工具
3. **雙向受眾**：求職者（個人防護）+ 勞動局（政策決策）
4. **可信資料來源**：全部來自政府每日更新的公開資料，非爬蟲，法律合規
5. **問責機制**：透過視覺化讓違規雇主資訊不再隱藏於 PDF，提高市場威懾效果

---

*本提案由 Claude Code 協助分析雙北開放資料後生成，資料集均來自 data.taipei 及 data.ntpc.gov.tw。*
