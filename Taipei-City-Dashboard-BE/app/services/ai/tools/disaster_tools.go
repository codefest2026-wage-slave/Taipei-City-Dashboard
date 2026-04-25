package tools

import (
	"TaipeiCityDashboardBE/app/models"
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

// Depth level mapping for WRA flood simulation gridcodes
var floodDepthLabels = map[int]string{
	1: "0~30cm",
	2: "30~50cm",
	3: "50~100cm",
	4: "1~2m",
	5: "2m以上",
}

func init() {
	Register("get_flood_risk_by_district", GetFloodRiskByDistrict)
	Register("get_nearest_shelters", GetNearestShelters)
}

// FloodRiskArgs defines query parameters for flood risk lookup
type FloodRiskArgs struct {
	District string `json:"district"`
}

// ShelterArgs defines query parameters for shelter lookup
type ShelterArgs struct {
	District    string `json:"district"`
	MinCapacity int    `json:"min_capacity"`
}

// GetFloodRiskByDistrict queries flood simulation risk statistics for a district.
// It uses the rainfall_flood_simulation_etl_ntpe table from DBDashboard.
func GetFloodRiskByDistrict(ctx context.Context, args string) (string, error) {
	var params FloodRiskArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	params.District = strings.TrimSpace(params.District)
	if params.District == "" {
		return "", fmt.Errorf("district 參數不能為空，請提供行政區名稱，例如：板橋區、中正區")
	}

	type FloodRow struct {
		Gridcode     int     `gorm:"column:gridcode"`
		PolygonCount int64   `gorm:"column:polygon_count"`
		AreaKm2      float64 `gorm:"column:area_km2"`
	}

	var rows []FloodRow
	query := `
		SELECT
			gridcode,
			COUNT(*) AS polygon_count,
			ROUND(SUM(area)::numeric / 1000000, 2) AS area_km2
		FROM rainfall_flood_simulation_etl_ntpe
		WHERE city LIKE '%' || ? || '%'
		GROUP BY gridcode
		ORDER BY gridcode
	`
	if err := models.DBDashboard.Raw(query, params.District).Scan(&rows).Error; err != nil {
		return "", fmt.Errorf("查詢淹水潛勢資料失敗: %v", err)
	}

	if len(rows) == 0 {
		return fmt.Sprintf("查無「%s」的淹水潛勢資料，請確認行政區名稱（例如：板橋區、汐止區）", params.District), nil
	}

	// Calculate risk level based on high-risk (gridcode >= 3) area ratio
	var totalArea, highRiskArea float64
	for _, r := range rows {
		totalArea += r.AreaKm2
		if r.Gridcode >= 3 {
			highRiskArea += r.AreaKm2
		}
	}

	riskLevel := "低"
	ratio := 0.0
	if totalArea > 0 {
		ratio = highRiskArea / totalArea
	}
	switch {
	case ratio >= 0.3:
		riskLevel = "極高"
	case ratio >= 0.2:
		riskLevel = "高"
	case ratio >= 0.1:
		riskLevel = "中"
	}

	var sb strings.Builder
	fmt.Fprintf(&sb, "【%s 淹水潛勢分析】\n", params.District)
	fmt.Fprintf(&sb, "整體風險等級：%s（高風險面積佔比 %.1f%%）\n\n", riskLevel, ratio*100)
	fmt.Fprintf(&sb, "各深度等級分布：\n")
	for _, r := range rows {
		label := floodDepthLabels[r.Gridcode]
		if label == "" {
			label = fmt.Sprintf("等級%d", r.Gridcode)
		}
		fmt.Fprintf(&sb, "  • %s：約 %.2f km²（%d 個網格）\n", label, r.AreaKm2, r.PolygonCount)
	}

	result, _ := json.Marshal(map[string]interface{}{
		"district":        params.District,
		"risk_level":      riskLevel,
		"high_risk_ratio": ratio,
		"summary":         sb.String(),
		"rows":            rows,
	})
	return string(result), nil
}

// GetNearestShelters queries air-raid / disaster shelters in a given district.
// It uses the urbn_air_raid_shelter_ntpe table from DBDashboard.
func GetNearestShelters(ctx context.Context, args string) (string, error) {
	var params ShelterArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	params.District = strings.TrimSpace(params.District)
	if params.District == "" {
		return "", fmt.Errorf("district 參數不能為空，請提供行政區名稱，例如：板橋區")
	}
	if params.MinCapacity < 0 {
		params.MinCapacity = 0
	}

	type ShelterRow struct {
		Address  string  `gorm:"column:address"`
		Capacity int     `gorm:"column:capacity"`
		Lng      float64 `gorm:"column:lng"`
		Lat      float64 `gorm:"column:lat"`
	}

	var rows []ShelterRow
	query := `
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
	if err := models.DBDashboard.Raw(query, params.District, params.MinCapacity).Scan(&rows).Error; err != nil {
		return "", fmt.Errorf("查詢避難所資料失敗: %v", err)
	}

	if len(rows) == 0 {
		return fmt.Sprintf("查無「%s」符合條件（容量 ≥ %d 人）的避難所，請嘗試降低容量需求或確認行政區名稱。",
			params.District, params.MinCapacity), nil
	}

	var sb strings.Builder
	fmt.Fprintf(&sb, "【%s 避難場所清單（容量 ≥ %d 人）】\n", params.District, params.MinCapacity)
	for i, r := range rows {
		fmt.Fprintf(&sb, "%d. %s（容量 %d 人）\n", i+1, r.Address, r.Capacity)
	}
	fmt.Fprintf(&sb, "\n⚠️ 緊急救援：119 ｜ 市民服務：1999")

	result, _ := json.Marshal(map[string]interface{}{
		"district":     params.District,
		"min_capacity": params.MinCapacity,
		"count":        len(rows),
		"summary":      sb.String(),
		"shelters":     rows,
	})
	return string(result), nil
}
