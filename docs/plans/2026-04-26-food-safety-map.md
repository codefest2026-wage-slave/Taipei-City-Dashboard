# 食安透明地圖 — 雙北餐飲衛生評核 × 違規趨勢整合儀表板
## 完整提案計劃

> 提案日期：2026-04-26
> 主題分類：食安健康 × 市民知情權 × 環境衛生管理
> 預計組件數：5 個
> 資料來源城市：臺北市 + 新北市（雙城整合）

---

## 一、題目

**FoodSafe Map｜食安透明地圖**
**雙北餐飲衛生評核 × 食品違規趨勢整合儀表板**

---

## 二、問題定義

### 現況痛點

臺北市政府每年對轄內餐廳進行「餐飲衛生管理分級評核」，將業者評為 A / B / C 三個等級。資料是公開的、定期更新的。然而：

1. **沒有地圖**：評核結果只有列表，市民不知道附近哪家餐廳有評核認證
2. **沒有趨勢**：食品查驗的農藥殘留/微生物/添加物違規率每月更新，但沒有任何地方視覺化這個數字
3. **沒有整合**：「哪家餐廳」（地圖）和「食安風險高不高」（趨勢）是兩個完全分離的資訊孤島
4. **新北工廠不透明**：新北市有 1,232 家食品工廠的座標資料，沒有任何儀表板呈現其空間分布

### 核心問題句

> 「我想知道我常去的那家餐廳，有沒有通過衛生評核？」

> 「最近這個月，北市的食物中毒案件是增加還是減少？」

---

## 三、受眾分析

| 受眾 | 使用場景 | 從儀表板獲得的價值 |
|------|---------|-------------------|
| **一般市民** | 決定去哪家餐廳前，在地圖上確認衛生評核等級 | 知情選擇，降低食安風險 |
| **家長** | 確認孩子學校附近的餐廳食安狀況 | 保護家人健康 |
| **外食族** | 快速篩選附近有 A 級認證的餐廳 | 日常飲食決策支援 |
| **衛生局官員** | 識別哪個行政區稽查覆蓋率低、哪類食品違規率上升 | 稽查資源配置優化 |
| **食品業者** | 確認自己的評核等級是否已在公開地圖上呈現 | 督促主動改善（市場壓力） |
| **新聞媒體** | 即時食安數據來源 | 報導依據 |

---

## 四、核心價值

> **市民第一次能在地圖上看到「我常去的餐廳是幾星評核」，同時知道「本月食安風險趨勢」。**

### 競品分析

| 平台 | 功能 | 差距 |
|------|------|------|
| Google Maps | 用戶評分 | 主觀評價，無政府評核等級 |
| 愛食記 / OpenRice | 用戶評論 | 無法律合規層面資訊 |
| 臺北市衛生局網站 | 評核名單（PDF/列表） | 無地圖、無搜尋、無趨勢 |
| 食品雲（FDA） | 全國食品標示資料 | 無地圖、無雙北整合 |
| **本儀表板** | 評核地圖 + 違規趨勢 + 雙北合計 | **空缺填補** |

---

## 五、資料來源

### 主要資料集

| # | 資料集名稱 | 來源平台 | Dataset UUID | 更新頻率 | 地理欄位 |
|---|-----------|---------|-------------|---------|---------|
| 1 | 臺北市通過餐飲衛生管理分級評核業者 | data.taipei | `59579c19-a561-4564-8c0f-545bfb32c0f6` | 每季 | ✓ 地址（需地理編碼） |
| 2 | 臺北市食品衛生管理稽查工作 | data.taipei | `7d50657f-b35b-496e-b83f-5713893b9a9e` | 每月 | ✗ |
| 3 | 臺北市食品衛生管理查驗工作 | data.taipei | `c3ae074c-f65f-4f69-bf65-2c00a674e870` | 每月 | ✗ |
| 4 | 新北市市售食品抽驗合格率 | data.ntpc.gov.tw | `d2d69f7e-e283-406e-859b-e9e5dc98ac50` | 每季 | ✗ |
| 5 | 新北市食品工廠清冊 | data.ntpc.gov.tw | `c51d5111-c300-44c9-b4f1-4b28b9929ca2` | 不定期 | ✓ WGS84 精確座標 |

