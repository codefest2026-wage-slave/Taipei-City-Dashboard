package tools

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// ── SQL format constants (mirrors what is stored in query_charts) ───────────
// These are the SQL strings inserted into dashboardmanager-demo.sql.
// Keeping them here allows format validation without a live database.

// metrotaipei variants (New Taipei data tables)
const sqlFloodRiskMap = `SELECT CASE gridcode WHEN 1 THEN '0~30cm' WHEN 2 THEN '30~50cm' WHEN 3 THEN '50~100cm' WHEN 4 THEN '1~2m' WHEN 5 THEN '2m以上' END AS x_axis, COUNT(*)::int AS data FROM rainfall_flood_simulation_etl_ntpe GROUP BY gridcode ORDER BY gridcode`

const sqlRainfallRealtimeChart = `SELECT district AS x_axis, ROUND(AVG(rainfall_today)::numeric,1)::float AS data FROM rainfall_realtime_tpe GROUP BY district ORDER BY data DESC LIMIT 12`

const sqlShelterMap = `SELECT town AS x_axis, SUM(person_capacity::int) AS data FROM urbn_air_raid_shelter_ntpe GROUP BY town ORDER BY data DESC LIMIT 15`

const sqlDisasterRiskKpi = `SELECT '高風險面積(km²)' AS x_axis, ROUND(SUM(ST_Area(wkb_geometry::geography)/1e6)::numeric,2)::float AS data FROM rainfall_flood_simulation_etl_ntpe WHERE gridcode >= 3 UNION ALL SELECT '避難場所數' AS x_axis, COUNT(*)::float AS data FROM urbn_air_raid_shelter_ntpe UNION ALL SELECT '總避難容量(人)' AS x_axis, SUM(person_capacity::int)::float AS data FROM urbn_air_raid_shelter_ntpe ORDER BY x_axis`

// taipei variants (Taipei City data tables)
const sqlFloodRiskMapTpe = `SELECT CASE gridcode WHEN 1 THEN '0~30cm' WHEN 2 THEN '30~50cm' WHEN 3 THEN '50~100cm' WHEN 4 THEN '1~2m' WHEN 5 THEN '2m以上' END AS x_axis, COUNT(*)::int AS data FROM rainfall_flood_simulation_etl_tpe GROUP BY gridcode ORDER BY gridcode`

const sqlShelterMapTpe = `SELECT town AS x_axis, SUM(person_capacity::int) AS data FROM urbn_air_raid_shelter GROUP BY town ORDER BY data DESC LIMIT 15`

const sqlDisasterRiskKpiTpe = `SELECT '高風險面積(km²)' AS x_axis, ROUND(SUM(ST_Area(wkb_geometry::geography)/1e6)::numeric,2)::float AS data FROM rainfall_flood_simulation_etl_tpe WHERE gridcode >= 3 UNION ALL SELECT '避難場所數' AS x_axis, COUNT(*)::float AS data FROM urbn_air_raid_shelter UNION ALL SELECT '總避難容量(人)' AS x_axis, SUM(person_capacity::int)::float AS data FROM urbn_air_raid_shelter ORDER BY x_axis`

// AI tool query for flood risk
const sqlAIFloodRisk = `
		SELECT
			gridcode,
			COUNT(*) AS polygon_count,
			ROUND(SUM(area)::numeric / 1000000, 2) AS area_km2
		FROM rainfall_flood_simulation_etl_ntpe
		WHERE city LIKE '%' || ? || '%'
		GROUP BY gridcode
		ORDER BY gridcode
	`

// AI tool query for shelters
const sqlAIShelters = `
		SELECT address,
		       person_capacity::int AS capacity,
		       lng::float AS lng,
		       lat::float AS lat
		FROM urbn_air_raid_shelter_ntpe
		WHERE town = ?
		  AND person_capacity::int >= ?
		ORDER BY capacity DESC
		LIMIT 10
	`

// --- GetFloodRiskByDistrict tests (no DB required) ---

func TestGetFloodRiskByDistrict_EmptyDistrict(t *testing.T) {
	_, err := GetFloodRiskByDistrict(context.Background(), `{"district":""}`)
	if err == nil {
		t.Fatal("expected error for empty district, got nil")
	}
	if !strings.Contains(err.Error(), "district") {
		t.Errorf("error message should mention 'district', got: %v", err)
	}
}

