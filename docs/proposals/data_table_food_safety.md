# 食安資料字典 — Food Safety Data Dictionary

> **給提案團隊**：以下 7 張資料表構成 dashboard 503「食安風險追蹤器」的後端資料（已部署於 main）。
> 每張表的時間 / 空間覆蓋、欄位語意、可衍生指標都列出來，方便提新元件時快速判斷是否能直接重用。
>
> - 全部位於 `dashboard` PostgreSQL DB（host:5433）
> - 一鍵 populate：`./scripts/food_safety/apply.sh`
> - 鏡像 schema 規格定義：`scripts/food_safety/migrations/001_create_tables.up.sql`
> - 完整實作背景：`docs/plans/2026-05-02-food-safety-radar-design.md`

## 概覽（一表盤點）

| Table | 範圍 | Rows | 時間 | 空間 | 主要用途 |
|---|---|---:|---|---|---|
| `food_inspection_tpe` | TPE 食品衛生稽查工作年度統計 | 20 | 2006-2025 | TPE only | 場所別稽查家次、不合格家次、食物中毒人數 |
| `food_testing_tpe` | TPE 食品衛生查驗工作年度統計 | 20 | 2006-2025 | TPE only | 違規原因別件數、不符規定比率 |
| `food_restaurant_tpe` | TPE 通過餐飲衛生分級評核業者 | 1,686 | 114 年 (2025) snapshot | TPE 12 行政區（含經緯度） | 地圖點位、行政區分布 |
| `food_factory_ntpc` | NTPC 食品工廠清冊 | 1,230 | 不定期 | NTPC 29 區（WGS84 精確座標） | 地圖點位、製造業聚集分析 |
| `food_inspection_by_city` | MOHW 食品衛生管理工作 - 按縣市別分 | 35 | 2007-2025 | 雙北 city-level（限合計） | 雙北稽查不合格率年度比較 |
| `food_type_violations` | MOHW 食品違規依類別分 | 383 | 2007-2025 | 雙北 city-level | 雙北食品類別違規結構（12 類） |
| `food_poisoning_cause` | MOHW 食物中毒病因物質分類 | 226 | 2007-2024 | 全國 | 病原體（細菌 / 病毒 / 化學 / 天然毒）年度趨勢 |

**重點原則：**
- 凡 TPE 自家資料（`food_*_tpe`）有 20 年完整序列，但只涵蓋臺北。
- MOHW 衛福部資料（`food_inspection_by_city`、`food_type_violations`、`food_poisoning_cause`）才有雙北或全國視角，但每年資料晚 1-2 季公開。
- 地圖點位（`food_restaurant_tpe`、`food_factory_ntpc`）已預先 geocode + GeoJSON 化在 `Taipei-City-Dashboard-FE/public/mapData/`。

---

## 1. `food_inspection_tpe` — 臺北市食品衛生稽查工作年度統計

> 涵蓋全市對「實體場所」的稽查家次、不合格家次與食物中毒人數。
> Source: `docs/assets/臺北市食品衛生管理稽查工作-年度統計.csv`（data.taipei 公開資料）

| 欄位 | 型別 | 意義 | 範例（2025） |
|---|---|---|---:|
| `year` | INTEGER PK | 年份（西元，原資料 ROC 年自動轉換） | 2025 |
| `total_inspections` | INTEGER | 全市稽查總家次 | 23,411 |
| `restaurant_insp` | INTEGER | 餐飲店稽查家次 | 9,807 |
| `drink_shop_insp` | INTEGER | 冷飲店稽查家次 | — |
| `street_vendor_insp` | INTEGER | 飲食攤販稽查家次 | — |
| `market_insp` | INTEGER | 傳統市場稽查家次 | — |
| `supermarket_insp` | INTEGER | 超級市場稽查家次 | — |
| `manufacturer_insp` | INTEGER | 製造廠商稽查家次 | 774 |
| `total_noncompliance` | INTEGER | 全市不合格飭令改善家次 | 7,275 |
| `restaurant_nc` | INTEGER | 餐飲店不合格家次 | — |
| `drink_shop_nc` | INTEGER | 冷飲店不合格家次 | — |
| `street_vendor_nc` | INTEGER | 飲食攤販不合格家次 | — |
| `market_nc` | INTEGER | 傳統市場不合格家次 | — |
| `supermarket_nc` | INTEGER | 超級市場不合格家次 | — |
| `manufacturer_nc` | INTEGER | 製造廠商不合格家次 | — |
| `food_poisoning_cases` | INTEGER | 食物中毒案件人數（人）| 909 |