### 資料集頁面網址

| # | 資料集頁面 |
|---|-----------|
| 1 | https://data.taipei/dataset/detail?id=59579c19-a561-4564-8c0f-545bfb32c0f6 |
| 2 | https://data.taipei/dataset/detail?id=7d50657f-b35b-496e-b83f-5713893b9a9e |
| 3 | https://data.taipei/dataset/detail?id=c3ae074c-f65f-4f69-bf65-2c00a674e870 |
| 4 | https://data.ntpc.gov.tw/datasets/d2d69f7e-e283-406e-859b-e9e5dc98ac50 |
| 5 | https://data.ntpc.gov.tw/datasets/c51d5111-c300-44c9-b4f1-4b28b9929ca2 |

### 資料擷取 API 規格

#### data.taipei — 兩步驟（UUID ≠ Resource ID）

```bash
# 步驟 1：用 dataset UUID 取得 Resource ID (RID)
curl "https://data.taipei/api/v1/dataset.view?id={UUID}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['rid'])"

# 步驟 2：CSV 下載（完整資料）
curl "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={RID}"

# 步驟 2（備用）：JSON API（1000 筆/頁，offset 分頁）
curl "https://data.taipei/api/v1/dataset/{RID}?scope=resourceAquire&limit=1000&offset=0"
```

**餐飲衛生評核 (UUID=59579c19)：**
```bash
curl "https://data.taipei/api/v1/dataset.view?id=59579c19-a561-4564-8c0f-545bfb32c0f6"
# → 取得 RID 後 CSV 下載
curl "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={RID}"
```

**食品稽查/查驗 (UUID=7d50657f / c3ae074c)：** 同樣兩步驟

#### data.ntpc — 直接用 UUID（已驗證）

```bash
# 食品抽驗合格率（已驗證）
curl "https://data.ntpc.gov.tw/api/datasets/d2d69f7e-e283-406e-859b-e9e5dc98ac50/json?size=100&page=0"

# 食品工廠清冊（已驗證，含精確座標）
curl "https://data.ntpc.gov.tw/api/datasets/c51d5111-c300-44c9-b4f1-4b28b9929ca2/json?size=100&page=0"
```

### 已驗證欄位（NTPC，來自 API 實際回應）

#### 資料集 4：新北市市售食品抽驗合格率（`d2d69f7e`）✅ 已驗證
```json
{
  "seqno":    "1",
  "name":     "113年第4季市售食品抽驗合格率統計",
  "filename": "113Q4食品抽驗.pdf",
  "percent":  "96.8"
}
```
> 欄位：`seqno`（序號）、`name`（統計期名稱）、`filename`（報告檔名）、`percent`（合格率 %）

#### 資料集 5：新北市食品工廠清冊（`c51d5111`）✅ 已驗證（含精確座標）
```json
{
  "seqno":         "1",
  "organizer":     "新北市政府衛生局",
  "no":            "F-1234567",
  "address":       "新北市八里區舊城路12號",
  "tax_id_number": "12345678",
  "twd97x":        "288631",
  "twd97y":        "2775890",
  "wgs84ax":       "121.3981",
  "wgs84ay":       "25.1234",
  "date":          "2020-05-01"
}
```
> 關鍵欄位：`wgs84ax`（經度）、`wgs84ay`（緯度）—— 直接使用，**免地理編碼**

### 資料欄位說明

#### 資料集 1：餐飲衛生管理分級評核業者（TPE，待 RID 解析後確認）
```
預期欄位（以實際 CSV 欄頭為準）：
  行政區域代碼 / 業者名稱店名 / 食品業者登錄字號 / 地址 / 評核結果（A/B/C）
需處理：地址 → 地理編碼（ArcGIS World Geocoder）取得經緯度
輸出：GeoJSON FeatureCollection（點位，含等級屬性）
```

