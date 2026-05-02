# 食安監控系統 Dashboard 504 — 前端實作 Design Spec

> 來源題目：`.worktrees/idea/docs/proposals/feature_plan_food_safety.md`
> 範圍：前端為主、DB 採假資料 mock；新 dashboard 並存於既有 503「食安風險追蹤器」之上
> 目標：完整還原 feature_plan 5 個組件 + 雙地圖 demo 故事線

---

## 1. 專案目標

實作家長視角的「食安監控系統」dashboard，呈現 2 張地圖（校內供應鏈 / 校外餐廳）+ 3 個輔助組件（違規 Rank、稽查折線、風險矩陣），並串成 mockup 1/2/3 描繪的 demo 故事。

**範圍邊界**：
- 純前端實作 + 最小 BE seed（hardcoded VALUES 註冊 dashboard 504 + 5 個 component）
- 不建新表、不寫 ETL、不接真實資料源
- mock data 走 `Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/*` 靜態檔
- 不取代既有 503「食安風險追蹤器」，並存
- 雙北為硬性條件（CLAUDE.md），所有 chart 預設 `metrotaipei`，每個 component 註冊 `taipei` + `metrotaipei` 兩份 query_chart

---

## 2. 總體架構

```
Taipei City Dashboard
├── BE (manager DB) ── dashboard 504「食安監控系統」最小註冊
│                       ├── components: 1021-1025（避開 503 的 1011-1015）
│                       ├── component_charts: 5
│                       ├── component_maps: 4（fsm_schools / fsm_supply_chain / fsm_restaurants / fsm_district_heat）
│                       ├── query_charts: 10（5 components × 2 cities）
│                       └── dashboards.id=504, index='food_safety_monitor'
│
└── FE 三層
    ├── 圖表層（左 sidebar 標準 chart 組件）
    │   ├── 1023 違規食品類別排行 (BarChart)
    │   ├── 1024 稽查強度趨勢 (ColumnLineChart)
    │   └── 1025 風險矩陣 (RiskMatrixChart - 新)
    ├── 地圖層（中央 Mapbox，由 mapStore 管理）
    │   ├── 1021 校內食安地圖
    │   │   ├── fsm_schools (circle, 雙北 ~60 校)
    │   │   ├── fsm_supply_chain (deck.gl ArcLayer, 動態載入)
    │   │   └── 事件學校 red status filter
    │   └── 1022 校外食安地圖
    │       ├── fsm_district_heat (fill choropleth)
    │       └── fsm_restaurants (circle, 含稽查狀態)
    └── 懸浮面板層（FoodSafetyOverlays.vue）
        ├── foodSafetyStore (Pinia) 統一管 active layer / selection / mock data
        ├── 校內模式 panels (active 1021)
        │   ├── SchoolSearchBar
        │   ├── LayerToggle
        │   ├── SchoolAnalysisPanel
        │   └── RecentIncidentsStrip
        └── 校外模式 panels (active 1022)
            ├── RestaurantFilterBar
            ├── RestaurantInspectionPanel
            └── ExternalStatsStrip
```

**互斥規則**：1021 與 1022 toggle 互斥，由 `foodSafetyStore.activeLayer` 控制。
**懸浮面板掛載**：`MapView.vue` 條件式 `<FoodSafetyOverlays v-if="contentStore.currentDashboard.index==='food_safety_monitor'"/>`，僅進此 dashboard 時 mount，離開即 unmount。
**現有 layout 不改**：複用 MapView 的 `.map-charts` (左 sidebar 360px) + `<MapContainer/>` (中央 Mapbox) 結構；懸浮面板以 absolute position 疊在地圖區之上。

---

## 3. 檔案樹

### 3.1 新增

