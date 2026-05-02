## ADDED Requirements

### Requirement: 月趨勢圖元件登錄於 dashboardmanager
`db-sample-data/dashboardmanager-demo.sql` SHALL 包含 `food_safety_monthly_trend` 的 `query_charts`、`components`、`dashboard_components` 三筆紀錄，使 `dashboard_id = 1200` 的食安儀表板在載入 fixture 後即可顯示此元件。

#### Scenario: 本機 fixture 匯入後元件出現在食安儀表板
- **WHEN** `dashboardmanager-demo.sql` 匯入至本機 PostgreSQL
- **THEN** `SELECT * FROM dashboard_components WHERE dashboard_id = 1200` 包含 `food_safety_monthly_trend` 相關元件紀錄

### Requirement: query_charts 提供 taipei 與 newtaipei 兩個城市變體
`query_charts` 表中 `index = 'food_safety_monthly_trend'` SHALL 存在 `city = 'taipei'` 與 `city = 'newtaipei'` 兩筆紀錄，各自的 `query_chart` SQL 以 `WHERE city = '臺北市'` 或 `WHERE city = '新北市'` 過濾 `food_safety_inspection_metrotaipei`。

#### Scenario: 以 taipei city 查詢只回傳臺北市資料
- **WHEN** API 呼叫 `/component/{id}/chart?city=taipei`
- **THEN** 回傳的時序資料中所有月份數值均來自 `city = '臺北市'` 的稽查紀錄

#### Scenario: 以 newtaipei city 查詢只回傳新北市資料
- **WHEN** API 呼叫 `/component/{id}/chart?city=newtaipei`
- **THEN** 回傳的時序資料中所有月份數值均來自 `city = '新北市'` 的稽查紀錄

### Requirement: query_chart SQL 回傳月抽檢總量與違規率兩個系列
SQL 查詢 SHALL 回傳兩個 `y_axis` 系列：
1. `y_axis = '月抽檢總量'`：該城市當月所有 `inspection_date IS NOT NULL` 的稽查件數（`COUNT(*)`）
2. `y_axis = '違規率(%)'`：當月 `inspection_result = '不合格'` 件數除以總件數乘以 100，四捨五入至小數點一位；分母為零時回傳 `NULL` 或 0

#### Scenario: 某月有 10 筆資料其中 2 筆不合格
- **WHEN** 某城市某月有 10 筆稽查紀錄，其中 2 筆 `inspection_result = '不合格'`
- **THEN** 該月 `月抽檢總量` 系列的 `data = 10`，`違規率(%)` 系列的 `data = 20.0`

#### Scenario: 某月所有稽查均合格
- **WHEN** 某城市某月所有稽查結果均為 `'合格'`
- **THEN** 該月 `違規率(%)` 系列的 `data = 0`

### Requirement: query_type 為 time，x 軸為月份 timestamptz
`query_charts` 的 `query_type` SHALL 為 `'time'`，`x_axis` 欄位 SHALL 為 `date_trunc('month', inspection_date)::timestamptz`，使後端 `GetTimeSeriesData` 可正確解析為時間序列格式 `{x: ISO timestamp, y: number}`。

#### Scenario: 回傳格式為時序陣列
- **WHEN** API 呼叫 `/component/{id}/chart?city=taipei`
- **THEN** response body 格式為 `{"status":"success","data":[{"name":"月抽檢總量","data":[{"x":"2024-01-01T00:00:00+08:00","y":...},...]},...]}` 

### Requirement: chart_config 指定 TimelineSeparateChart 與藍橘配色
`components` 表的 `chart_config` JSON SHALL 包含 `"types": ["TimelineSeparateChart"]` 及 `"color": ["#3D8BFF", "#FF7043"]`，確保前端渲染為折線圖且藍線（月抽檢總量）在前、橘線（違規率）在後。

#### Scenario: chart_config 設定正確
- **WHEN** `SELECT chart_config FROM components WHERE index = 'food_safety_monthly_trend'` 執行
- **THEN** 回傳的 JSON 包含 `types` 陣列中有 `"TimelineSeparateChart"`，且 `color` 陣列第一個元素為 `"#3D8BFF"`，第二個為 `"#FF7043"`