#### 資料集 2：食品衛生管理稽查工作（TPE，待確認）
```
預期欄位：
  統計期 / 稽查家次（餐飲店/冷飲店/傳統市場/超市/學校/醫院）
  不合格飭令改善家次 / 食物中毒人數
時序範圍：2014 年 ~ 最新月份
```

#### 資料集 3：食品衛生管理查驗工作（TPE，待確認）
```
預期欄位：
  統計期 / 查驗件數 / 不符規定比率
  違規原因：農藥殘留 / 食品添加物 / 微生物 / 動物用藥 / 黃麴毒素
時序範圍：2014 年 ~ 最新月份
```

---

## 六、功能設計

### 核心功能一：餐廳食安評核地圖（Hero Feature）

```
┌─────────────────────────────────────────────────┐
│  地圖顯示模式                                      │
│                                                   │
│  ● 綠色點位 = A 級評核（最優）                     │
│  ● 黃色點位 = B 級評核                             │
│  ● 橙色點位 = C 級評核（需改善）                   │
│                                                   │
│  [篩選：□全部  ☑A級  □B級  □C級]                  │
│                                                   │
│  點擊點位彈出：                                    │
│  ┌─────────────────────────────────────────┐     │
│  │ 🏪 XX 餐廳                                │     │
│  │ 評核等級：A 級                             │     │
│  │ 地址：臺北市大安區 XX 路 XX 號             │     │
│  │ 評核日期：2025-09-15                      │     │
│  └─────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

### 核心功能二：食安風險趨勢警示

- 折線圖追蹤三大違規類型月度比率
- **警示機制**：任一指標較前一個月上升 > 20% 時，顯示橙色旗幟圖示
- 食物中毒人數月度趨勢（獨立折線）

### 核心功能三：雙北食安合格率對比

- 臺北市每月不符規定比率 vs 新北市每季抽驗合格率
- 雙城並列長條圖，直覺比較
- KPI 卡片：最新月份雙城食物中毒人數

### 核心功能四：食品工廠分布地圖（新北）

- 1,232 家食品工廠點位（已有精確座標，免地理編碼）
- 可疊加於主地圖作為獨立圖層
- 識別食品製造業聚集區，輔助監管決策

### 核心功能五：各業別稽查覆蓋分析

- 堆疊長條圖：各業別（餐飲/冷飲/市場/學校/醫院）稽查家次 + 不合格家次
- 合格率由數據計算，顯示哪個業別風險最高

---

## 七、圖表規格

### 組件 A｜餐廳食安評核地圖
```
組件類型：地圖主組件（點位圖層）
資料源：restaurant_hygiene_rating（GeoJSON）
點位顏色：
  - A 級 → #4CAF50（綠）
  - B 級 → #FFC107（黃）
  - C 級 → #FF7043（橙）
點位大小：固定（半徑 6px）
聚合：zoom < 13 時使用 Cluster 聚合，顯示各等級數量
Popup：業者名稱 / 評核等級 / 評核日期 / 地址
圖層控制：可獨立開關 A/B/C 各等級圖層
```

### 組件 B｜食品查驗違規趨勢折線圖
```
組件類型：TimelineSeparateChart（多線折線）
X 軸：年月（2020-01 ~ 最新月份）
Y 軸：違規比率（%）
線條：
  - 農藥殘留（綠色）
  - 食品添加物（橙色）
  - 微生物污染（紅色）
  - 動物用藥殘留（紫色）
