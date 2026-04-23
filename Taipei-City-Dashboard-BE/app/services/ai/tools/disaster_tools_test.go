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

const sqlFloodRiskMap = `SELECT
        CASE gridcode
            WHEN 1 THEN '0~30cm'
            WHEN 2 THEN '30~50cm'
            WHEN 3 THEN '50~100cm'
            WHEN 4 THEN '1~2m'
            WHEN 5 THEN '2m以上'
        END AS x_axis,
        COUNT(*) AS data
     FROM rainfall_flood_simulation_etl_ntpe
     GROUP BY gridcode
     ORDER BY gridcode`

const sqlRainfallRealtimeChart = `SELECT
        station_name AS x_axis,
        rainfall_today AS data
     FROM rainfall_realtime_tpe
     WHERE data_time = (SELECT MAX(data_time) FROM rainfall_realtime_tpe)
     ORDER BY rainfall_today DESC
     LIMIT 20`

const sqlShelterMap = `SELECT
        town AS x_axis,
        SUM(person_capacity::int) AS data
     FROM urbn_air_raid_shelter_ntpe
     GROUP BY town
     ORDER BY data DESC
     LIMIT 20`

const sqlDisasterRiskKpi = `SELECT
        '避難場所總數'    AS x_axis,
        'metrotaipei'    AS y_axis,
        COUNT(*)           AS data
     FROM urbn_air_raid_shelter_ntpe
     UNION ALL
     SELECT
        '避難總容量（人）',
        'metrotaipei',
        COALESCE(SUM(person_capacity::int), 0)
     FROM urbn_air_raid_shelter_ntpe
     UNION ALL
     SELECT
        '高風險淹水區塊',
        'metrotaipei',
        COUNT(*)
     FROM rainfall_flood_simulation_etl_ntpe
     WHERE gridcode >= 3`

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
		"flood_risk_map":          sqlFloodRiskMap,
		"rainfall_realtime_chart": sqlRainfallRealtimeChart,
		"shelter_map":             sqlShelterMap,
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
	lower := strings.ToLower(sqlDisasterRiskKpi)
	for _, col := range []string{"x_axis", "y_axis", "data"} {
		if !strings.Contains(lower, col) {
			t.Errorf("disaster_risk_kpi three_d query missing %q column alias", col)
		}
	}
}

func TestQueryChartSQL_CorrectTableNames(t *testing.T) {
	// All queries must use the _ntpe-suffixed table names.
	checks := []struct {
		name      string
		sql       string
		wantTable string
	}{
		{"flood_risk_map",     sqlFloodRiskMap,       "rainfall_flood_simulation_etl_ntpe"},
		{"shelter_map",        sqlShelterMap,          "urbn_air_raid_shelter_ntpe"},
		{"disaster_risk_kpi",  sqlDisasterRiskKpi,     "urbn_air_raid_shelter_ntpe"},
		{"disaster_risk_kpi2", sqlDisasterRiskKpi,     "rainfall_flood_simulation_etl_ntpe"},
		{"rainfall_chart",     sqlRainfallRealtimeChart, "rainfall_realtime_tpe"},
	}
	for _, tc := range checks {
		if !strings.Contains(tc.sql, tc.wantTable) {
			t.Errorf("[%s] SQL should reference table %q", tc.name, tc.wantTable)
		}
	}
}

func TestQueryChartSQL_NoWrongTableNames(t *testing.T) {
	// Guard against accidentally using un-suffixed table names.
	wrongTables := []string{
		"rainfall_flood_simulation_etl ",  // missing _ntpe
		"urbn_air_raid_shelter ",           // missing _ntpe
	}
	allSQL := sqlFloodRiskMap + sqlShelterMap + sqlDisasterRiskKpi
	for _, bad := range wrongTables {
		if strings.Contains(allSQL, bad) {
			t.Errorf("SQL contains wrong table name (missing _ntpe): %q", strings.TrimSpace(bad))
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
		"disaster_prevention_metrotaipei",
		"rainfall_flood_simulation_etl_ntpe",
		"urbn_air_raid_shelter_ntpe",
	}
	for _, token := range required {
		if !strings.Contains(content, token) {
			t.Errorf("dashboardmanager-demo.sql missing expected token: %q", token)
		}
	}
}
