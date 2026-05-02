# 校園午餐資料字典 — School Meal Data Dictionary

> **給提案團隊**：以下 7 張資料表來自「校園食材登入平台」OpenAPI（衛福部 K12EA 教育部午餐管理系統），雙北全部抓得到，已部署於 main。
> 每張表的時空覆蓋、欄位語意、衍生指標、提案速查表都列出來，方便評估能不能拿來做新元件。
>
> - 全部位於 `dashboard` PostgreSQL DB（host:5433）
> - 一鍵 populate：`./scripts/school_meal_ingredients/apply.sh`
> - Schema 規格：`scripts/school_meal_ingredients/migrations/{001,002}_*.up.sql`
> - 資料抓取：`scripts/school_meal_ingredients/etl/snapshot_apis.py`（resumable，年月可縮放）
> - 完整實作背景：`docs/superpowers/specs/2026-05-02-school-meal-ingredients-design.md`

## 概覽（一表盤點）

| Table | 範圍 | Rows (2024/10) | 時間 | 空間 | 主要用途 |
|---|---|---:|---|---|---|
| `school_meal_ingredient_names` | 食材名稱去重字典 | 1,755 | 跨月聚合 | 雙北 | AI 食材詞庫、首次/末次出現年月、出現次數 |
| `school_meal_food_dictionary` | 官方食材中文標準名稱 + 俗名 | 2,937 | 一次性（2022/11） | 全國 | 食材標準化、俗名對照（如「攋尿蝦」← 「黃順」）|
| `school_meal_caterers` | 全國團膳業者清冊 | 595 | 月度快照 | 全國（含雙北）| 團膳業者列表（業者名 / 統編 / 地址）|
| `school_meal_seasoning_records_nation` | 全國調味料使用記錄 | 103,518 | 起迄日期 | 全國 | 學校 × 調味料 × 供應商；認證標章追蹤 |
| `school_meal_ingredient_records` | 雙北食材使用記錄 | 278,402 | 供餐日期 | 雙北 × 國中小/高中職 | 學校 × 供餐日 × 食材 × 食材供應商 + 調味料 |
| `school_meal_dish_records` | 雙北午餐菜色記錄 | 112,744 | 供餐日期 | 雙北 × 國中小/高中職 | 學校 × 供餐日 × 菜色名稱（菜單）|
| `school_meal_dish_ingredient_records` | 雙北菜色×食材聯合表 | 278,402 | 供餐日期 | 雙北 × 國中小/高中職 | 學校 × 供餐日 × 菜色 × 食材 × 供應商（最完整 fact 表）|

**重點原則：**
- 雙北 city × grade 表（`*_ingredient_records` / `*_dish_records` / `*_dish_ingredient_records`）含 4 欄 provenance（`year_queried, month_queried, county_queried, grade_queried`），記錄是哪次 API 查詢產生這筆 row，方便溯源。
- 全國表（`food_dictionary` / `caterers` / `seasoning_records_nation`）不分 city × grade — 雙北資料**已包含於全國表內**，按 `縣市名稱` / `county` 篩選即可。
- **目前 row count 僅涵蓋 2024/10 單月**。`snapshot_apis.py --year-from 2020` 可做 5 年回填（resumable + token 過期 graceful exit）。
- AI / NLP 任務優先：`school_meal_ingredient_names`（去重字典）+ `school_meal_food_dictionary`（標準名/俗名）兩張為核心。

---

## 1. `school_meal_ingredient_names` — 雙北食材名稱去重字典（核心 AI 詞庫）