**衍生指標：**
- 各場所不合格率 = `<venue>_nc / <venue>_insp`
- 食物中毒人數年度趨勢（最強警訊：2025 = 909 人，較 2023 的 169 人增 5.4 倍）
- 場所稽查覆蓋率變化

**已知關注時序事件：**
- 2024-2025 食物中毒激增（從 169 到 909）— 適合做警示燈號 / 趨勢預警

---

## 2. `food_testing_tpe` — 臺北市食品衛生查驗工作年度統計

> 「查驗」≠「稽查」。查驗是抽樣送實驗室檢測（化驗）；稽查是現場查訪。
> Source: `docs/assets/臺北市食品衛生管理查驗工作-年度統計.csv`

| 欄位 | 型別 | 意義 | 範例（2025） |
|---|---|---|---:|
| `year` | INTEGER PK | 年份 | 2025 |
| `total_tested` | INTEGER | 查驗總件數 | 49,511 |
| `total_violations` | INTEGER | 與規定不符總件數 | 350 |
| `violation_rate` | NUMERIC(5,2) | 不符規定比率（%）| 0.71 |
| `viol_labeling` | INTEGER | 違規標示件數 | — |
| `viol_ad` | INTEGER | 違規廣告件數 | — |
| `viol_additive` | INTEGER | 食品添加物違規件數 | 23 |
| `viol_container` | INTEGER | 食品器皿容器包裝違規件數 | — |
| `viol_microbe` | INTEGER | 微生物超標件數 | 156 |
| `viol_mycotoxin` | INTEGER | 真菌毒素件數 | — |
| `viol_vetdrug` | INTEGER | 動物用藥殘留件數 | — |
| `viol_chemical` | INTEGER | 化學成分違規件數 | — |
| `viol_composition` | INTEGER | 成分分析違規件數 | — |
| `viol_other` | INTEGER | 其他違規件數 | — |

**衍生指標：**
- 違規原因類別佔比（DonutChart 已實作 = 1014）
- 不符規定比率年度趨勢（2018 = 1.38% 高峰，2025 = 0.71%）
- 微生物 / 添加物 / 化學成分等子類年度比較

---

## 3. `food_restaurant_tpe` — 臺北市通過餐飲衛生管理分級評核業者

> 通過 TPE 衛生局評核的餐飲業者，地址已 geocode 到經緯度。
> Source: `docs/assets/114年臺北市通過餐飲衛生管理分級評核業者 (1141218).csv` + 9,680-entry geocode cache。

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `name` | VARCHAR(200) | 業者名稱店名 | "五花馬-松山機場" |
| `address` | VARCHAR(300) | 完整地址（含樓層） | "臺北市松山區敦化北路 340-9 號" |
| `district` | VARCHAR(50) | 行政區（依地址欄位代碼自動對映 12 區）| "松山區" |
| `grade` | VARCHAR(10) | 評核等級：`優` 或 `良` | "優" |
| `lng` | DOUBLE PRECISION | 經度（cache hit 為實際值；miss 為行政區 centroid + 抖動）| 121.5503 |
| `lat` | DOUBLE PRECISION | 緯度 | 25.0599 |

**業者統計：**
- 評核「優」: 1,609 家（占 95%）
- 評核「良」: 77 家（占 5%）
- 涵蓋 12 個行政區

**衍生指標：**
- 行政區評核業者密度（每千家餐廳中的優級比例）
- 個別業者地圖點位查詢（FE 已用 GeoJSON 渲染）
- 與 Google Maps / 愛食記等用戶評分的相關性分析

**注意：** 約 6% 地址 cache miss，使用行政區質心 + jitter 作 fallback；這些點位置略有偏差但不影響行政區聚合分析。

---

## 4. `food_factory_ntpc` — 新北市食品工廠清冊

> NTPC 列管的合法食品工廠，含 WGS84 精確座標（**不需 geocode**）。
> Source: NTPC API `c51d5111-c300-44c9-b4f1-4b28b9929ca2` 一次性快照於 `scripts/food_safety/snapshots/ntpc_food_factory.csv`。

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `name` | VARCHAR(200) | 主管機關 / 業者名稱（原欄位 `organizer`）| "鴻輝食品廠" |
| `address` | VARCHAR(300) | 工廠地址 | "新北市新莊區..." |
| `tax_id` | VARCHAR(50) | 統一編號（原 `tax_id_number`）| — |
| `lng` | DOUBLE PRECISION | 經度（原 `wgs84ax`，已驗證範圍 120-122.5）| 121.4486 |
| `lat` | DOUBLE PRECISION | 緯度（原 `wgs84ay`，已驗證範圍 24-26）| 25.0327 |
| `district` | VARCHAR(50) | 行政區（從 address 自動 regex 抽出）| "新莊區" |