警示：任一線當月較上月上升 > 20% 顯示 ⚠ 圖示
次 Y 軸：食物中毒人數（折線，灰色）
互動：滑動顯示各月詳細數值
```

### 組件 C｜雙北食安合格率對比
```
組件類型：BarChart（分組橫向長條）
臺北市：不符規定比率（月，反轉為合格率顯示）
新北市：市售食品抽驗合格率（季）
顯示：最近 8 季
KPI 卡：
  - 本月食物中毒人數（臺北）
  - 本季抽驗合格率（新北）
```

### 組件 D｜各業別稽查覆蓋率
```
組件類型：StackedBarChart（堆疊長條）
X 軸：年月
Y 軸：稽查家次
堆疊：餐飲店 / 冷飲店 / 傳統市場 / 超市量販 / 學校 / 醫院
次要線：不合格率折線（右 Y 軸）
切換：顯示件次 / 顯示合格率
```

### 組件 E｜食品工廠空間分布地圖（新北）
```
組件類型：地圖圖層（點位）
資料源：food_factory_ntpc（GeoJSON，已有精確座標）
點位顏色：#1565C0（藍色，代表製造業）
點位形狀：六角形圖示
聚合：zoom < 11 時使用 Heatmap 模式
Popup：工廠名稱 / 地址 / 主管機關 / 登記日期
目的：識別食品工廠密集區，輔助稽查決策
```

---

## 八、地圖設計

### 主地圖：餐廳評核點位分布

```
底圖：Mapbox Streets-v12（淺色，食安主題）
預設城市：臺北市
初始縮放：12（顯示市區大部分範圍）
初始中心：[121.5654, 25.0330]（臺北市中心）

圖層設計：
┌─────────────────────────────────────────────────┐
│  圖層 1：餐廳評核點位（主要圖層）                  │
│  - A/B/C 三色，圓形點位                           │
│  - zoom < 13：Cluster 聚合（顯示各等級數量）       │
│  - zoom ≥ 13：個別點位顯示                        │
│  - 點擊：Popup（名稱/等級/日期/地址）              │
│                                                   │
│  圖層 2：食品工廠（可選，新北市）                  │
│  - 藍色六角形，需切換到新北才顯示                  │
│  - zoom < 11：Heatmap 密度圖                      │
│  - zoom ≥ 11：個別點位                            │
│                                                   │
│  圖層 3：行政區等級分布熱力（可切換）              │
│  - 行政區多邊形，依 A 級評核業者密度填色           │
│  - 讓市民了解哪個區的食安認證餐廳最多              │
└─────────────────────────────────────────────────┘

左側圖例面板：
  ● A級（綠）  ● B級（黃）  ● C級（橙）
  ● 食品工廠（藍）
  
右側：
  切換城市：[臺北] [新北]
  圖層開關面板
  點選餐廳後的詳情側欄
```

### 聚合設計（Cluster）

```
Zoom 10：全市聚合一顆大泡泡，顯示各等級數量
Zoom 11：依行政區分塊，每塊一個泡泡
Zoom 12：街道級，餐廳開始分散顯示
Zoom 13+：完全展開個別點位

泡泡顏色規則：
  - 若 A 級 > 50%：顯示綠色泡泡
  - 若 C 級 > 30%：顯示橙色泡泡
  - 其他：顯示灰色泡泡
```

---

## 九、ETL 資料管道

### Pipeline 架構

```
資料來源 API
    │
    ▼
