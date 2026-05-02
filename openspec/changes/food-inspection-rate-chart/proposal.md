## Why

食品安全稽查資料目前缺乏直觀的月度趨勢視覺化，無法讓使用者快速掌握雙北各月抽檢量與不合格率的變化。此功能透過雙線圖呈現每月抽檢總量（藍線）與不合格率（橘線），並支援台北市/新北市切換，讓決策者能即時識別食安風險趨勢。

## What Changes

- **新增前端雙線圖元件**：在 `DashboardComponent` 體系下新增月度抽檢量（藍線）與不合格率（橘線）雙線折線圖，支援城市篩選下拉選單（台北市 / 新北市）。
- **後端新增 dashboard_id 1200 的資料端點**：於現有 `componentData` 機制下，透過 `componentConfig` 註冊新元件，提供按城市過濾後的月度抽檢量及不合格數統計資料。
- **資料轉換邏輯**：後端依 `inspection_date` 彙整每月資料，計算總抽檢量與 `hazard_level == "不合格"` 的不合格率（不合格數 ÷ 總抽檢量）。

## Capabilities

### New Capabilities
- `inspection-rate-chart`: 月度食安抽檢不合格率雙線圖元件，含城市篩選，顯示每月抽檢量（藍線）與不合格率（橘線），對應 dashboard_id 1200。

### Modified Capabilities

## Impact

- **Frontend**: 新增 Vue 3 折線圖元件（基於現有 `BarChart`/`LineChart` 元件模式），新增城市篩選 props 與資料聚合邏輯。
- **Backend**: 在 `componentConfig.go` 中新增 component 設定項（id 對應 dashboard_id 1200），`componentData.go` 新增對應資料查詢函式，`dashboard.go` 路由可複用現有 `/api/v1/component/:id/chart` 端點。
- **Database**: 依賴現有食安稽查資料表（含 `inspection_date`、`hazard_level`、`city` 欄位）；無 schema 變更。