```
scripts/food_safety_monitor/                                  # 仿 503 的 scripts/food_safety/
├── README.md
├── apply.sh / rollback.sh / backup_db.sh
├── _db_env.sh                                                # copy from 503
├── .env.script.example                                       # copy from 503
└── migrations/
    ├── 001_seed_dashboard.up.sql                             # 註冊 504 + 5 components + 4 component_maps + 10 query_charts (hardcoded VALUES)
    └── 001_seed_dashboard.down.sql                           # 移除所有 504 相關 row

Taipei-City-Dashboard-FE/public/mockData/food_safety_monitor/
├── schools.geojson                                           # 雙北 ~60 國中小 Point
├── suppliers.geojson                                         # ~25 團膳供應商 Point
├── supply_chain.geojson                                      # school↔supplier LineString → ArcLayer
├── incidents.json                                            # 5-8 起食安事件 (含 AI 摘要、新聞連結)
├── district_heatmap.geojson                                  # 雙北 41 區 Polygon (含 density 屬性)
├── restaurants.geojson                                       # 雙北餐廳稽查點
└── restaurant_inspections.json                               # 餐廳稽查歷史 keyed by restaurant_id

Taipei-City-Dashboard-FE/src/store/
└── foodSafetyStore.js                                        # Pinia: activeLayer / selection / mock data cache / actions

Taipei-City-Dashboard-FE/src/dashboardComponent/components/
└── RiskMatrixChart.vue                                       # 新 chart：ApexCharts scatter 4 象限

Taipei-City-Dashboard-FE/src/dashboardComponent/assets/chart/
└── RiskMatrixChart.svg                                       # 新 chart 縮圖

Taipei-City-Dashboard-FE/src/components/foodSafety/
├── FoodSafetyOverlays.vue                                    # 主容器，conditional render 內含 7 個子面板
├── SchoolSearchBar.vue                                       # 頂部 (校內)
├── LayerToggle.vue                                           # 左下 (校內)
├── SchoolAnalysisPanel.vue                                   # 右側 (校內) — school/supplier/incident 三視角覆蓋式
├── RecentIncidentsStrip.vue                                  # 底部 (校內)
├── RestaurantFilterBar.vue                                   # 頂部 (校外)
├── RestaurantInspectionPanel.vue                             # 右側 (校外)
└── ExternalStatsStrip.vue                                    # 底部 (校外)

docs/superpowers/specs/
└── 2026-05-02-food-safety-monitor-design.md                  # 本檔
```

### 3.2 修改

| 檔案 | 改動 |
|---|---|
| `Taipei-City-Dashboard-FE/src/dashboardComponent/utilities/chartTypes.js` | 註冊 `RiskMatrixChart` + svg |
| `Taipei-City-Dashboard-FE/src/dashboardComponent/DashboardComponent.vue` | import + dispatch RiskMatrixChart |
| `Taipei-City-Dashboard-FE/src/views/MapView.vue` | 尾段 conditional mount `<FoodSafetyOverlays/>` |

### 3.3 不動

- BE 程式（manager DB seed 之外完全不動）
- 既有 503 dashboard + 其 ETL（並存）
- 通用 `mapStore`（複用既有 `addArcMapLayer` / `addGeojsonSource` / `addMapLayer` API）
- 通用 `MapContainer.vue`（toolbar 不動）

---

## 4. 資料 Schema

### 4.1 BE seed migration (`001_seed_dashboard.up.sql`)

依 503 同模式，但無新表，全部 hardcoded VALUES：

```sql
BEGIN;

DELETE FROM query_charts   WHERE index LIKE 'fsm_%';
DELETE FROM component_maps WHERE index LIKE 'fsm_%';
DELETE FROM component_charts WHERE index LIKE 'fsm_%';
DELETE FROM components WHERE id BETWEEN 1021 AND 1025;

INSERT INTO components (id, index, name) VALUES
  (1021, 'fsm_school_map',         '校內食安地圖'),
  (1022, 'fsm_restaurant_map',     '校外食安地圖'),
  (1023, 'fsm_violation_rank',     '違規食品類別排行'),
  (1024, 'fsm_inspection_trend',   '稽查強度趨勢'),
  (1025, 'fsm_risk_matrix',        '風險矩陣');

INSERT INTO component_charts (index, color, types, unit) VALUES
  ('fsm_school_map',       ARRAY['#43A047','#E53935','#FFA000'], ARRAY['MapLegend'],         '校'),
  ('fsm_restaurant_map',   ARRAY['#1565C0','#FFA000','#E53935'], ARRAY['MapLegend'],         '家'),
  ('fsm_violation_rank',   ARRAY['#E53935','#FFA000','#43A047','#1565C0','#8E24AA','#26C6DA','#9E9E9E'], ARRAY['BarChart'], '件'),
  ('fsm_inspection_trend', ARRAY['#1565C0','#E53935'],            ARRAY['ColumnLineChart'],   '件/%'),
  ('fsm_risk_matrix',      ARRAY['#E53935','#FF9800','#1565C0','#43A047'], ARRAY['RiskMatrixChart'], '家');

INSERT INTO component_maps (index, title, type, source, size, paint) VALUES
  ('fsm_schools',       '學校節點',       'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","incident_status"],"red","#E53935","yellow","#FFA000","#43A047"],"circle-radius":6,"circle-opacity":0.85}'::json),
  ('fsm_supply_chain',  '供應鏈連線',     'arc',    'geojson', 'big',
    '{"arc-color":["#FFA000","#E53935"],"arc-width":2,"arc-opacity":0.6,"arc-animate":true}'::json),
  ('fsm_restaurants',   '餐廳稽查點',     'circle', 'geojson', 'big',
    '{"circle-color":["match",["get","grade"],"優","#43A047","良","#FFA000","#E53935"],"circle-radius":4,"circle-opacity":0.8}'::json),
  ('fsm_district_heat', '行政區違規密度', 'fill',   'geojson', 'big',
    '{"fill-color":["interpolate",["linear"],["get","density"],0,"#43A047",50,"#FFA000",100,"#E53935"],"fill-opacity":0.5}'::json);

-- 10 條 query_charts (5 components × 2 cities)
-- ... 詳見實作（每條為 hardcoded VALUES）

INSERT INTO dashboards (id, index, name, components, icon, created_at, updated_at) VALUES
  (504, 'food_safety_monitor', '食安監控系統',
   ARRAY[1021,1022,1023,1024,1025], 'health_and_safety', NOW(), NOW())
ON CONFLICT (index) DO NOTHING;

INSERT INTO dashboard_groups (dashboard_id, group_id) VALUES
  (504, 2), (504, 3)
ON CONFLICT DO NOTHING;

COMMIT;
```

