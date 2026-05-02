## 為何做

食安風險追蹤器儀表板目前以快照方式呈現稽查現況，無法讓使用者看出各月稽查數量的趨勢變化（是否改善或惡化）。在 `food_safety_inspection_metrotaipei` 資料表上新增月度趨勢折線圖，可揭露季節性規律與風險升高的時序訊號。

## 變更內容

- 新增 `query_charts` 紀錄（`food_safety_monthly_trend`）：使用 `three_d` 查詢類型，以 `YYYY-MM` × `hazard_level` 聚合稽查件數，供堆疊時序圖呈現。
- 在 `db-sample-data/dashboardmanager-demo.sql` 中登錄此元件，使其在本機食安儀表板上免 Airflow 執行即可顯示。
- 擴充 `db-sample-data/check.sql` 現有 fixture，新增跨多個月份的樣本資料，讓趨勢圖在本機有可見的資料點。

## 能力範疇

### 新增能力

- `food-safety-monthly-trend-chart`：以 `TimelineStackedChart` 呈現 `food_safety_inspection_metrotaipei` 的月度稽查件數，依危害等級（hazard_level）堆疊，涵蓋雙北，並整合至現有食安儀表板頁面。

### 修改能力

- `food-safety-check-db-sample`：擴充現有 SQL fixture，新增跨月份的 `INSERT` 資料列，使趨勢圖有足夠資料點可顯示。

## 影響範圍

- `db-sample-data/check.sql`：新增多月份 `INSERT` 資料列。
- `db-sample-data/dashboardmanager-demo.sql`：`query_charts`、`components`、`dashboard_components` 各新增一筆紀錄。
- Go 後端、Airflow DAG、資料庫 migration、Vue 元件均無需修改（沿用現有 `TimelineStackedChart`）。
