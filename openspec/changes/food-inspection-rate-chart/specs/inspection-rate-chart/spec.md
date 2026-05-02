## ADDED Requirements

### Requirement: City filter selector
The component SHALL display a dropdown selector allowing the user to choose between 臺北市 and 新北市. Selecting a city SHALL re-fetch chart data with the corresponding city parameter.

#### Scenario: Default city on load
- **WHEN** the chart component mounts
- **THEN** 臺北市 is selected by default and data is fetched with `city=臺北市`

#### Scenario: User switches city
- **WHEN** the user selects 新北市 from the dropdown
- **THEN** the chart re-fetches data with `city=新北市` and updates both lines

### Requirement: Monthly inspection volume series (blue line)
The component SHALL display a blue line representing the total number of inspections per calendar month for the selected city, aggregated from the `inspection_date` field.

#### Scenario: Data rendered as blue line
- **WHEN** chart data is loaded
- **THEN** the series named `抽檢量` SHALL be rendered as a blue line with values equal to the monthly inspection count

#### Scenario: Monthly granularity
- **WHEN** multiple inspection records share the same year-month
- **THEN** they are aggregated into a single data point on the x-axis

### Requirement: Monthly fail rate series (orange line)
The component SHALL display an orange line representing the monthly non-compliance rate (percentage) for the selected city, computed as `COUNT(hazard_level = '不合格') / COUNT(*) × 100`.

#### Scenario: Data rendered as orange line
- **WHEN** chart data is loaded
- **THEN** the series named `不合格率` SHALL be rendered as an orange line with values representing percentage (0–100)

#### Scenario: Zero-inspection month
- **WHEN** a month has zero inspections for the selected city
- **THEN** the fail rate data point for that month SHALL be 0 (no division by zero error)

### Requirement: Dual-axis display (shared x-axis, separate y-axes)
The chart SHALL render both series on a shared time x-axis. The two series SHALL share the same x-axis (months) and display on separate y-axes to accommodate different value scales (count vs. percentage).

#### Scenario: Both series visible simultaneously
- **WHEN** data for both series is available
- **THEN** both lines are drawn on the same chart within the same time range

### Requirement: Backend time_series data endpoint
The backend SHALL serve monthly aggregated data for component 1200 via the existing `/api/v1/component/:id/chart` endpoint using `query_type = "time_series"`. The SQL query SHALL accept a `{city}` substitution parameter and return rows with `x_axis` (first day of month, timestamp), `y_axis` (series name), and `data` (numeric value).

#### Scenario: Valid city param returns two series
- **WHEN** `GET /api/v1/component/1200/chart?city=臺北市` is called
- **THEN** the response contains exactly two series: `抽檢量` and `不合格率`, each with one data point per month

#### Scenario: Missing city param defaults to 臺北市
- **WHEN** `GET /api/v1/component/1200/chart` is called without a city param
- **THEN** the response returns data for 臺北市
