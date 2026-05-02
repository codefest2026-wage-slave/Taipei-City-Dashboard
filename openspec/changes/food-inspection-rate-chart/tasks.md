## 1. Database — Register Component 1200

- [x] 1.1 Insert a row into `components` table: `id=1200, index='food_inspection_rate', name='食安抽檢不合格率'`
- [x] 1.2 Insert a row into `query_charts` table with `query_type='time'`, two city rows (taipei=臺北市, metrotaipei=新北市), UNION SQL query returning `(x_axis, y_axis='抽檢量', data=monthly_count)` UNION `(x_axis, y_axis='不合格率', data=ROUND(...))` from `food_safety_inspection_metrotaipei`, grouped by `DATE_TRUNC('month', inspection_date)`. Filter uses `inspection_result NOT IN ('合格')` (not hazard_level — that column stores risk levels, not pass/fail).
- [x] 1.3 Insert rows into `dashboards` (id=1200) and `dashboard_groups` (groups 2=taipei, 3=metrotaipei) linking dashboard 1200 to component 1200.

## 2. Backend — Verify Endpoint

- [ ] 2.1 Test `GET /api/v1/component/1200/chart?city=taipei` returns two series (`不合格率`, `抽檢量`) each with monthly `{x, y}` data points
- [ ] 2.2 Test `GET /api/v1/component/1200/chart?city=metrotaipei` returns correct New Taipei City data
- [x] 2.3 Confirmed missing `city` param defaults to `taipei` — verified in `GetComponentChartData` controller (lines 36-38): if `query.City == ""` then `query.City = "taipei"`.

## 3. Frontend — Component Config

- [x] 3.1 Chart config stored in DB via `component_charts` INSERT: `color: ['#2894FF', '#FF7A00']` (blue, orange), `types: ['TimelineSeparateChart']`, `unit: '%'`
- [x] 3.2 City selector uses the existing global city mechanism (cityManager selectBtnList); no custom `chart_config.filter` needed. Dashboard in metrotaipei group → selectBtnList shows `[{name:"雙北",value:"metrotaipei"}, {name:"臺北市",value:"taipei"}]`. "臺北市" → 臺北市 data; "雙北" → 新北市 data (semantic mismatch acceptable for MVP).

## 4. Frontend — UI Wiring

- [x] 4.1 Confirmed `DashboardComponent.vue` maps `"TimelineSeparateChart"` → `TimelineSeparateChart.vue` at lines 197-198 — no change needed.
- [x] 4.2 Verified city toggle mechanism: `cityDashboard.components` pre-loads both city variants; `@change-city` swaps the displayed component via `contentStore.setComponentData`. Chart data is pre-fetched for each city via `city=component.city` param.
- [ ] 4.3 Smoke-test the component on dashboard 1200: both lines render, city switch updates data, blue = 抽檢量, orange = 不合格率. Run `scripts/food_safety_inspection_metrotaipei/apply.sh` first to seed the DB.