> 從 6 張 raw table 中萃取出的「食材名稱」唯一值，附帶出現次數、首末次出現年月、來源縣市。
> Source: `school_meal_ingredient_records.ingredient_name` + `school_meal_dish_ingredient_records.ingredient_name`（loader: `etl/load_ingredient_names.py`）

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `name` | VARCHAR(200) UNIQUE NOT NULL | 食材名稱（已去重）| "胡蘿蔔" |
| `occurrence` | INTEGER NOT NULL | 該食材在所有 row 出現次數 | 34,076 |
| `first_seen_ym` | VARCHAR(7) | 首次出現的年月（'YYYY-MM'）| "2024-10" |
| `last_seen_ym` | VARCHAR(7) | 最末次出現的年月（'YYYY-MM'）| "2024-10" |
| `source_counties` | TEXT[] | 出現過的縣市 array | `{臺北市,新北市}` |

**Top 10 高頻食材（2024/10 雙北）：**

| 食材 | 次數 |
|---|---:|
| 胡蘿蔔 | 34,076 |
| 白米 | 26,530 |
| 洋蔥 | 17,362 |
| 紅蘿蔔 | 13,802 |
| 木耳 | 10,156 |
| 馬鈴薯 | 9,750 |
| 雞蛋 | 9,584 |
| 白蘿蔔 | 9,230 |
| 杏鮑菇 | 7,838 |
| 金針菇 | 7,732 |

**衍生指標：**
- AI 食材實體辨識（NER）詞庫
- 食材標準化字典（找「胡蘿蔔 / 紅蘿蔔」這類同物異名 — 出現次數懸殊但可能指同一物）
- 季節性食材偵測（多月回填後 `first_seen_ym` / `last_seen_ym` 差距）
- 雙北專屬食材 vs 共通食材（以 `source_counties` 篩選）

**強制條件：** loader 啟動時若任一城市缺失即 `sys.exit(1)` — 雙北合規 enforced。

---

## 2. `school_meal_food_dictionary` — 官方食材中文標準名稱字典（一次性 2022/11）

> 教育部 K12EA 平台官方公布的食材中文標準名稱，含俗名對照。**只有一份 snapshot**（建立於 2022/11），但作為標準化字典已足夠。
> Source: `food_chinese_names.csv`（datasetname = `食材中文名稱資料集`）

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `food_category` | VARCHAR(100) | 食材類別 | "豆魚蛋肉類" |
| `formal_name` | VARCHAR(200) NOT NULL | 食材中文標準名稱 | "素麥克雞塊" |
| `alias_name` | TEXT | 俗名（多筆換行分隔，可包含多個別名）| "雞翅膀\n翅膀" |

**衍生指標：**
- 食材標準化映射表（`alias_name → formal_name`）— 把使用者輸入的俗名轉成標準名
- 食材類別聚合（蔬菜 / 肉類 / 水產 / 蛋豆⋯）
- AI 訓練 corpus 的 ground truth 對照

**注意：** `alias_name` 可能含換行符與空字串；CSV 用 quoted multi-line 格式儲存（`csv.DictReader` 已正確處理）。

---

## 3. `school_meal_caterers` — 全國團膳業者清冊

> 全國列管的學校供餐團膳業者，每月快照。雙北業者按 `county` 過濾。
> Source: `nation_*_學校供餐團膳業者*.csv`

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `county` | VARCHAR(20) | 縣市名稱 | "臺北市" |
| `name` | VARCHAR(300) NOT NULL | 業者名稱 | "○○團膳股份有限公司" |
| `tax_id` | VARCHAR(20) | 業者統一編號 | "12345678" |
| `address` | VARCHAR(500) | 業者地址 | "臺北市內湖區..." |

**衍生指標：**
- 雙北團膳業者市佔比較
- 統編 join `school_meal_ingredient_records.caterer_tax_id` 找該業者實際供餐紀錄
- 地址 geocode → 業者點位地圖
- 與其他公開資料庫（GCIS 商業司）join 找業者規模

---

## 4. `school_meal_seasoning_records_nation` — 全國調味料使用記錄