**風險矩陣 query_chart shape**（採 `two_d` 預分群）：
```sql
$$SELECT * FROM (VALUES
  ('高危險店家', 12), ('新興風險', 8), ('改善中', 15), ('優良店家', 65)
) AS t(x_axis, data) ORDER BY data DESC$$
```
RiskMatrixChart.vue 接到這個 shape 後，依 `x_axis` 字串配對到 4 象限座標（hardcoded 對應），`data` 表象限店家數量。每個象限內以 `count` 個 jitter 點散佈呈現視覺密度（仿 mockup 3 右下散佈點群）。

**散佈點 detail（具體店家名）**：不另外建檔，直接從 `restaurants.geojson` features 補一個 `risk_quadrant` 屬性（`'high_risk' | 'emerging' | 'improving' | 'good'`），點擊象限時 filter `restaurants` array 取對應店家名 list。

> 註：本決策在 §6.1 R5 中拍板採方案 (a) two_d 預分群，因「四象限歸屬邏輯（新興風險 = 一年內違規 ∩ 一年前無違規）」寫在 SQL VALUES 比 FE 三維分群直觀。

### 4.2 mockData 檔案

#### `schools.geojson`
```jsonc
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {
      "id": "TPE-XX-001",
      "name": "臺北市信義國小",
      "city": "臺北市",
      "district": "信義區",
      "type": "elementary",            // elementary | junior_high
      "incident_status": "red",        // red | yellow | green
      "incident_count": 2,
      "supplier_ids": ["SUP-001","SUP-005"]
    },
    "geometry": { "type": "Point", "coordinates": [121.567, 25.033] }
  }]
}
```

#### `suppliers.geojson`
```jsonc
{ "features": [{
  "properties": {
    "id": "SUP-001",
    "name": "大樹團膳企業",
    "address": "新北市板橋區...",
    "city": "新北市",
    "hazard_level": "Critical",        // Critical | High | Medium | Low
    "last_inspection": "2025-08-12",
    "last_status": "未通過",
    "served_school_ids": ["TPE-XX-001","TPE-XX-007","NTPC-XX-003"]
  },
  "geometry": { "type": "Point", "coordinates": [121.46, 25.01] }
}]}
```

#### `supply_chain.geojson` (LineString → deck.gl ArcLayer)
```jsonc
{ "features": [{
  "properties": {
    "school_id": "TPE-XX-001",
    "supplier_id": "SUP-001",
    "risk": "high"                     // high | medium | low → 影響 arc 顏色
  },
  "geometry": { "type": "LineString", "coordinates": [[121.567,25.033],[121.46,25.01]] }
}]}
```