**工廠分布 Top 5：**
中和區 170 / 新莊區 149 / 樹林區 127 / 三重區 126 / 汐止區 109

**衍生指標：**
- 食品工廠空間聚集度（heatmap）
- 工廠類別分布（需擴充 organizer 解析或加入新欄位）
- 與餐廳供應鏈關係（需另接資料）

**重新抓取資料：**
```bash
python3 scripts/food_safety/etl/snapshot_apis.py
```

---

## 5. `food_inspection_by_city` — 衛福部食品衛生管理工作（按縣市別分）

> 衛福部統計處每年公開的雙北 city-level 稽查彙總。
> Source: `docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx`（多年 sheet）。

| 欄位 | 型別 | 意義 | 範例（2025） |
|---|---|---|---:|
| `id` | SERIAL PK | 自動編號 | — |
| `year` | INTEGER NOT NULL | 年份（西元） | 2025 |
| `city` | VARCHAR(20) NOT NULL | 城市：`臺北市` 或 `新北市` | "臺北市" |
| `venue` | VARCHAR(40) NOT NULL | 場所別 — **目前一律為 `合計`**（衛福部 xlsx 未提供 by-venue 細分）| "合計" |
| `inspections` | INTEGER | 該城市該年度稽查家次（合計）| 71,932 |
| `noncompliance` | INTEGER | 不合格家次（合計）| 468 |
| `poisoning_cases` | INTEGER | 食物中毒人數（**目前一律為 NULL**，xlsx 未提供）| `NULL` |
| `ntpc_violation_rate` | NUMERIC(5,2) | 不符規定比率（%，由 `noncompliance / inspections` 計算）| 0.65 |
| UNIQUE | (year, city, venue) | 自然鍵 | — |

**雙北年度比較（2025）：**
| city | inspections | noncompliance | rate |
|---|---:|---:|---:|
| 臺北市 | 71,932 | 468 | 0.65% |
| 新北市 | 89,088 | 100 | 0.11% |

**衍生指標：**
- 雙北 NC 件數 stacked column（dashboard 已實作 = 1012 / 1015 metrotaipei）
- 雙北稽查強度比較（inspections per capita / 商家）
- 公開時間差分析（衛福部 vs TPE 自家統計差異）

**⚠️ 已知資料缺口：**
- 無 by-venue（餐飲店 / 冷飲店 / ...）細分 → 無法做雙北 venue 比較
- 無 by-city poisoning_cases → 食物中毒人數 by city 須仰賴各市自家資料
- TPE 數字與 `food_inspection_tpe` 略有差異（統計範圍口徑不同；衛福部 xlsx 是「報部」資料）

---

## 6. `food_type_violations` — 衛福部食品違規依類別分

> 從同一份衛福部 xlsx 抽出的「食品類別 × 城市 × 年份」違規件數。
> Source: `docs/assets/10521-01-03食品衛生管理工作－按縣市別分1150331.xlsx`（多年 sheet）。
> Loader: `load_mohw_dual_city.py` (12 食品類別映射為 column-index 範圍)

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `year` | INTEGER NOT NULL | 年份 | 2024 |
| `city` | VARCHAR(20) NOT NULL | 城市 | "臺北市" |
| `category` | VARCHAR(40) NOT NULL | 食品類別（共 12 類）| "蔬果類" |
| `count` | INTEGER NOT NULL | 該類別違規件數 | 202 |
| UNIQUE | (year, city, category) | 自然鍵 | — |

**12 食品類別清單：**
乳品類 / 肉品類 / 蛋品類 / 水產類 / 穀豆烘焙 / 蔬果類 / 飲料及水 / 食用油脂 / 調味品 / 健康食品 / 複合調理 / 其他

**Top 5 違規類別（臺北 2024-2025）：**
| category | count |
|---|---:|
| 蔬果類 | 202 (2024) / 157 (2025) |
| 飲料及水 | 103 (2025) |
| 其他 | 81 (2024) |
| 穀豆烘焙 | 75 (2024) / 72 (2025) |

**衍生指標：**
- 雙北違規結構比較 donut（dashboard 1014 已實作合併版）
- 高風險食品類別年度走勢（折線）
- 季節性違規（需要月度資料 — 目前僅年度）

---