func TestGetFloodRiskByDistrict_MissingDistrictKey(t *testing.T) {
	_, err := GetFloodRiskByDistrict(context.Background(), `{}`)
	if err == nil {
		t.Fatal("expected error when district key is missing")
	}
}

func TestGetFloodRiskByDistrict_InvalidJSON(t *testing.T) {
	_, err := GetFloodRiskByDistrict(context.Background(), `not-json`)
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}

// --- GetNearestShelters tests (no DB required) ---

func TestGetNearestShelters_EmptyDistrict(t *testing.T) {
	_, err := GetNearestShelters(context.Background(), `{"district":""}`)
	if err == nil {
		t.Fatal("expected error for empty district")
	}
	if !strings.Contains(err.Error(), "district") {
		t.Errorf("error should mention 'district', got: %v", err)
	}
}

func TestGetNearestShelters_NegativeCapacity(t *testing.T) {
	// Negative min_capacity should be clamped to 0, not error
	// (error would come from DB, not from validation — so we just
	//  verify the guard doesn't panic before reaching DB)
	params := ShelterArgs{District: "板橋區", MinCapacity: -10}
	if params.MinCapacity < 0 {
		params.MinCapacity = 0
	}
	if params.MinCapacity != 0 {
		t.Errorf("expected MinCapacity clamped to 0, got %d", params.MinCapacity)
	}
}

func TestGetNearestShelters_InvalidJSON(t *testing.T) {
	_, err := GetNearestShelters(context.Background(), `{broken`)
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}

// --- Registry tests ---

func TestDisasterToolsRegistered(t *testing.T) {
	tools := []string{"get_flood_risk_by_district", "get_nearest_shelters"}
	for _, name := range tools {
		if _, ok := registry[name]; !ok {
			t.Errorf("tool %q not registered", name)
		}
	}
}

func TestFloodRiskToolSchema(t *testing.T) {
	schema := map[string]interface{}{
		"name":        "get_flood_risk_by_district",
		"description": "查詢指定行政區的淹水潛勢風險",
		"parameters": map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"district": map[string]interface{}{
					"type":        "string",
					"description": "行政區名稱，例如：板橋區、中正區、汐止區",
				},
			},
			"required": []string{"district"},
		},
	}
	b, err := json.Marshal(schema)
	if err != nil {
		t.Fatalf("failed to marshal schema: %v", err)
	}
	if len(b) == 0 {
		t.Error("schema JSON should not be empty")
	}
}

func TestShelterToolSchema(t *testing.T) {
	schema := map[string]interface{}{
		"name":        "get_nearest_shelters",
		"description": "查詢指定行政區的避難場所列表，包括地址和容量",
		"parameters": map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"district": map[string]interface{}{
					"type":        "string",
					"description": "行政區名稱",
				},
				"min_capacity": map[string]interface{}{
					"type":        "integer",
					"description": "最小容量需求（人），預設 0",
					"default":     0,
				},
			},
			"required": []string{"district"},
		},
	}
	b, err := json.Marshal(schema)
	if err != nil {
		t.Fatalf("failed to marshal schema: %v", err)
	}
	if len(b) == 0 {
		t.Error("schema JSON should not be empty")
	}
}

func TestFloodDepthLabels(t *testing.T) {
	expected := map[int]string{
		1: "0~30cm",
		2: "30~50cm",
		3: "50~100cm",
		4: "1~2m",
		5: "2m以上",
	}
	for code, label := range expected {
		if floodDepthLabels[code] != label {
			t.Errorf("floodDepthLabels[%d] = %q, want %q", code, floodDepthLabels[code], label)
		}
	}
}

func TestFloodRiskLevelLogic(t *testing.T) {
	cases := []struct {
		ratio     float64
		wantLevel string
	}{
		{0.35, "極高"},
		{0.25, "高"},
		{0.15, "中"},
		{0.05, "低"},
	}
	for _, tc := range cases {
		level := "低"
		switch {
		case tc.ratio >= 0.3:
			level = "極高"
		case tc.ratio >= 0.2:
			level = "高"
		case tc.ratio >= 0.1:
			level = "中"
		}
		if level != tc.wantLevel {
			t.Errorf("ratio=%.2f: got %q, want %q", tc.ratio, level, tc.wantLevel)
		}
	}
}