#### `incidents.json` (5-8 起 mock 事件)
```jsonc
[{
  "id": "INC-2025-09-15",
  "occurred_at": "2025-09-15",
  "severity": "Critical",
  "school_id": "TPE-XX-001",
  "school_name": "臺北市信義國小",
  "supplier_id": "SUP-001",
  "title": "信義國小午餐 15 人食物中毒",
  "deaths": 0, "injured": 15, "hospitalized": 4,
  "confirmed_food": "雞肉飯",
  "suspected_food": "雞肉飯 / 高麗菜",
  "ai_summary": "板橋圍小近三年共 4 起食安事件...（mock）",
  "news_links": [
    { "title": "聯合新聞網報導", "url": "https://example.com/news/1" }
  ],
  "affected_school_ids": ["TPE-XX-001","TPE-XX-007"]
}]
```

#### `district_heatmap.geojson`
> 從 `Taipei-City-Dashboard-FE/public/mapData/metrotaipei_town.geojson` 取雙北 41 區 Polygon，每區隨機 mock `density: 0-100` 屬性。

#### `restaurants.geojson`
> 借用 503 現有 `food_restaurant_tpe.geojson`，加 ~200 點新北 mock，每筆 features.properties 含：
> - `grade: '優' | '良' | '需改善'`
> - `risk_quadrant: 'high_risk' | 'emerging' | 'improving' | 'good'`（用於 RiskMatrixChart 點擊象限後 lazy filter，§4.1 註）
> - `district`、`city`（雙北 filter 用）
> - `severity: 'high' | 'medium' | 'low'`（restaurantFilters severity 用）

#### `restaurant_inspections.json`
```jsonc
{
  "RES-001": {
    "name": "信佳小館（信義店）",
    "history": [
      { "date": "2025/04/12", "status": "FAIL", "issue": "餐具大腸桿菌超標" },
      { "date": "2024/11/05", "status": "PASS" }
    ]
  }
}
```

### 4.3 `foodSafetyStore` (Pinia) state

```js
state: () => ({
  activeLayer: null,                  // 'school' | 'restaurant' | null
  layerToggles: {
    showSupplyChain: false,
    showIncidentSchools: true
  },

  // selection (覆蓋式單一 focus，§6.1 R6)
  analysisFocus: null,                // { type: 'school'|'supplier'|'incident', payload }
  selectedRestaurant: null,

  schoolSearchQuery: '',
  restaurantFilters: {
    district: 'all',
    severity: 'all',
    timeRange: '1y'
  },

  // mock data (進 dashboard 504 並行預載，§6.2 D3)
  schools: [],
  suppliers: [],
  supplyChain: [],
  incidents: [],
  restaurants: [],
  restaurantInspections: {},

  loading: { schools: false, suppliers: false, restaurants: false }
}),
actions: {
  async loadAllMockData() { /* parallel fetch all 7 mock files */ },
  setActiveLayer(layer) { /* 互斥 toggle, dispatch mapStore add/remove */ },
  setAnalysisFocus(type, payload) { /* 覆蓋式 */ },
  redrawSupplyArcs(filteredFeatures) { /* removeMapLayer + AddArcMapLayer */ },
  selectSchool(school) { /* setAnalysisFocus + supplyArcs + ease */ },
  selectSupplier(supplier) { /* setAnalysisFocus + supplier→served arcs */ },
  selectIncident(incident) { /* setAnalysisFocus + impact range arcs + fitBounds */ },
  selectRestaurant(restaurant) { ... },
  $reset() { /* clear selection + remove all fsm_* mapStore layers */ }
}
```

---

## 5. 互動流程

### 5.1 進入 dashboard 504

```
sidebar 點「食安監控系統」 → contentStore.changeCurrentDashboard(504)
  → http.get('/dashboard/') 拿 504 + 5 component meta
  → 路由 /mapview?index=food_safety_monitor&city=metrotaipei
  → MapView mount → mapStore.initializeMapBox()
  → contentStore.currentDashboard.index === 'food_safety_monitor' 觸發
    <FoodSafetyOverlays/> conditional mount
  → foodSafetyStore.loadAllMockData() (並行預載，§6.2 D3)
  → sidebar 顯示 5 chart 組件，地圖 layer 預設關，懸浮面板隱藏
```

### 5.2 校內地圖（互斥開啟）

```
sidebar「校內食安地圖」toggle 開
  → DashboardComponent emits('toggle', true, map_config)
  → MapView.handleToggle 攔截 → foodSafetyStore.setActiveLayer('school')
  → mapStore.removeMapLayer(fsm_restaurants, fsm_district_heat) (若 active)
  → mapStore.addMapLayer(fsm_schools)（雙北 ~60 校 circle）
  → 不主動載 supply_chain / suppliers，等使用者觸發
  → <FoodSafetyOverlays> 渲染 4 個校內懸浮面板：
     - SchoolSearchBar (top-center, 320px)
     - LayerToggle (bottom-left)
     - SchoolAnalysisPanel (top-right, 380px)
     - RecentIncidentsStrip (bottom-center, 橫向 scroll)
```

