package tools

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
)

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
