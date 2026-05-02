## Context

The dashboard platform uses a database-driven component system where:
- Each component has an `index` in the `components` table and a linked row in `query_charts` with the SQL query and `query_type`
- `query_type = "time_series"` routes to `GetTimeSeriesData()` which aggregates rows of `(x_axis, y_axis, data)` into named series
- City filtering is passed as `?city=` query param and substituted into the SQL at query time
- The frontend `TimelineSeparateChart.vue` already renders multi-series line charts via ApexCharts using `series` prop shaped as `[{name, data: [{x, y}]}]`

This change registers a new component (dashboard_id 1200) and wires a city-filterable monthly aggregation query into the existing pipeline without any new Go code or new Vue components.

## Goals / Non-Goals

**Goals:**
- Register component 1200 (`food_inspection_rate`) in the database with `query_type = "time_series"`
- SQL query returns two named series per city: `抽檢量` (total monthly inspections) and `不合格率` (fail count / total × 100)
- Frontend config sets series 0 color to blue, series 1 color to orange and maps to `TimelineSeparateChart`
- City dropdown (臺北市 / 新北市) filters the query via existing `?city=` param

**Non-Goals:**
- No new Go controller or model functions — the existing `GetComponentChartData` + `GetTimeSeriesData` pipeline handles this
- No new Vue component — `TimelineSeparateChart.vue` is reused
- No database schema migration — the food safety table already has `inspection_date`, `hazard_level`, `city`

## Decisions

### Decision 1: Use `time_series` query_type with a UNION query
**Why**: `GetTimeSeriesData` groups rows by `y_axis` into named series. A UNION of two SELECT statements — one for total count, one for fail rate — produces the two series in a single query execution.
**Alternative**: A custom `query_type` with a dedicated controller function. Rejected because it requires Go changes and duplicates existing infrastructure.

### Decision 2: Express fail rate as percentage (0–100) in the SQL, not a ratio (0–1)
**Why**: ApexCharts renders the `y` value directly as a number with the configured `unit`. Using percentage (e.g. 12.5) with `unit: "%"` is more readable than 0.125.
**Alternative**: ratio with `unit: ""` and a frontend formatter. Rejected as more complex.

### Decision 3: City filter via substitution parameter `{city}` in SQL
**Why**: Existing `GetComponentChartDataQuery` already substitutes `{city}` in the stored SQL string before execution.
**Alternative**: A separate component per city. Rejected — wastes DB rows and breaks the city-filter UX pattern.

### Decision 4: Frontend dropdown drives `?city=` API param via existing chart config `filter` mechanism
**Why**: Other components use `chart_config.filter` to pass city to the API. Reusing this avoids custom event handling in the new component.

## Risks / Trade-offs

- **Risk**: UNION query performance on large inspection tables → Mitigation: index on `(city, inspection_date, hazard_level)` recommended; query only touches month-level aggregates
- **Risk**: Division by zero if a month has zero inspections in the city filter → Mitigation: `NULLIF(total, 0)` in SQL; `GetTimeSeriesData` maps NULL to 0
- **Trade-off**: Fail rate and total count have very different scales (e.g., 5% vs 300 inspections); rendered on the same Y-axis. The `TimelineSeparateChart` uses a single axis — if this looks poor visually, a `ColumnLineChart` (dual-axis) can be swapped in without backend changes.
