## 背景脈絡

食安風險追蹤器現有儀表板已完成以下基礎建設：
- `food_safety_inspection_metrotaipei` PostgreSQL 資料表（由 Airflow DAG 寫入），含 `city`（臺北市 / 新北市）、`inspection_date`（DATE）、`inspection_result` 欄位
- `db-sample-data/check.sql` 提供本機開發用的樣本資料 fixture
- 前端已有 `TimelineSeparateChart` 元件（ApexCharts line chart，x 軸為 datetime 類型，支援多系列）
- 後端 `query_type = "time"` 對應 `GetTimeSeriesData`，依 `y_axis` 值分組，回傳 `{name, data: [{x: timestamp, y: number}]}` 格式
- 城市切換機制：`query_charts` 表同一 `index` 可有多個 `city` 變體，API 依 `?city=` 參數取對應 SQL
- 食安儀表板 `dashboard_id = 1200`

約束：不修改 Go 程式碼、Vue 元件、DAG 或 schema migration。

## 目標 / 非目標

**目標：**
- 新增雙折線趨勢圖，x 軸為月份，y 軸為數量，兩條線：
  1. **藍線**：月抽檢總量（`COUNT(*)`，依 `inspection_date` 統計）
  2. **橘線**：月違規率（`COUNT(*) FILTER (WHERE inspection_result = '不合格') / COUNT(*) × 100`，百分比）
- 提供城市下拉選單（臺北市 / 新北市），透過 `city` 欄位過濾資料
- 在 `dashboardmanager-demo.sql` 中完整登錄，本機免執行 Airflow 即可看到圖表
- 擴充 `check.sql` fixture，提供跨至少 6 個月份的資料點（含合格 / 不合格）

**非目標：**
- 不新增 API endpoint 或修改 Go 路由
- 不新增 Vue 元件（沿用 `TimelineSeparateChart`）
- 不實作地圖圖層互動或歷史資料查詢

## 技術決策

### 決策 1：使用 `query_type = "time"` + `TimelineSeparateChart`

`TimelineSeparateChart` 渲染 ApexCharts `type="line"`，支援多系列共享同一 datetime x 軸，可顯示「月抽檢總量」＋「違規率」兩條線。

**SQL 查詢設計（以臺北市為例）：**
```sql
SELECT
  date_trunc('month', inspection_date)::timestamptz  AS x_axis,
  '月抽檢總量'                                        AS y_axis,
  COUNT(*)::float                                     AS data
FROM food_safety_inspection_metrotaipei
WHERE inspection_date IS NOT NULL
  AND city = '臺北市'
GROUP BY 1

UNION ALL

SELECT
  date_trunc('month', inspection_date)::timestamptz  AS x_axis,
  '違規率(%)'                                         AS y_axis,
  ROUND(
    COUNT(*) FILTER (WHERE inspection_result = '不合格')
    * 100.0 / NULLIF(COUNT(*), 0), 1
  )                                                  AS data
FROM food_safety_inspection_metrotaipei
WHERE inspection_date IS NOT NULL
  AND city = '臺北市'
GROUP BY 1
ORDER BY 1, 2
```

新北市版本將 `city = '臺北市'` 改為 `city = '新北市'`。

### 決策 2：兩個 `query_charts` 城市變體（taipei / newtaipei）

後端 `GetComponentChartDataQuery` 以 `components.index` JOIN `query_charts.index` 並 `WHERE query_charts.city = ?` 取對應 SQL。因此需要兩筆 `query_charts` 紀錄，`index` 相同（`food_safety_monthly_trend`），`city` 各為 `taipei` 和 `newtaipei`，SQL 分別過濾 `city = '臺北市'` / `city = '新北市'`。

前端 `DashboardComponent` 的 `selectBtn` 下拉選單由父元件傳入 `selectBtnList`，切換時觸發 `changeCity` 事件，重新以新 `city` 參數呼叫 API。

### 決策 3：兩條線共用同一 y 軸（接受比例不一致的取捨）

`TimelineSeparateChart` 目前不支援雙 y 軸，月抽檢總量（件數）與違規率（%）共享同一軸。在 fixture 資料量下兩者數值接近，視覺上尚可接受。未來若需雙軸，可新增 `ColumnLineChart` 元件，但不在本次範疇。

### 決策 4：`chart_config.color` 指定 `["#3D8BFF", "#FF7043"]`

在 `components` 的 `chart_config` JSON 中指定顏色陣列，確保藍線（月抽檢總量）在前、橘線（違規率）在後。

## 風險 / 取捨

- **y 軸共用**：若月總量遠大於 100，違規率曲線會被壓扁。→ 接受此取捨，符合本次範疇約束。
- **`inspection_date` 為 DATE 型別**：`date_trunc('month', date_col)` 回傳 `timestamp without time zone`，需明確 cast 為 `timestamptz` 讓 `GetTimeSeriesData` 正確解析。→ SQL 中使用 `date_trunc(...)::timestamptz`。
- **fixture 月份跨度不足**：若資料僅含 1-2 個月，圖表無趨勢可言。→ `check.sql` 補充 2024-01 ～ 2024-06 共 6 個月，每月各 5-10 筆，含合格 / 不合格。
- **違規率分母為零**：若某月無資料，`NULLIF(COUNT(*), 0)` 回傳 NULL，後端 GORM scan 至 `float64` 會為 0，前端顯示 0%，無誤導。

## 部署計畫

1. 修改 `db-sample-data/check.sql`，新增 2024-01 ～ 2024-06 跨月份 INSERT 資料列（含合格 / 不合格各月份）。
2. 在 `db-sample-data/dashboardmanager-demo.sql` 新增：
   - `query_charts`：兩筆紀錄（`city = taipei` / `city = newtaipei`），`query_type = 'time'`
   - `components`：一筆元件紀錄（`index = 'food_safety_monthly_trend'`）
   - `dashboard_components`：一筆紀錄，綁定至 `dashboard_id = 1200`
3. 重建本機資料庫 fixture，確認城市切換與折線圖均正常顯示。
4. 回滾：刪除上述新增紀錄及 INSERT 列，無 schema 變更。