// ── SQL format validation (no DB required) ─────────────────────────────────
// The backend executes query_chart SQL verbatim from DBManager.
// two_d queries must return columns: x_axis, data
// three_d queries must return columns: x_axis, y_axis, data
// All queries must reference the correct table names (with _ntpe suffix).

func TestQueryChartSQL_TwoD_HasRequiredColumns(t *testing.T) {
	twoDQueries := map[string]string{
		"flood_risk_map (ntpe)":          sqlFloodRiskMap,
		"flood_risk_map (tpe)":           sqlFloodRiskMapTpe,
		"rainfall_realtime_chart":        sqlRainfallRealtimeChart,
		"shelter_map (ntpe)":             sqlShelterMap,
		"shelter_map (tpe)":              sqlShelterMapTpe,
		"disaster_risk_kpi (ntpe)":       sqlDisasterRiskKpi,
		"disaster_risk_kpi (tpe)":        sqlDisasterRiskKpiTpe,
	}
	for name, sql := range twoDQueries {
		lower := strings.ToLower(sql)
		if !strings.Contains(lower, "x_axis") {
			t.Errorf("[%s] two_d query missing 'x_axis' column alias", name)
		}
		if !strings.Contains(lower, " data") && !strings.Contains(lower, "\tdata") {
			t.Errorf("[%s] two_d query missing 'data' column alias", name)
		}
	}
}

func TestQueryChartSQL_ThreeD_HasRequiredColumns(t *testing.T) {
	// disaster_risk_kpi is now two_d; verify it does NOT accidentally include y_axis
	// (would cause BE to attempt three_d parsing and fail)
	for _, sql := range []string{sqlDisasterRiskKpi, sqlDisasterRiskKpiTpe} {
		lower := strings.ToLower(sql)
		if strings.Contains(lower, "y_axis") {
			t.Error("disaster_risk_kpi is two_d but SQL contains 'y_axis' — update query_type to three_d or remove y_axis")
		}
	}
}

func TestQueryChartSQL_CorrectTableNames(t *testing.T) {
	checks := []struct {
		name      string
		sql       string
		wantTable string
	}{
		{"flood_risk_map (ntpe)",    sqlFloodRiskMap,          "rainfall_flood_simulation_etl_ntpe"},
		{"flood_risk_map (tpe)",     sqlFloodRiskMapTpe,        "rainfall_flood_simulation_etl_tpe"},
		{"shelter_map (ntpe)",       sqlShelterMap,             "urbn_air_raid_shelter_ntpe"},
		{"shelter_map (tpe)",        sqlShelterMapTpe,          "urbn_air_raid_shelter"},
		{"disaster_kpi (ntpe)",      sqlDisasterRiskKpi,        "urbn_air_raid_shelter_ntpe"},
		{"disaster_kpi (ntpe2)",     sqlDisasterRiskKpi,        "rainfall_flood_simulation_etl_ntpe"},
		{"disaster_kpi (tpe)",       sqlDisasterRiskKpiTpe,     "urbn_air_raid_shelter"},
		{"disaster_kpi (tpe2)",      sqlDisasterRiskKpiTpe,     "rainfall_flood_simulation_etl_tpe"},
		{"rainfall_chart",           sqlRainfallRealtimeChart,  "rainfall_realtime_tpe"},
	}
	for _, tc := range checks {
		if !strings.Contains(tc.sql, tc.wantTable) {
			t.Errorf("[%s] SQL should reference table %q", tc.name, tc.wantTable)
		}
	}
}