> 各校使用的調味料（鹽、糖、醬油、麻油⋯）+ 供應商 + 使用起迄日期。雙北資料按 `county` 過濾。
> Source: `nation_*_調味料及供應商*.csv`

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `county` | VARCHAR(20) | 縣市名稱 | "新北市" |
| `district` | VARCHAR(50) | 區域名稱 | "板橋區" |
| `school_name` | VARCHAR(300) | 學校名稱 | "○○國民小學" |
| `start_date` | DATE | 開始使用日期 | 2024-10-01 |
| `end_date` | DATE | 結束使用日期 | 2024-10-31 |
| `caterer_name` | VARCHAR(300) | 供餐業者 | "○○團膳" |
| `caterer_tax_id` | VARCHAR(20) | 供餐業者統一編號 | — |
| `seasoning_supplier_name` | VARCHAR(300) | 調味料供應商名稱 | "○○食品" |
| `seasoning_name` | VARCHAR(200) | 調味料名稱 | "醬油" |
| `certification_label` | VARCHAR(100) | 認證標章 | "ISO 22000" |
| `certification_no` | VARCHAR(100) | 認證編號 | — |

**衍生指標：**
- 雙北調味料使用 Top N（鹽、糖、油、醬料⋯）
- 認證標章覆蓋率（有認證的 supplier 佔比）
- 同一調味料的多源頭 supplier 比較
- 供應商 × 學校 bipartite graph（看供應集中度）

---

## 5. `school_meal_ingredient_records` — 雙北食材使用記錄（fact 表）

> 雙北 × 國中小/高中職的「學校 × 供餐日 × 食材」最細顆粒記錄。每 row 同時包含食材 + 對應調味料供應資訊。
> Source: `(tpe|ntpc)_YYYYMM_(國中小|高中職)_午餐食材及供應商*.csv`

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `year_queried` | SMALLINT NOT NULL | API 查詢年份（**provenance**）| 2024 |
| `month_queried` | SMALLINT NOT NULL | API 查詢月份 | 10 |
| `county_queried` | VARCHAR(20) NOT NULL | API 查詢縣市（`臺北市`/`新北市`/`全國`）| "臺北市" |
| `grade_queried` | VARCHAR(20) NOT NULL | API 查詢學級（`國中小`/`高中職`）| "國中小" |
| `county` | VARCHAR(20) | row 內市縣名稱 | "臺北市" |
| `district` | VARCHAR(50) | 區域名稱 | "信義區" |
| `school_name` | VARCHAR(300) | 學校名稱 | "○○國民中學" |
| `meal_date` | DATE | 供餐日期 | 2024-10-15 |
| `caterer_name` | VARCHAR(300) | 供餐業者 | "○○團膳" |
| `caterer_tax_id` | VARCHAR(20) | 供餐業者統編 | "12345678" |
| `ingredient_supplier_name` | VARCHAR(300) | 食材供應商名稱 | "○○農產" |
| `ingredient_supplier_tax_id` | VARCHAR(20) | 食材供應商統編 | — |
| `ingredient_name` | VARCHAR(200) | 食材名稱 | "胡蘿蔔" |
| `seasoning_supplier_name` | VARCHAR(300) | 調味料供應商名稱 | — |
| `seasoning_supplier_tax_id` | VARCHAR(20) | 調味料供應商統編 | — |
| `seasoning_name` | VARCHAR(200) | 調味料名稱 | "鹽" |
| `certification_label` | VARCHAR(100) | 認證標章 | "產銷履歷" |
| `certification_no` | VARCHAR(100) | 認證編號 | — |

**約束：**
- `CHECK (month_queried BETWEEN 1 AND 12)`
- `CHECK (county_queried IN ('臺北市','新北市','全國'))` — 雙北政策硬性鎖定
- Index：`(county_queried, year_queried, month_queried)` 主篩選 + `(ingredient_name)` AI 查詢

**衍生指標：**
- 學校 × 食材 × 日期 fact pivot（每校每日吃了哪些食材）
- 食材使用熱力圖（行政區 × 食材）
- 供應商集中度（一個食材幾個供應商在供）
- 供餐日數 / 月（學校稽核）
- 與調味料 join：每餐的食材 + 調味料完整搭配

---

## 6. `school_meal_dish_records` — 雙北午餐菜色記錄