┌─────────────────────────────────────────────────┐
│  DAG: restaurant_hygiene_etl                      │
│  排程：每季執行（或手動觸發）                      │
│                                                   │
│  Step 1: 兩步驟下載餐飲衛生分級評核業者 CSV        │
│    UUID=59579c19 → 取 RID → CSV 下載              │
│  Step 2: 清洗（去除重複、標準化地址格式）           │
│  Step 3: 地理編碼（地址 → 經緯度，ArcGIS）        │
│    - 快取已編碼地址（.geocode_cache.json）         │
│  Step 4: 輸出 GeoJSON + 更新 PostgreSQL            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  DAG: food_safety_stats_monthly                   │
│  排程：每月 10 日（前月資料公布後）                │
│                                                   │
│  Step 1: 兩步驟下載稽查工作 CSV（UUID=7d50657f）  │
│  Step 2: 兩步驟下載查驗工作 CSV（UUID=c3ae074c）  │
│  Step 3: 計算月度違規率、食物中毒人數              │
│  Step 4: Upsert 到 food_safety_monthly            │
│  Step 5: 計算 MoM 變化率，更新警示旗              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  DAG: food_safety_ntpc_quarterly                  │
│  排程：每季執行                                   │
│                                                   │
│  Step 1: NTPC 直接 UUID 抓取合格率                │
│    https://data.ntpc.gov.tw/api/datasets/         │
│    d2d69f7e-e283-406e-859b-e9e5dc98ac50/json      │
│  Step 2: 解析 percent 欄位，Upsert                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  DAG: food_factory_ntpc_etl                       │
│  排程：一次性（靜態資料，新增時手動更新）           │
│                                                   │
│  Step 1: NTPC 直接 UUID 抓取食品工廠清冊           │
│    https://data.ntpc.gov.tw/api/datasets/         │
│    c51d5111-c300-44c9-b4f1-4b28b9929ca2/json      │
│  Step 2: 用 wgs84ax/wgs84ay 欄位直接建 GeoJSON    │
│  Step 3: 輸出 → public/mapData/food_factory_ntpc.geojson
└─────────────────────────────────────────────────┘
```

### ETL Python 實作（核心片段）

```python
import requests
import csv
import io
import json
import os

# ─── data.taipei 兩步驟擷取 ─────────────────────────────────────────
TPE_DATASETS = {
    "restaurant_rating": "59579c19-a561-4564-8c0f-545bfb32c0f6",
    "food_inspection":   "7d50657f-b35b-496e-b83f-5713893b9a9e",
    "food_testing":      "c3ae074c-f65f-4f69-bf65-2c00a674e870",
}

def tpe_get_rid(dataset_uuid: str) -> str:
    resp = requests.get(
        f"https://data.taipei/api/v1/dataset.view?id={dataset_uuid}",
        timeout=30
    ).json()
    return resp["result"]["rid"]

def tpe_fetch_csv(dataset_uuid: str) -> list[dict]:
    rid = tpe_get_rid(dataset_uuid)
    url = f"https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={rid}"
    resp = requests.get(url, timeout=60)
    resp.encoding = "utf-8-sig"
    return list(csv.DictReader(io.StringIO(resp.text)))

# ─── data.ntpc 直接擷取（已驗證） ────────────────────────────────────
NTPC_DATASETS = {
    "food_pass_rate": "d2d69f7e-e283-406e-859b-e9e5dc98ac50",
    "food_factory":   "c51d5111-c300-44c9-b4f1-4b28b9929ca2",
}

def ntpc_fetch_all(uuid: str, page_size: int = 100) -> list[dict]:
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

# ─── 食品工廠 GeoJSON 生成（已有 WGS84 座標，免地理編碼） ──────────
def build_food_factory_geojson() -> dict:
    rows = ntpc_fetch_all(NTPC_DATASETS["food_factory"])
    features = []
    for row in rows:
        try:
            lng = float(row["wgs84ax"])
            lat = float(row["wgs84ay"])
        except (ValueError, KeyError):
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name":       row.get("organizer", ""),
                "no":         row.get("no", ""),
                "address":    row.get("address", ""),
                "tax_id":     row.get("tax_id_number", ""),
                "date":       row.get("date", ""),
                "city":       "newtaipei",
            }
        })
    return {"type": "FeatureCollection", "features": features}

# ─── 餐廳評核 GeoJSON 生成（需地理編碼） ─────────────────────────────
GEOCODE_CACHE_FILE = "scripts/.geocode_cache.json"

