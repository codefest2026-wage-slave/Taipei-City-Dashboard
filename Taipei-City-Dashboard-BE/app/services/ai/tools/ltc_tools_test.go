package tools

import (
	"context"
	"encoding/json"
	"testing"
)

// ── parseArgs helper tests ─────────────────────────────────

func TestParseArgs_LtcResource_Valid(t *testing.T) {
	raw := `{"district":"板橋區","service_type":"居家服務"}`
	var p LtcResourceArgs
	if err := parseArgs(raw, &p); err != nil {
		t.Fatalf("parseArgs failed: %v", err)
	}
	if p.District != "板橋區" {
		t.Errorf("district got %q, want 板橋區", p.District)
	}
	if p.ServiceType != "居家服務" {
		t.Errorf("service_type got %q, want 居家服務", p.ServiceType)
	}
}

func TestParseArgs_LtcResource_MissingServiceType(t *testing.T) {
	raw := `{"district":"三重區"}`
	var p LtcResourceArgs
	if err := parseArgs(raw, &p); err != nil {
		t.Fatalf("parseArgs failed: %v", err)
	}
	if p.ServiceType != "" {
		t.Errorf("service_type should be empty, got %q", p.ServiceType)
	}
}

func TestParseArgs_AgingStats_Valid(t *testing.T) {
	raw := `{"district":"永和區"}`
	var p AgingStatsArgs
	if err := parseArgs(raw, &p); err != nil {
		t.Fatalf("parseArgs failed: %v", err)
	}
	if p.District != "永和區" {
		t.Errorf("district got %q, want 永和區", p.District)
	}
}

func TestParseArgs_InvalidJSON(t *testing.T) {
	var p LtcResourceArgs
	if err := parseArgs(`{bad json}`, &p); err == nil {
		t.Error("expected error for invalid JSON, got nil")
	}
}

// ── Tool registry tests ────────────────────────────────────

func TestRegistry_LtcToolsRegistered(t *testing.T) {
	for _, name := range []string{"get_nearby_ltc_resources", "get_district_aging_stats"} {
		if _, ok := registry[name]; !ok {
			t.Errorf("tool %q not registered", name)
		}
	}
}

func TestExecute_UnknownTool(t *testing.T) {
	_, err := Execute(context.Background(), "non_existent_tool", "{}")
	if err == nil {
		t.Error("expected error for unknown tool, got nil")
	}
}

// ── Validation: empty district returns error ───────────────

func TestGetNearbyLtcResources_EmptyDistrict(t *testing.T) {
	_, err := GetNearbyLtcResources(context.Background(), `{"district":""}`)
	if err == nil {
		t.Error("expected error for empty district, got nil")
	}
}

func TestGetDistrictAgingStats_EmptyDistrict(t *testing.T) {
	_, err := GetDistrictAgingStats(context.Background(), `{"district":""}`)
	if err == nil {
		t.Error("expected error for empty district, got nil")
	}
}

// ── LtcToolsJSON: schema is valid JSON ────────────────────

func TestLtcToolsJSON_ValidJSON(t *testing.T) {
	s, err := LtcToolsJSON()
	if err != nil {
		t.Fatalf("LtcToolsJSON error: %v", err)
	}
	var out []map[string]interface{}
	if err := json.Unmarshal([]byte(s), &out); err != nil {
		t.Fatalf("LtcToolsJSON not valid JSON: %v", err)
	}
	if len(out) != 2 {
		t.Errorf("expected 2 tool definitions, got %d", len(out))
	}
}

func TestLtcToolsJSON_HasRequiredFields(t *testing.T) {
	s, _ := LtcToolsJSON()
	var out []map[string]interface{}
	_ = json.Unmarshal([]byte(s), &out)

	names := map[string]bool{}
	for _, tool := range out {
		name, _ := tool["name"].(string)
		names[name] = true
		if tool["description"] == nil {
			t.Errorf("tool %q missing description", name)
		}
		if tool["parameters"] == nil {
			t.Errorf("tool %q missing parameters", name)
		}
	}
	for _, expected := range []string{"get_nearby_ltc_resources", "get_district_aging_stats"} {
		if !names[expected] {
			t.Errorf("tool %q not found in schema", expected)
		}
	}
}