> 雙北學校的「學校 × 供餐日 × 菜色名稱」記錄（菜單）。**菜色不是食材** — 是組合而成的菜餚（如「番茄炒蛋」、「咖哩雞」）。
> Source: `(tpe|ntpc)_YYYYMM_(國中小|高中職)_午餐菜色資料集.csv`

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `year_queried` | SMALLINT NOT NULL | provenance 年 | 2024 |
| `month_queried` | SMALLINT NOT NULL | provenance 月 | 10 |
| `county_queried` | VARCHAR(20) NOT NULL | provenance 縣市 | "新北市" |
| `grade_queried` | VARCHAR(20) NOT NULL | provenance 學級 | "高中職" |
| `county` | VARCHAR(20) | row 內市縣 | "新北市" |
| `district` | VARCHAR(50) | 區域 | "三重區" |
| `school_name` | VARCHAR(300) | 學校名稱 | "○○高中" |
| `meal_date` | DATE | 供餐日期 | 2024-10-21 |
| `dish_name` | VARCHAR(200) | 菜色名稱 | "番茄炒蛋" |

**約束：** 同 #5（month/county CHECK + provenance index）。再加 `(dish_name)` index。

**衍生指標：**
- Top 菜色排行（哪些菜最常出現）
- 菜色重複度（同學校 N 天內重複次數）
- 菜色 × 學級對比（國中小 vs 高中職偏好差異）
- 季節性菜色（多月回填後）
- 雙北菜色多樣性比較

**用途分野：** 適合做菜單分析 / 推薦；不適合做食材營養分析（拆不出組成）。

---

## 7. `school_meal_dish_ingredient_records` — 雙北菜色×食材聯合表（最完整 fact）

> 把 #5（食材）+ #6（菜色）展開成「菜色 → 食材」明細。**最完整的事實表**，row 數與 `school_meal_ingredient_records` 相同（每菜色用了哪些食材）。
> Source: `(tpe|ntpc)_YYYYMM_(國中小|高中職)_午餐菜色及食材*.csv`

| 欄位 | 型別 | 意義 | 範例 |
|---|---|---|---|
| `id` | SERIAL PK | 自動編號 | — |
| `year_queried` | SMALLINT NOT NULL | provenance 年 | 2024 |
| `month_queried` | SMALLINT NOT NULL | provenance 月 | 10 |
| `county_queried` | VARCHAR(20) NOT NULL | provenance 縣市 | "臺北市" |
| `grade_queried` | VARCHAR(20) NOT NULL | provenance 學級 | "國中小" |
| `county` | VARCHAR(20) | row 內市縣 | "臺北市" |
| `district` | VARCHAR(50) | 區域 | "大安區" |
| `school_name` | VARCHAR(300) | 學校名稱 | "○○國小" |
| `meal_date` | DATE | 供餐日期 | 2024-10-15 |
| `caterer_name` | VARCHAR(300) | 供餐業者 | — |
| `caterer_tax_id` | VARCHAR(20) | 供餐業者統編 | — |
| `ingredient_supplier_name` | VARCHAR(300) | 食材供應商名稱 | — |
| `ingredient_supplier_tax_id` | VARCHAR(20) | 食材供應商統編 | — |
| `dish_category` | VARCHAR(100) | 菜色類別 | "主食" / "主菜" / "副菜" / "湯品" |
| `dish_name` | VARCHAR(200) | 菜色名稱 | "番茄炒蛋" |
| `ingredient_name` | VARCHAR(200) | 該菜色用到的食材 | "雞蛋" |
| `seasoning_supplier_name` | VARCHAR(300) | 調味料供應商 | — |
| `seasoning_supplier_tax_id` | VARCHAR(20) | 調味料供應商統編 | — |
| `seasoning_name` | VARCHAR(200) | 調味料名稱 | "鹽" |
| `certification_label` | VARCHAR(100) | 認證標章 | — |
| `certification_no` | VARCHAR(100) | 認證編號 | — |