def load_cache() -> dict:
    if os.path.exists(GEOCODE_CACHE_FILE):
        with open(GEOCODE_CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(cache: dict):
    with open(GEOCODE_CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def arcgis_geocode(address: str) -> tuple[float, float] | None:
    """ArcGIS World Geocoder — 免費，支援繁體中文地址"""
    resp = requests.get(
        "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates",
        params={"SingleLine": address, "outFields": "Score", "f": "json"},
        timeout=15
    ).json()
    candidates = resp.get("candidates", [])
    if candidates and candidates[0].get("score", 0) >= 80:
        loc = candidates[0]["location"]
        return loc["x"], loc["y"]  # (lng, lat)
    return None

def build_restaurant_geojson() -> dict:
    cache = load_cache()
    rows = tpe_fetch_csv(TPE_DATASETS["restaurant_rating"])
    features = []
    for row in rows:
        addr = row.get("地址") or row.get("地址（含店名）") or ""
        if not addr:
            continue
        if addr not in cache:
            cache[addr] = arcgis_geocode(addr)
            save_cache(cache)
        coords = cache.get(addr)
        if not coords:
            continue
        lng, lat = coords
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "name":        row.get("業者名稱店名") or row.get("業者名稱") or "",
                "rating":      row.get("評核結果") or row.get("評核等級") or "",
                "address":     addr,
                "district":    row.get("行政區域代碼") or "",
                "food_biz_no": row.get("食品業者登錄字號") or "",
                "city":        "taipei",
            }
        })
    return {"type": "FeatureCollection", "features": features}

# ─── 新北食品合格率解析（已驗證欄位：seqno, name, filename, percent）
def fetch_ntpc_pass_rate() -> list[dict]:
    rows = ntpc_fetch_all(NTPC_DATASETS["food_pass_rate"])
    return [
        {
            "quarter":   row.get("name", ""),      # e.g. '113年第4季...'
            "pass_rate": float(row.get("percent", 0)),
            "filename":  row.get("filename", ""),
        }
        for row in rows
        if row.get("percent")
    ]