## 7. `food_poisoning_cause` — 衛福部食物中毒案件病因物質分類

> 全國（**非 by-city**）食物中毒案件按病因物質分類年度統計。
> Source: `docs/assets/10521-05-01食品中毒案件病因物質分類統計.xlsx`。

| 欄位 | 型別 | 意義 | 範例（2024）|
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `year` | INTEGER NOT NULL | 年份 | 2024 |
| `cause` | VARCHAR(60) NOT NULL | 病因物質（含主類-子類前綴避免重複，如 `細菌-其他` / `天然毒-其他`）| "諾羅病毒" |
| `cases` | INTEGER | 案件數 | 562 |
| `persons` | INTEGER | 患者人數 | 3,634 |
| UNIQUE | (year, cause) | 自然鍵 | — |

**Top 病因（2024）：**
| cause | cases | persons |
|---|---:|---:|
| 未檢出 | 951 | 4,938 |
| 無檢體 | 792 | 3,570 |
| 諾羅病毒 | 562 | 3,634 |
| 金黃色葡萄球菌 | 90 | 827 |
| 仙人掌桿菌 | 87 | 929 |
| 腸炎弧菌 | 55 | 388 |

**衍生指標：**
- 細菌性 vs 病毒性 vs 化學性 病因占比變化
- 諾羅病毒季節性流行模式（需擴充月度資料）
- 「未檢出 / 無檢體」比例反映檢測技術進展

**注意：** 此表 dashboard 503 目前**未直接 wired**（spec §4 列為 fallback 用途），但提案者可直接讀取此表做新元件。

---

## 提案參考速查（需求 → 資料源）

| 需求類型 | 推薦表 | 備註 |
|---|---|---|
| 時序趨勢圖（≥10 年）| `food_inspection_tpe` / `food_testing_tpe` | TPE only；20 年覆蓋最厚 |
| 雙北年度比較 | `food_inspection_by_city` | 限 city-level 合計，無 venue |
| 雙北食品類別分析 | `food_type_violations` | 12 類 × 雙北 × 19 年 |
| 食物中毒病原追蹤 | `food_poisoning_cause` | 全國，無 by-city |
| 餐廳地圖點位 | `food_restaurant_tpe` | 含 grade（優/良）與經緯度 |
| 工廠地圖點位 | `food_factory_ntpc` | 含 WGS84 精確座標、行政區 |
| 行政區聚合分析 | `food_restaurant_tpe.district` / `food_factory_ntpc.district` | 兩表都有 district 欄 |
| 場所別風險（限 TPE）| `food_inspection_tpe.<venue>_nc / <venue>_insp` | 6 種場所 |
| 違規原因（限 TPE）| `food_testing_tpe.viol_*` | 9 種違規原因 |

## 資料更新流程

| 資料源 | 更新頻率 | 流程 |
|---|---|---|
| TPE CSV (3 個) | 不定期（年度）| data.taipei 手動下載新版本 → 覆蓋 `docs/assets/` → 重跑 `apply.sh` |
| NTPC factory | 不定期 | `python3 scripts/food_safety/etl/snapshot_apis.py` → commit snapshot CSV → 重跑 `apply.sh` |
| MOHW xlsx (3 個) | 衛福部統計處每季 | 從 https://dep.mohw.gov.tw 下載新版 → 覆蓋 `docs/assets/` → 重跑 `apply.sh` |

## 對應 dashboard 503 components

| Component | Index | Type | 主要表 | 雙北版本 |
|---|---|---|---|---|
| 1011 食物中毒趨勢 | `food_poisoning_trend` | ColumnLineChart | `food_inspection_tpe` | + `food_inspection_by_city`（NTPC NC 線）|
| 1012 場所不合格件數 | `food_venue_risk` | ColumnChart | `food_inspection_tpe`（taipei venue 累計）| `food_inspection_by_city` (year × city stacked) |
| 1013 食安認證地圖 | `food_safety_map` | MapLegend + GeoJSON | `food_restaurant_tpe` + `food_factory_ntpc` | 雙城雙圖層 |
| 1014 違規原因分析 | `food_violation_types` | DonutChart | `food_testing_tpe`（taipei 7 類）| `food_type_violations`（雙北合計 12 類） |
| 1015 年度檢驗違規件數 | `food_testing_rate` | ColumnChart | `food_testing_tpe`（taipei 年度）| `food_testing_tpe` + `food_inspection_by_city`（雙城 stacked）|

---

*Generated: 2026-05-02 — 對應 commit `04f5120` 及之後 main 上的 schema。*