#### 5.2.1 路徑 1：家長視角（school → suppliers → other schools）

```
SchoolSearchBar 輸入「信義國小」 → schoolSearchQuery 更新 → 自動完成下拉
  → 點選結果 → foodSafetyStore.selectSchool(school)
  → mapStore.easeToLocation([coords, 14, 0, 0]) + circle highlight ring
  → SchoolAnalysisPanel 顯示：學校名 / 危害等級 / 歷史事件 list / AI 摘要 / 新聞連結

若 layerToggles.showSupplyChain = true:
  → supply_chain.geojson filter school_id === selected.id
  → mapStore.AddArcMapLayer(filtered)（學校 → 所有供應商，arc 顏色依 risk）

點地圖上 supplier circle:
  → layer-scoped click handler (§6.1 R1) → foodSafetyStore.selectSupplier(supplier)
  → SchoolAnalysisPanel 切換到「供應商檢視」：
     稽查記錄 / 危害等級 badge / 改善狀態 / served_school_ids 列表 (可點選跳回 school)
  → mapStore 重繪 ArcLayer：supplier 為 source，所有 served schools 為 target
```

#### 5.2.2 路徑 2：新聞視角（incident → impact range）

```
點 RecentIncidentsStrip 某張事件卡 → foodSafetyStore.selectIncident(incident)
  → 學校 layer filter 高亮 incident.affected_school_ids（黃色 ring）
  → AddArcMapLayer 拉 supplier → affected schools (全紅 arc)
  → easeToLocation fit bounds 涵蓋所有受影響學校
  → SchoolAnalysisPanel 切到「事件檢視」：
     title / occurred_at / severity / 死亡/受傷/住院 / confirmed_food / suspected_food / ai_summary / news_links
```

#### 5.2.3 LayerToggle 子開關

| Toggle | 行為 |
|---|---|
| 顯示供應鏈 | 開：載入 selected school 的 supply_chain arcs；關：清掉 arcs |
| 顯示事件學校 | 開：incident_status === 'red' 學校 circle 變紅 + 放大；關：所有學校統一綠 |

### 5.3 校外地圖

```
sidebar「校外食安地圖」toggle 開 → setActiveLayer('restaurant')
  → mapStore.removeMapLayer(fsm_schools, fsm_supply_chain)
  → mapStore.addMapLayer(fsm_district_heat)（41 區 fill choropleth, beforeId 插在區界 label 之下，§6.1 R4）
  → mapStore.addMapLayer(fsm_restaurants)
  → <FoodSafetyOverlays> 切換 3 個校外面板：
     - RestaurantFilterBar (top-center) — 區域 / 違規程度 / 時間區間 dropdown
     - RestaurantInspectionPanel (top-right, 320px) — 預設隱藏
     - ExternalStatsStrip (bottom) — 4 張統計卡 + 違規類別 Top 5 mini DonutChart

點 restaurant circle → selectRestaurant → RestaurantInspectionPanel 顯示：
  餐廳名 / 地址 / grade / 稽查歷史 timeline / 「查看詳細稽查記錄」

RestaurantFilterBar 變動 → restaurantFilters 更新 → mapStore filter expression
```

### 5.4 離開 dashboard 504

```
切到別的 dashboard → MapView 路由 unmount
  → <FoodSafetyOverlays> unmount → onUnmounted hooks
  → foodSafetyStore.$reset() (清 selection + 顯式 removeMapLayer fsm_* 防呆，§6.1 R3)
```

### 5.5 Dual-city 切換（雙北硬性條件）

```
頂部 city tag 切「臺北 / 雙北 / 新北」 → contentStore.setComponentData
  → sidebar charts 重拉對應 city query_chart (BE 已備雙版)
  → 地圖 layer 不重載，僅更新 mapStore filter expression：
     'metrotaipei' → 不 filter
     'taipei'      → ['==', ['get','city'], '臺北市']
     'ntpc'        → ['==', ['get','city'], '新北市']
```

---

## 6. 風險與決策紀錄

### 6.1 已採納的對策（implementation 須遵守）