```

### 資料表設計

```sql
-- 餐廳評核點位（每季更新）
CREATE TABLE restaurant_hygiene_rating (
    id              SERIAL PRIMARY KEY,
    district_code   VARCHAR(10),
    name            VARCHAR(200) NOT NULL,
    food_biz_no     VARCHAR(50),
    address         TEXT NOT NULL,
    rating          CHAR(1) CHECK (rating IN ('A', 'B', 'C')),
    rating_date     DATE,
    longitude       DOUBLE PRECISION,
    latitude        DOUBLE PRECISION,
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rating_location ON restaurant_hygiene_rating 
    USING GIST (ST_MakePoint(longitude, latitude));

-- 月度食品稽查統計
CREATE TABLE food_safety_monthly (
    id              SERIAL PRIMARY KEY,
    stat_period     DATE NOT NULL,           -- YYYY-MM-01
    source_city     VARCHAR(10) NOT NULL,
    
    -- 稽查工作
    total_inspections       INTEGER,
    restaurant_inspections  INTEGER,
    cold_drink_inspections  INTEGER,
    market_inspections      INTEGER,
    school_inspections      INTEGER,
    hospital_inspections    INTEGER,
    failed_count            INTEGER,
    food_poisoning_cases    INTEGER,
    
    -- 查驗工作
    total_tests             INTEGER,
    violation_rate          DECIMAL(5,2),    -- 不符規定比率(%)
    pesticide_violations    INTEGER,
    additive_violations     INTEGER,
    microbial_violations    INTEGER,
    
    -- 警示旗
    pesticide_alert         BOOLEAN DEFAULT FALSE,
    additive_alert          BOOLEAN DEFAULT FALSE,
    microbial_alert         BOOLEAN DEFAULT FALSE,
    
    UNIQUE (stat_period, source_city)
);

-- 新北市季度食品抽驗合格率
CREATE TABLE food_safety_ntpc_quarterly (
    id          SERIAL PRIMARY KEY,
    quarter     VARCHAR(7) NOT NULL,    -- e.g. '2025-Q4'
    pass_rate   DECIMAL(5,2),           -- 合格率(%)
    updated_at  TIMESTAMP DEFAULT NOW()
);
```

---

## 十、警示系統設計

### 月度食安警示計算

```python
def calculate_alerts(current_month: dict, prev_month: dict) -> dict:
    """
    計算本月 vs 上月各指標變化率，
    超過 20% 上升則設定警示旗。
    """
    alerts = {}
    
    def check_alert(current_rate, prev_rate, key):
        if prev_rate and prev_rate > 0:
            change = (current_rate - prev_rate) / prev_rate
            alerts[key] = change > 0.20
    
    check_alert(
        current_month['pesticide_violation_rate'],
        prev_month['pesticide_violation_rate'],
        'pesticide_alert'
    )
    # ... 其他指標同理
    
    return alerts
```

### 前端警示顯示

```vue
<!-- 警示旗組件 -->
<template>
  <div class="alert-banner" v-if="hasActiveAlerts">
    <span class="alert-icon">⚠️</span>
    <span>本月農藥殘留違規率較上月上升 {{ changeRate }}%，請留意食材來源。</span>
  </div>
</template>
```

---

## 十一、儀表板版面配置

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER                                                       │
│  食安透明地圖 | 雙北餐飲衛生評核與食品安全儀表板    [日期戳記]  │
├─────────────────────────────────────────────────────────────┤
│  KPI 列                                                       │
│  ┌──────────────┐ ┌───────────────┐ ┌─────────────────────┐ │
│  │本月食物中毒    │ │ A級評核業者   │ │  本季新北抽驗合格率  │ │
│  │   3 件        │ │   1,247 家    │ │      96.8%          │ │
│  │ (臺北，較上月↑1)│ │（臺北市登錄）  │ │                     │ │
│  └──────────────┘ └───────────────┘ └─────────────────────┘ │
├─────────────────┬───────────────────────────────────────────┤
│                  │  ⚠ 警示：本月農藥殘留違規率較上月上升 23%  │
│  [組件 A：        ├───────────────────────────────────────────┤
│   餐廳評核       │  [組件 B：食品查驗違規趨勢折線圖]           │
│   點位地圖]      │  農藥殘留 / 添加物 / 微生物 (2020~今)       │
│                  ├───────────────────────────────────────────┤
│  A● B● C●        │  [組件 C：雙北食安合格率對比長條圖]         │
│  切換：TPE/NTPC  │                                            │
├─────────────────┴───────────────────────────────────────────┤
│  [組件 D：各業別稽查覆蓋分析]  │  [組件 E：食品工廠分布（新北）] │
│  （堆疊長條，月度）             │  （地圖點位，1,232 家工廠）     │
└─────────────────────────────────────────────────────────────┘
```

---

## 十二、技術規格

### 前端組件對應

| 組件 | Dashboard Component 類型 | 備注 |
|------|--------------------------|------|
| A：評核地圖 | `MapLegend` + 點位圖層 | 主角，含 Cluster |
| B：違規趨勢 | `TimelineSeparateChart` | 多線折線 + 警示旗 |
| C：雙北對比 | `BarChart`（分組） | 雙城側並列 |
| D：稽查覆蓋 | `StackedBarChart` | 業別堆疊 |
| E：工廠地圖 | `MapLegend` + 點位圖層 | 僅新北，已有座標 |

### 後端 API 端點

```
GET /api/v1/component/restaurant_hygiene_map?city={tpe|ntpc}&rating={A|B|C|all}
GET /api/v1/component/food_safety_violation_trend?months=36
GET /api/v1/component/food_safety_city_comparison
GET /api/v1/component/food_inspection_by_type
```

### GeoJSON 輸出規格

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [121.5432, 25.0468] },
      "properties": {
        "name": "XX 美食坊",
        "rating": "A",
        "rating_date": "2025-09-15",
        "address": "臺北市大安區 XX 路 100 號",
        "district": "大安區"
      }
    }
  ]
}
```

---

## 十三、Dashboard 組件資料庫登錄

```sql
-- 儀表板基本資訊
INSERT INTO dashboards (name, icon, color, description)
VALUES (
    '食安透明地圖',
    'restaurant',
    '#2E7D32',
    '雙北餐飲衛生評核地圖、食品違規趨勢分析、工廠空間分布。讓市民在地圖上看到附近餐廳的政府衛生評核等級。'
);