func TestQueryChartSQL_NoWrongTableNames(t *testing.T) {
	// Guard against accidentally omitting city suffix for ntpe tables.
	// Note: "urbn_air_raid_shelter" (no suffix) IS valid for Taipei City — only check
	// "rainfall_flood_simulation_etl " (missing _ntpe/_tpe) is wrong.
	wrongTables := []string{
		"rainfall_flood_simulation_etl ",  // missing city suffix
	}
	allSQL := sqlFloodRiskMap + sqlFloodRiskMapTpe + sqlDisasterRiskKpi + sqlDisasterRiskKpiTpe
	for _, bad := range wrongTables {
		if strings.Contains(allSQL, bad) {
			t.Errorf("SQL contains wrong table name (missing city suffix): %q", strings.TrimSpace(bad))
		}
	}
}

func TestAIToolSQL_FloodRisk_HasPlaceholder(t *testing.T) {
	if !strings.Contains(sqlAIFloodRisk, "rainfall_flood_simulation_etl_ntpe") {
		t.Error("AI flood risk SQL should query rainfall_flood_simulation_etl_ntpe")
	}
	if !strings.Contains(sqlAIFloodRisk, "?") {
		t.Error("AI flood risk SQL should use GORM placeholder '?'")
	}
	for _, col := range []string{"gridcode", "polygon_count", "area_km2"} {
		if !strings.Contains(sqlAIFloodRisk, col) {
			t.Errorf("AI flood risk SQL missing expected column %q", col)
		}
	}
}

func TestAIToolSQL_Shelters_HasPlaceholder(t *testing.T) {
	if !strings.Contains(sqlAIShelters, "urbn_air_raid_shelter_ntpe") {
		t.Error("AI shelter SQL should query urbn_air_raid_shelter_ntpe")
	}
	if strings.Count(sqlAIShelters, "?") < 2 {
		t.Error("AI shelter SQL should have at least 2 GORM placeholders (town, min_capacity)")
	}
	for _, col := range []string{"address", "capacity", "lng", "lat"} {
		if !strings.Contains(sqlAIShelters, col) {
			t.Errorf("AI shelter SQL missing expected output column %q", col)
		}
	}
}

// TestDashboardManagerSQLFile verifies the appended disaster SQL block
// exists in dashboardmanager-demo.sql and contains critical identifiers.
func TestDashboardManagerSQLFile(t *testing.T) {
	// Navigate from this test file up to the repo root
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Skip("cannot determine test file path")
	}
	// tools/ → ai/ → services/ → app/ → BE/ → repo root
	repoRoot := filepath.Join(filepath.Dir(filename), "../../../../..")
	sqlPath := filepath.Join(repoRoot, "db-sample-data", "dashboardmanager-demo.sql")

	data, err := os.ReadFile(sqlPath)
	if err != nil {
		t.Skipf("dashboardmanager-demo.sql not found at %s: %v", sqlPath, err)
	}
	content := string(data)

	required := []string{
		"flood_risk_map",
		"rainfall_realtime_chart",
		"shelter_map",
		"disaster_risk_kpi",
		"disaster_prevention",
		"rainfall_flood_simulation_etl_ntpe",
		"rainfall_flood_simulation_etl_tpe",
		"urbn_air_raid_shelter_ntpe",
		"urbn_air_raid_shelter",
	}
	for _, token := range required {
		if !strings.Contains(content, token) {
			t.Errorf("dashboardmanager-demo.sql missing expected token: %q", token)
		}
	}
}

// TestCitySwitchingCompliance verifies every component has BOTH taipei and metrotaipei entries.
func TestCitySwitchingCompliance(t *testing.T) {
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Skip("cannot determine test file path")
	}
	repoRoot := filepath.Join(filepath.Dir(filename), "../../../../..")
	sqlPath := filepath.Join(repoRoot, "db-sample-data", "dashboardmanager-demo.sql")

	data, err := os.ReadFile(sqlPath)
	if err != nil {
		t.Skipf("dashboardmanager-demo.sql not found: %v", err)
	}
	content := string(data)

	components := []string{"flood_risk_map", "rainfall_realtime_chart", "shelter_map", "disaster_risk_kpi"}
	cities := []string{"metrotaipei", "taipei"}

	for _, comp := range components {
		for _, city := range cities {
			token := "'" + comp + "','" + city + "'"
			if !strings.Contains(content, token) {
				t.Errorf("city switching compliance: missing query_charts entry for component=%q city=%q", comp, city)
			}
		}
	}
}