| 風險 | 對策 |
|---|---|
| **R1** mapStore.click 全域 handler | 用 `mapStore.map.on('click', layer_id, handler)` layer-scoped 綁定，不污染既有全域 popup |
| **R2** ArcLayer 動態 data 需重建 layer | 封裝為 `foodSafetyStore.redrawSupplyArcs(filteredFeatures)` action |
| **R3** 離開 dashboard 後 fsm_* layer 清除 | `foodSafetyStore.$reset` 顯式 `removeMapLayer` per fsm 層作雙保險 |
| **R4** district_heat z-index 衝突 | `addMapLayer` 用 `beforeId` 插在 metrotaipei_town label 之下、village 之上 |
| **R5** 風險矩陣 query_chart shape | 採 `two_d` 預分群（4 象限名稱 + 店家數）；FE RiskMatrixChart 自行對應到象限座標 |
| **R6** SchoolAnalysisPanel 多視角 | `analysisFocus` 單欄位覆蓋式（school/supplier/incident），不維持 tab 並行 |

### 6.2 已拍板的決策

| ID | 決策 |
|---|---|
| **D1** 校內搜尋只搜學校（不含供應商，對齊 mockup）|
| **D2** RecentIncidentsStrip 預設 5 起 + 橫向 scroll 顯示其餘 |
| **D3** 進 dashboard 504 並行預載 schools + restaurants 全部 mock data |
| **D4** mock data 採半真實（學校用真實雙北國中小名單抽取，事件 / 違規 / 供應商虛構但合理）|
| **D5** Mobile 不支援，顯示「請使用桌機」hint，不污染既有 mobile 邏輯 |
| **D6** 不寫測試（hackathon scope，重 demo 體驗）|

---

## 7. Out of Scope

明確不在本次實作的：
- 真實資料源（新聞爬蟲、政府 API、LLM 抽 tag、AI 摘要產生 pipeline）
- ETL 程式 / 新建 DB 表
- 取代或合併既有 503「食安風險追蹤器」
- Mobile responsive（採 D5）
- 自動化測試（採 D6）
- Network graph 進階互動（force-directed layout、節點拖拉、群集分析）—— 僅做 ArcLayer 連線
- AI Summary 真實產生 —— mock 為靜態文字
- 多語言（中文 only）
- WebSocket / 即時更新

---

## 8. 開發順序建議（給後續 implementation plan 參考）

> 本節僅為粗略順序，詳細 step-by-step plan 將由 writing-plans skill 後續產出。

```
1. BE seed migration (無新表)              → verify: dashboard 504 可在 sidebar 看到
2. Mock data 檔案產生（雙北合理範例）       → verify: 7 個檔可正常 fetch
3. foodSafetyStore Pinia store              → verify: state + actions 單元行為
4. RiskMatrixChart.vue + chartTypes 註冊    → verify: 1025 sidebar 可渲染
5. FoodSafetyOverlays 殼 + conditional mount → verify: 進 504 顯示空殼，離開消失
6. 校內 4 面板（含 SchoolAnalysisPanel 三視角覆蓋） → verify: mockup 1 對齊
7. 校內地圖 layer + ArcLayer 動態繪製       → verify: 路徑 1 + 路徑 2 完整跑通
8. 校外 3 面板                              → verify: mockup 2 對齊
9. 校外地圖 layer + 區界 z-index            → verify: 點 restaurant 看 popup
10. 互斥 toggle + city 切換 filter expression → verify: 雙北切換不需重載 GeoJSON
11. End-to-end 手動 demo 走完整故事線        → verify: 對齊 feature_plan §「完整 Demo 故事線」六步
```

---

## 9. Glossary

| 名詞 | 定義 |
|---|---|
| **dashboard 504** | 本 spec 定義的新 dashboard，index `food_safety_monitor`，與既有 503「食安風險追蹤器」並存 |
| **fsm_** | "Food Safety Monitor" 的 prefix，所有 504 相關 component_maps / query_charts / migration row 都用此 prefix |
| **互斥 toggle** | 1021 校內地圖 與 1022 校外地圖 同一時間僅一個可開啟 |
| **覆蓋式單一 focus** | SchoolAnalysisPanel 的視角切換不維持 tab 狀態，後 click 覆蓋前 click |
| **半真實 mock data** | 真實雙北學校名單 + 虛構但合理的事件 / 違規 / 供應商資料 |
| **layer-scoped click** | 用 `mapStore.map.on('click', layer_id, handler)` 綁特定圖層的 click event，不走全域 popup |
