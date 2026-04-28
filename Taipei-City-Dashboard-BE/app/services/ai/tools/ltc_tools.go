package tools

// SPDX-License-Identifier: AGPL-3.0-or-later

import (
	"TaipeiCityDashboardBE/app/models"
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

func init() {
	Register("get_nearby_ltc_resources", GetNearbyLtcResources)
	Register("get_district_aging_stats", GetDistrictAgingStats)
}

// LtcResourceArgs defines arguments for get_nearby_ltc_resources
type LtcResourceArgs struct {
	District    string `json:"district"`
	ServiceType string `json:"service_type"`
}

// LtcResourceResult holds a single long-term care facility record
type LtcResourceResult struct {
	PlaceName   string  `gorm:"column:place_name"`
	ServiceItem string  `gorm:"column:service_item"`
	Address     string  `gorm:"column:address"`
	Tel         string  `gorm:"column:tel"`
	Lng         float64 `gorm:"column:lng"`
	Lat         float64 `gorm:"column:lat"`
}

// GetNearbyLtcResources queries long-term care facilities in the given district.
// Tool schema:
//
//	{
//	  "name": "get_nearby_ltc_resources",
//	  "description": "查詢指定行政區附近的長照資源，包括居家服務、日間照顧、住宿機構等。",
//	  "parameters": {
//	    "type": "object",
//	    "properties": {
//	      "district": {"type": "string", "description": "行政區名稱，例如：板橋區、中正區"},
//	      "service_type": {
//	        "type": "string",
//	        "enum": ["all", "居家服務", "日間照顧", "住宿式機構"],
//	        "description": "長照服務類型，預設 all"
//	      }
//	    },
//	    "required": ["district"]
//	  }
//	}
func GetNearbyLtcResources(ctx context.Context, args string) (string, error) {
	var params LtcResourceArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	if params.District == "" {
		return "", fmt.Errorf("district is required")
	}

	db := models.DBDashboard.WithContext(ctx).Table("long_term_nwtpe").
		Select("place_name, service_item, address, tel, ROUND(lng::numeric, 4) as lng, ROUND(lat::numeric, 4) as lat").
		Where("zone = ?", params.District)

	if params.ServiceType != "" && params.ServiceType != "all" {
		db = db.Where("service_item LIKE ?", "%"+params.ServiceType+"%")
	}

	var results []LtcResourceResult
	if err := db.Order("place_name").Limit(20).Scan(&results).Error; err != nil {
		return "", fmt.Errorf("查詢長照資源失敗: %v", err)
	}

	if len(results) == 0 {
		return fmt.Sprintf("在 %s 目前查無符合條件的長照機構資料。建議撥打 1966 長照專線詢問。", params.District), nil
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("【%s 長照資源查詢結果】共 %d 間\n\n", params.District, len(results)))
	for i, r := range results {
		sb.WriteString(fmt.Sprintf("%d. %s\n   服務項目：%s\n   地址：%s\n   電話：%s\n\n",
			i+1, r.PlaceName, r.ServiceItem, r.Address, r.Tel))
	}
	sb.WriteString("如需更多資訊，請撥打 1966 長照專線。")
	return sb.String(), nil
}

// AgingStatsArgs defines arguments for get_district_aging_stats
type AgingStatsArgs struct {
	District string `json:"district"`
}

// AgingStatsResult holds aging statistics for a district
type AgingStatsResult struct {
	District          string  `gorm:"column:district"`
	City              string  `gorm:"column:city"`
	AgingRatio        float64 `gorm:"column:aging_ratio"`
	LtcCount          int     `gorm:"column:ltc_count"`
	LtcDensityPer10k  float64 `gorm:"column:ltc_density_per_10k"`
	DesertScore       float64 `gorm:"column:desert_score"`
	ElderlyPop        int     `gorm:"column:elderly_pop"`
	TotalPop          int     `gorm:"column:total_pop"`
}

// GetDistrictAgingStats queries aging statistics for a district from ltc_desert_index view.
// Tool schema:
//
//	{
//	  "name": "get_district_aging_stats",
//	  "description": "取得指定行政區的高齡化統計數據，包括老化比例、照護沙漠分數、長照機構數。",
//	  "parameters": {
//	    "type": "object",
//	    "properties": {
//	      "district": {"type": "string", "description": "行政區名稱，例如：板橋區、永和區"}
//	    },
//	    "required": ["district"]
//	  }
//	}
func GetDistrictAgingStats(ctx context.Context, args string) (string, error) {
	var params AgingStatsArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	if params.District == "" {
		return "", fmt.Errorf("district is required")
	}

	var result AgingStatsResult
	err := models.DBDashboard.WithContext(ctx).
		Table("ltc_desert_index").
		Where("district = ?", params.District).
		First(&result).Error

	if err != nil {
		return fmt.Sprintf("查無 %s 的高齡化統計資料。請確認行政區名稱（需包含「區」，例如：板橋區）。", params.District), nil
	}

	// Determine resource adequacy
	adequacy := "充足"
	if result.LtcDensityPer10k < 0.5 {
		adequacy = "不足（建議優先投入資源）"
	} else if result.LtcDensityPer10k < 1.0 {
		adequacy = "略顯不足"
	}

	return fmt.Sprintf(
		"【%s 高齡化統計】\n"+
			"- 總人口：%d 人\n"+
			"- 65歲以上人口：%d 人\n"+
			"- 高齡化比例：%.1f%%\n"+
			"- 長照機構數：%d 間\n"+
			"- 長照密度：%.2f 間／萬人（%s）\n"+
			"- 照護沙漠指數：%.2f（越高代表資源越缺乏）\n",
		result.District,
		result.TotalPop,
		result.ElderlyPop,
		result.AgingRatio,
		result.LtcCount,
		result.LtcDensityPer10k, adequacy,
		result.DesertScore,
	), nil
}

// ltcToolsMetadata returns the tool definitions for LLM consumption (for reference/documentation)
func ltcToolsMetadata() []map[string]interface{} {
	return []map[string]interface{}{
		{
			"name":        "get_nearby_ltc_resources",
			"description": "查詢指定行政區附近的長照資源，包括居家服務、日間照顧、住宿機構等。",
			"parameters": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"district": map[string]interface{}{
						"type":        "string",
						"description": "行政區名稱，例如：板橋區、中正區",
					},
					"service_type": map[string]interface{}{
						"type":        "string",
						"enum":        []string{"all", "居家服務", "日間照顧", "住宿式機構"},
						"description": "長照服務類型，預設 all",
					},
				},
				"required": []string{"district"},
			},
		},
		{
			"name":        "get_district_aging_stats",
			"description": "取得指定行政區的高齡化統計數據，包括老化比例、照護沙漠分數、長照機構數。",
			"parameters": map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"district": map[string]interface{}{
						"type":        "string",
						"description": "行政區名稱，例如：板橋區、永和區",
					},
				},
				"required": []string{"district"},
			},
		},
	}
}

// LtcToolsJSON returns the JSON-encoded tool definitions for LLM API consumption
func LtcToolsJSON() (string, error) {
	b, err := json.Marshal(ltcToolsMetadata())
	if err != nil {
		return "", err
	}
	return string(b), nil
}