**約束：** 同 #5/#6（month/county CHECK + provenance index）。再加 `(ingredient_name)` 與 `(dish_name)` 兩個 index。

**這張表是 #5 的超集 + 加 `dish_category` 與 `dish_name`**：每筆 ingredient_records 可對應多筆 dish_ingredient_records（一份食材可能用在多道菜）。

**衍生指標（最強）：**
- **菜色 → 食材組成 lookup**（「番茄炒蛋」用了哪些食材？）
- **食材 → 菜色 lookup**（「胡蘿蔔」出現在哪些菜？）
- 菜色類別營養分析（主食 / 主菜 / 副菜 / 湯品 食材分布）
- 食譜推薦 AI（菜色 + 食材 graph）
- 雙北菜色食材搭配差異
- Supplier-to-school routing（食材供應鏈視覺化）

---

## 提案參考速查（需求 → 資料源）

| 需求類型 | 推薦表 | 備註 |
|---|---|---|
| **AI 食材詞庫 / NER** | `school_meal_ingredient_names` | 已去重 + 出現次數 + 來源縣市 |
| **食材標準化（俗名 → 標準名）** | `school_meal_food_dictionary` | 官方對照表 |
| **菜色 → 食材組成** | `school_meal_dish_ingredient_records` | join `dish_name` → `ingredient_name` |
| **食材 → 菜色出現位置** | `school_meal_dish_ingredient_records` | filter `ingredient_name` |
| **學校 × 供餐日 × 食材** | `school_meal_ingredient_records` | 最細顆粒 |
| **學校菜單** | `school_meal_dish_records` | 每校每日菜色 |
| **團膳業者 × 學校關係** | `school_meal_caterers` + records 表 join `tax_id` | 業者市場分析 |
| **調味料使用情況** | `school_meal_seasoning_records_nation` | 全國 + 起迄日期 |
| **雙北菜色多樣性比較** | `school_meal_dish_records` | group by `county_queried` |
| **食材供應商集中度** | `*_records.ingredient_supplier_name` | 一食材幾家在供 |
| **行政區聚合** | 三張 records 表的 `district` 欄 | 學校所在行政區 |
| **時序分析（年月趨勢）** | provenance 4 欄（`year_queried, month_queried`）+ records | 需先回填多月 |

## 資料更新流程

| 資料源 | 更新頻率 | 流程 |
|---|---|---|
| K12EA OpenAPI（雙北月度資料 + 全國月度業者/調味料）| 教育部每月 | `python3 scripts/school_meal_ingredients/etl/snapshot_apis.py --year-from 2024 --month-from 10 --year-to 2024 --month-to 10`（範圍可調）→ commit `snapshots/*.csv` + `manifest.json` → 重跑 `apply.sh` |
| 食材中文名稱資料集 | 一次性（2022/11 公布後未更新）| 同上一鍵抓取，`food_chinese_names.csv` 一次到位 |

**回填全部 5 年（2020/01 → 當月）：** 直接執行 `snapshot_apis.py` 不帶範圍參數。Token 過期時 graceful exit + manifest 保留進度，更新 `FATRACE_ACCESSCODE` 後 rerun 即續抓。

## 對應 dashboard components

**目前未 wired 任何 dashboard component**（提案空間最大）。

提案速查：

- 雙北學校菜單比較地圖：`school_meal_dish_records` + `district` 聚合
- 食材供應鏈視覺化：`school_meal_ingredient_records` 的 supplier × school 雙邊圖
- AI 食材標準化助手：`school_meal_ingredient_names` + `school_meal_food_dictionary`
- 認證食材覆蓋追蹤：`*_records.certification_label` 非空率隨年月變化
- 季節性食材推薦：多月回填後 `meal_date` 月份 × `ingredient_name` 熱力圖
- 雙北菜色多樣性指數（每校每月 unique dish 數）

---

*Generated: 2026-05-02 — 對應 main 上 schema commit；migration 001 + 002 = 7 張表。*