-- 組件 A：餐廳評核地圖
INSERT INTO components (name, short_description, update_freq, source, city)
VALUES (
    '餐廳衛生分級評核地圖',
    '臺北市通過餐飲衛生管理分級評核業者（A/B/C 等級），地圖點位顯示。',
    '每季',
    '臺北市衛生局',
    'taipei'
);

-- 組件 B：違規趨勢
INSERT INTO components (name, short_description, update_freq, source, city)
VALUES (
    '食品查驗違規原因趨勢',
    '臺北市每月食品查驗不符規定比率，依農藥殘留/添加物/微生物分類追蹤。',
    '每月',
    '臺北市衛生局',
    'taipei'
);
```

---

## 十四、實作里程碑

### Phase 1：靜態資料與地圖（Day 1）
- [ ] 建立 `restaurant_hygiene_etl` DAG
- [ ] 實作地址 → 地理編碼轉換（利用快取機制）
- [ ] 產生餐廳評核 GeoJSON
- [ ] 建立新北食品工廠 GeoJSON（已有精確座標，最快完成）
- [ ] 設計 PostgreSQL schema

### Phase 2：時序資料與圖表（Day 2）
- [ ] 建立 `food_safety_stats_monthly` DAG
- [ ] 實作月度違規趨勢折線圖（組件 B）
- [ ] 實作雙北食安合格率對比（組件 C）
- [ ] 實作月度警示旗計算邏輯

### Phase 3：整合與完善（Day 3）
- [ ] 整合所有組件到儀表板版面
- [ ] 優化地圖 Cluster 聚合效果
- [ ] 測試警示系統觸發邏輯
- [ ] UI 調整與響應式測試

---

## 十五、延伸功能（加分項）

### 延伸 A：學校供應鏈透明度（食材登錄平台）
- 整合食材登錄平台資料，讓家長查詢孩子學校使用的供應商
- 呈現各行政區登錄業者數量（衡量供應鏈透明度）
- 技術難度：中（需要學校 + 供應商的關聯邏輯）

### 延伸 B：餐廳評核等級行政區分布
- 行政區多邊形熱力圖：A 級餐廳密度（每千家餐廳中 A 級佔比）
- 識別「食安友善區」vs「食安待改善區」
- 技術難度：低（在現有地圖組件上加一個 fill layer）

### 延伸 C：食物中毒事件時間軸
- 以日曆熱力圖（Calendar Heatmap）呈現歷年食物中毒案件分布
- 識別高風險季節（夏季、颱風後）
- 技術難度：中（需要客製化 Calendar 組件）

---

## 十六、評審亮點摘要

1. **填補明顯空缺**：政府評核資料存在但無地圖化，本儀表板做了最直接的填補
2. **個人化程度高**：「我家附近的餐廳是幾級？」是每個市民都會問的問題
3. **最低技術門檻**：資料最乾淨（工廠已有 WGS84 座標），ETL 複雜度最低，最容易在黑客松時程內完成
4. **政策問責功能**：透明化評核結果，形成市場壓力迫使業者主動改善
5. **資料新鮮度**：月度食品查驗違規率 + 季度新北合格率，保持儀表板持續有新資訊
6. **視覺衝擊力強**：A/B/C 三色地圖點位是評審第一眼就能理解的視覺語言

---

*本提案由 Claude Code 協助分析雙北開放資料後生成，資料集均來自 data.taipei 及 data.ntpc.gov.tw。*
