# Taipei City Dashboard — Codebase 完整分析報告

**日期：** 2026-04-13
**版本：** 2.2.0
**分析範圍：** 完整 monorepo（BE / FE / DE / docker / helm-chart）

---

## 目錄

1. [專案概述](#1-專案概述)
2. [整體架構](#2-整體架構)
3. [技術棧總覽](#3-技術棧總覽)
4. [後端分析（Go/Gin）](#4-後端分析-gogin)
5. [前端分析（Vue 3）](#5-前端分析-vue-3)
6. [資料工程分析（Airflow）](#6-資料工程分析-airflow)
7. [資料庫 Schema](#7-資料庫-schema)
8. [Docker 與部署設定](#8-docker-與部署設定)
9. [Kubernetes / Helm 部署](#9-kubernetes--helm-部署)
10. [安全與認證](#10-安全與認證)
11. [AI 功能整合](#11-ai-功能整合)
12. [效能最佳化](#12-效能最佳化)
13. [已知限制與未完成功能](#13-已知限制與未完成功能)
14. [專案統計](#14-專案統計)
15. [改善建議](#15-改善建議)

---

## 1. 專案概述

Taipei City Dashboard 是由台北市資料治理委員會（TUIC）開發的**開源都市智慧儀表板平台**，提供台北市各類公共數據的即時視覺化。功能涵蓋：

- 互動式地理資訊地圖（Mapbox GL + Deck.gl）
- 多樣化統計圖表（25+ 圖表類型）
- AI 對話查詢（TWCC 台灣 AI 雲端 + 向量語意搜尋）
- 多城市支援（台北市、新北市）
- 管理後台（使用者、元件、儀表板管理）
- 嵌入式 Widget 供外部網站使用

**Repository 根目錄結構：**

```
Taipei-City-Dashboard/
├── Taipei-City-Dashboard-BE/   # Go 後端 API
├── Taipei-City-Dashboard-FE/   # Vue 3 前端
├── Taipei-City-Dashboard-DE/   # Airflow 資料工程
├── db-sample-data/             # PostgreSQL 示範資料
├── docker/                     # Docker Compose 設定
├── helm-chart/                 # Kubernetes Helm Chart
├── LICENSE
└── README.md
```

---

## 2. 整體架構

```
┌─────────────────────────────────────────────────────────────────┐
│                        使用者 (Browser)                          │
└─────────────────────────────────────────┬───────────────────────┘
                                          │ HTTPS
                                          ▼
                              ┌───────────────────┐
                              │    Nginx (Proxy)   │
                              └──────┬─────────────┘
                    ┌────────────────┴──────────────────┐
                    ▼                                   ▼
         ┌──────────────────┐               ┌──────────────────┐
         │ Vue 3 Frontend   │               │  Go/Gin Backend  │
         │ (Vite + Pinia)   │   REST API    │  (REST API)      │
         └──────────────────┘               └────┬──────┬──────┘
                                                 │      │
              ┌──────────────────────────────────┘      │
              │                                         │
    ┌─────────▼─────────┐    ┌────────────┐   ┌────────▼───────┐
    │ PostgreSQL-Manager │    │    Redis   │   │ PostgreSQL-Data │
    │ (配置/使用者資料)   │    │  (快取)    │   │  (儀表板資料)   │
    └───────────────────┘    └────────────┘   └────────────────┘
                                                        ▲
                                             ┌──────────┴──────────┐
                                             │  Airflow ETL Pipelines│
                                             │  (150+ DAGs)         │
                                             └─────────────────────┘
              ┌──────────────────────────────┐
              │        Qdrant Vector DB       │
              │  (語意搜尋 / E5 Embeddings)   │
              └──────────────────────────────┘
              ┌──────────────────────────────┐
              │   TWCC AI Foundry (外部)      │
              │   llama3.3-ffm-70b            │
              └──────────────────────────────┘
```

**資料流向：**

1. Airflow DAG 從政府開放資料 API（TDX、CHT 等）抓取資料
2. 轉換後寫入 PostgreSQL-Data（儀表板資料）
3. Go 後端讀取資料並透過 REST API 回傳
4. Vue 前端呈現圖表和地圖
5. 使用者設定、認證資訊存於 PostgreSQL-Manager
6. Redis 快取熱門資料，降低資料庫負載
7. Qdrant 儲存元件語意向量，支援 AI 搜尋

---

## 3. 技術棧總覽

| 層級 | 技術 | 版本 |
|------|------|------|
| **前端框架** | Vue.js 3 | 3.4.15 |
| **前端建置工具** | Vite | 5.0.12 |
| **前端狀態管理** | Pinia | 2.1.7 |
| **地圖** | Mapbox GL + Deck.gl | 3.1.0 / 9.0.9 |
| **3D 渲染** | Three.js | 0.163.0 |
| **圖表** | ApexCharts | 3.45.2 |
| **後端語言** | Go | 1.25.4 |
| **後端框架** | Gin | 1.9.1 |
| **ORM** | GORM | 1.25.5 |
| **資料庫** | PostgreSQL + PostGIS | 16 / 3.4 |
| **快取** | Redis | 7.2.3 |
| **向量資料庫** | Qdrant | latest |
| **工作流程** | Apache Airflow | 2.10.5 |
| **容器** | Docker / Docker Compose | - |
| **K8s 部署** | Kubernetes + Helm | v2.2.0 chart |
| **AI 推理** | ONNX Runtime + TWCC API | 1.23.2 |

---

## 4. 後端分析（Go/Gin）

### 4.1 目錄結構

```
Taipei-City-Dashboard-BE/
├── app/
│   ├── controllers/          # 17 個控制器（API 處理邏輯）
│   ├── models/              # 資料模型與 DB 操作
│   ├── routes/              # 路由設定
│   ├── middleware/          # 中介軟體（認證、限流、CORS）
│   ├── services/            # 業務邏輯服務
│   ├── cache/               # Redis 快取層
│   ├── util/                # 工具函式
│   └── initial/             # 初始化與示範資料載入
├── global/                  # 全域設定與常數
├── logs/                    # 日誌工具
├── cmd/                     # CLI 命令處理器
└── main.go                  # 入口點
```

### 4.2 API 端點總覽

```
/api/v1/
├── /auth/
│   ├── POST   /login                    # 基本認證登入（JWT）
│   ├── GET    /callback                 # Isso/Taiwan Pass OAuth 回調
│   └── POST   /logout                   # 登出
│
├── /user/
│   ├── GET    /me                       # 取得登入使用者資訊
│   ├── PATCH  /me                       # 更新使用者資料
│   ├── POST   /:id/viewpoint            # 儲存地圖視角
│   └── GET    /:id/viewpoint            # 取得地圖視角
│
├── /component/
│   ├── GET    /                         # 列出所有元件
│   ├── GET    /:id                      # 元件詳情
│   ├── GET    /:id/chart                # 圖表資料（支援 city, time_from, time_to）
│   ├── GET    /:id/history              # 歷史資料（自動決定時間粒度）
│   ├── POST   /                         # [管理員] 新增元件
│   ├── PATCH  /:id                      # [管理員] 更新元件
│   └── DELETE /:id                      # [管理員] 刪除元件
│
├── /dashboard/
│   ├── GET    /                         # 公開儀表板列表
│   ├── GET    /:index                   # 儀表板詳情
│   ├── POST   /                         # 個人儀表板（登入使用者）
│   ├── PATCH  /:index                   # 更新個人儀表板
│   └── DELETE /:index                   # 刪除個人儀表板
│
├── /vector/
│   └── POST   /component               # AI 語意搜尋（Qdrant）
│
├── /chatlog/
│   ├── POST   /                         # 建立對話 Session
│   ├── GET    /session                  # 列出 Sessions
│   └── GET    /session/:session         # Session 詳情
│
├── /ai/
│   └── POST   /chat/twai               # TWCC AI Foundry 對話
│
├── /contributor/                        # 資料來源管理（CRUD）
├── /issue/                              # 使用者回饋（CRUD）
└── /incident/                           # 緊急事件管理（CRUD）
```

### 4.3 歷史資料查詢時間粒度邏輯

後端根據查詢時間範圍自動決定時間粒度：

| 時間範圍 | 粒度 |
|---------|------|
| < 24 小時 | 每小時 |
| < 1 個月 | 每日 |
| < 3 個月 | 每週 |
| < 2 年 | 每月 |
| > 2 年 | 每年 |

### 4.4 資料查詢類型

| 類型 | 說明 |
|------|------|
| `two_d` | 二維樞紐資料（類別 vs. 數值） |
| `three_d` | 三維資料（類別、子類別、數值） |
| `percent` | 百分比分布 |
| `time` | 時間序列資料 |
| `map_legend` | 地理特徵屬性資料 |

### 4.5 Middleware 執行鏈

```
所有請求
  → AddCommonHeaders（CORS、安全標頭）
  → SanitizeXForwardedFor（代理 IP 處理）
  → ValidateJWT（除登入/回調端點外）
  → 端點限流 + 角色檢查
```

### 4.6 限流設定（60 秒視窗）

| 端點 | API 限制 | 總量限制 |
|------|---------|---------|
| /auth | 30,000 | 60,000 |
| /component | 20,000 | 100,000 |
| /chatlog POST | 60 | - |
| /dashboard | 20,000 | 100,000 |

---

## 5. 前端分析（Vue 3）

### 5.1 目錄結構

```
Taipei-City-Dashboard-FE/
├── src/
│   ├── App.vue                  # 根元件（含版面配置）
│   ├── main.js                  # Vue 應用初始化
│   ├── router/                  # Vue Router 路由設定
│   ├── store/                   # Pinia 狀態管理
│   ├── views/                   # 頁面元件
│   ├── components/              # 可複用元件
│   ├── dashboardComponent/      # 圖表 Widget 庫（25+ 種）
│   ├── directives/              # Vue 自訂指令
│   └── assets/                  # 圖片、SCSS 樣式
└── vite.config.js               # Vite 建置設定
```

### 5.2 路由結構

```
/                          → 重定向 /dashboard
/dashboard                 → DashboardView（主儀表板）
/mapview                   → MapView（地理空間視圖）
/component                 → ComponentView（元件瀏覽器）
/component/:index          → ComponentInfoView（元件詳情）
/embed/:id/:city           → EmbedView（可嵌入 Widget）
/admin/dashboard           → 儀表板管理
/admin/user                → 使用者管理
/admin/contributor         → 資料來源管理
/admin/edit-component      → 元件設定
/admin/issue               → 回饋管理
/admin/disaster            → 緊急事件系統
```

### 5.3 Pinia Store

| Store | 大小 | 職責 |
|-------|------|------|
| `contentStore.js` | 31 KB | 儀表板/元件資料、圖表更新 |
| `mapStore.js` | 72 KB | 地圖狀態、圖層、視角 |
| `authStore.js` | - | 使用者認證與權限 |
| `adminStore.js` | 12 KB | 管理後台狀態 |
| `dialogStore.js` | - | 彈窗顯示狀態 |
| `chatStore.js` | - | AI 對話介面狀態 |

### 5.4 圖表元件庫（25+ 種）

| 分類 | 元件 |
|------|------|
| 長條圖類 | BarChart, BarPercentChart, BarChartWithGoal, ColumnChart, ColumnLineChart |
| 時間序列 | TimelineStackedChart, TimelineSeparateChart |
| 儀表類 | SpeedometerChart, GuageChart |
| 圓形圖 | DonutChart |
| 文字/圖示 | TextUnitChart, IconPercentChart |
| 地理 | DistrictChart, MapLegend |
| 捷運專用 | MetroChart, MetroCarDensity |
| 其他 | RadarChart, TagTooltip, ComponentTag |

---

## 6. 資料工程分析（Airflow）

### 6.1 目錄結構

```
Taipei-City-Dashboard-DE/
├── dags/
│   ├── proj_city_dashboard/         # 150+ 台北市 DAG
│   ├── proj_new_taipei_city_dashboard/  # 新北市 DAG
│   ├── operators/
│   │   └── common_pipeline.py       # 佇列路由邏輯
│   ├── utils/                       # ETL 工具函式
│   │   ├── extract_stage.py (32KB)  # 資料萃取
│   │   ├── transform_address.py (40KB) # 地址正規化
│   │   ├── transform_time.py (11KB) # 時間轉換
│   │   ├── transform_geometry.py    # 地理轉換
│   │   ├── load_stage.py (13KB)     # 資料載入
│   │   └── housekeeping.py (12KB)   # 資料清理
│   └── settings/
│       └── global_config.py         # 全域設定
└── docker/                          # Airflow Docker 設定
```

### 6.2 DAG 佇列路由規則

| 排程頻率 | 佇列 |
|---------|------|
| ≤ 10 分鐘（即時） | `realtime` |
| 每日，DAG ID 為偶數 | `default` |
| 每日，DAG ID 為奇數 | `heavy` |
| 每月以上 | `heavy` |
| 其他（小時、週） | `default` |

### 6.3 ETL 流程

```
資料來源（TDX / CHT / 政府開放資料）
    ↓
extract_stage.py（API 抓取）
    ↓
transform_address.py（地址正規化）
transform_geometry.py（GIS 轉換）
transform_time.py（時間對齊）
    ↓
load_stage.py（寫入 PostgreSQL）
    ↓
housekeeping.py（舊資料歸檔、清理）
```

### 6.4 Airflow 效能最佳化設定

```ini
AIRFLOW__SCHEDULER__PARSING_PROCESSES=2
AIRFLOW__SCHEDULER__MIN_FILE_PROCESS_INTERVAL=120
AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=300
AIRFLOW__SCHEDULER__MAX_THREADS=2
```
（避免大量 DAG 檔案反覆解析造成 CPU 飽和）

---

## 7. 資料庫 Schema

### 7.1 兩個 PostgreSQL 16 實例（含 PostGIS 3.4）

**DASHBOARD DB**（儀表板統計資料）
- 儲存各元件的實際量測值、時間序列資料
- 使用 PostGIS 支援地理資料
- 由 Airflow DAG 持續寫入

**MANAGER DB**（設定與中繼資料）

| 資料表 | 說明 |
|-------|------|
| `auth_user` | 使用者帳號 |
| `role` | 使用者角色 |
| `group` | 使用者群組（public, taipei, metrotaipei） |
| `auth_user_group_role` | 使用者-群組-角色對應 |
| `dashboards` | 儀表板中繼資料 |
| `dashboard_group` | 儀表板群組 |
| `components` | 元件定義 |
| `component_charts` | 圖表設定 |
| `component_maps` | 地圖圖層設定 |
| `contributors` | 資料來源歸屬 |
| `query_charts` | 語意向量（Qdrant 用） |
| `issue` | 使用者回饋 |
| `incident` | 緊急事件 |
| `chat_log` | 對話紀錄 |
| `ai_chat_log` | AI 對話紀錄 |
| `viewport` | 儲存地圖視角 |

---

## 8. Docker 與部署設定

### 8.1 Docker Compose 服務清單

| 服務 | 說明 | 對外 Port |
|------|------|---------|
| `nginx` | 反向代理 | 80, 443 |
| `dashboard-fe` | Vue Vite 開發伺服器 | - |
| `dashboard-be` | Go 應用程式 | 8080 |
| `postgres-data` | 儀表板資料 DB | 5432 |
| `postgres-manager` | 管理員設定 DB | - |
| `redis` | 快取 | 6379 |
| `qdrant` | 向量資料庫 | 6333 |
| `pgadmin` | DB 管理介面 | 8889 |

### 8.2 啟動順序

```bash
# 1. 啟動資料庫
docker-compose -f docker-compose-db.yaml up -d

# 2. 初始化（migrate + 載入示範資料）
docker-compose -f docker-compose-init.yaml up

# 3. 啟動所有服務
docker-compose -f docker-compose.yaml up -d
```

### 8.3 Dockerfile 多階段建置

**後端：**
1. `model_export` — 匯出 ONNX E5 Embeddings 模型
2. `builder` — 編譯 Go 應用程式
3. `prod` — Debian slim 執行環境（含 ONNX Runtime）
4. `dev` — Go 開發環境（Volume Mount）

**前端：**
- Node.js 建置階段 → Nginx 靜態檔案服務

### 8.4 關鍵環境變數

```bash
# 前端
VITE_API_URL=/api/dev
VITE_MAPBOXTOKEN=              # 必填：Mapbox 存取 Token
VITE_MAPBOXTILE=               # Tileset URL

# 後端
GIN_MODE=debug
JWT_SECRET=secret
IDNO_SALT=salt                 # 身分證號雜湊用 salt

# 資料庫
DB_DASHBOARD_HOST=postgres-data
DB_MANAGER_HOST=postgres-manager
DB_DASHBOARD_DBNAME=dashboard
DB_MANAGER_DBNAME=dashboardmanager

# AI
TWCC_API_URL=https://api-ams.twcc.ai/api
TWCC_MODEL=llama3.3-ffm-70b-16k-chat
QDRANT_URL=http://qdrant:6333

# 認證
ISSO_URL=https://id.taipei/isso
ISSO_CLIENT_ID=
ISSO_CLIENT_SECRET=
```

---

## 9. Kubernetes / Helm 部署

### 9.1 Helm Chart 結構

```
helm-chart/
├── Chart.yaml                        # v2.2.0
├── values-prod.yaml                  # 正式環境設定
├── values-sit.yaml                   # SIT 環境設定
├── values-external-db.yaml           # 外部 DB 設定
└── templates/
    ├── frontend-deployment.yaml
    ├── backend-deployment.yaml
    ├── frontend/backend-service.yaml
    ├── frontend-nginx-configmap.yaml
    ├── hpa.yaml                      # HPA 自動擴縮
    ├── ingress.yaml
    ├── postgresql-pvc.yaml
    ├── serviceaccount.yaml
    └── servicemonitor.yaml           # Prometheus 監控
```

### 9.2 正式環境資源設定

| 元件 | Replicas | CPU | Memory |
|------|---------|-----|--------|
| Frontend | 2 | 250m–1000m | 1280Mi–2560Mi |
| Backend | 2 | (見 values-prod) | (見 values-prod) |

**HPA：** 依 CPU/Memory 指標自動調整副本數
**Ingress：** Azure Internal Load Balancer

---

## 10. 安全與認證

### 10.1 認證機制

1. **本地認證：** Email + 密碼（SHA 雜湊）
2. **OAuth：** Isso / Taiwan Pass（台灣政府身分識別）
3. **JWT Token：** Bearer Token，8 小時過期
4. **IP 處理：** X-Forwarded-For 標頭正規化

### 10.2 RBAC 角色設計

```
群組：public / taipei / metrotaipei
角色：admin / viewer（推測）
使用者 → 群組 → 角色 多對多關聯
```

### 10.3 資料安全

- 兩個分離的 PostgreSQL 實例（資料庫分離）
- 後端限流防止濫用
- 身分證號使用 Salt 雜湊處理（`IDNO_SALT`）
- JWT 快取避免重複資料庫查詢

---

## 11. AI 功能整合

### 11.1 語意搜尋（Qdrant + E5 Embeddings）

```
使用者輸入查詢文字
    → Go 後端用 ONNX E5 模型生成向量
    → 對 Qdrant 進行向量相似度搜尋
    → 返回最相關的 Dashboard Component
```

- **模型：** E5-small（ONNX 格式，本地推理）
- **向量維度：** E5 標準 384 維
- **Collection：** `query_charts`（儲存元件描述向量）

### 11.2 AI 對話（TWCC AI Foundry）

```
使用者提問
    → POST /api/v1/ai/chat/twai
    → 呼叫 TWCC API（llama3.3-ffm-70b-16k-chat）
    → 紀錄至 ChatLog + AIChatLog
    → 回傳 AI 回應
```

- **模型：** llama3.3-ffm-70b（台灣 AI 雲端）
- **超時設定：** 60 秒
- **Session 追蹤：** 保存對話歷史

### 11.3 AI 架構評估

| 功能 | 技術 | 成熟度 |
|------|------|--------|
| 語意搜尋 | E5 + Qdrant | 生產就緒 |
| AI 對話 | TWCC LLaMA 3.3 | 生產就緒 |
| 本地 LM | ONNX Runtime | 開發中 |

---

## 12. 效能最佳化

### 12.1 後端

| 最佳化 | 機制 |
|--------|------|
| JWT 快取 | Redis 儲存 Token，避免重複 DB 查詢 |
| 資料快取 | Redis 快取常用元件資料 |
| 連線池 | GORM 內建連線池 |
| 限流 | 多層次限流保護後端 |

### 12.2 前端

| 最佳化 | 機制 |
|--------|------|
| 程式碼分割 | Vite vendor chunk 手動拆分 |
| 懶載入 | Vue Router 路由懶載入 |
| 資產壓縮 | vite-plugin-compression |
| 狀態更新去抖 | Pinia plugin debounce |

### 12.3 資料工程

| 最佳化 | 機制 |
|--------|------|
| 任務佇列分級 | realtime / default / heavy 三級佇列 |
| DAG 解析節流 | `PARSING_PROCESSES=2`, `MIN_FILE_PROCESS_INTERVAL=120` |
| 空間索引 | Rtree 加速地理查詢 |
| 增量載入 | 依排程頻率決定更新策略 |

---

## 13. 已知限制與未完成功能

| 功能 | 狀態 | 說明 |
|------|------|------|
| WebSocket | 已停用 | `websocket.go` 路由被註解 |
| CORS | 需設定 | `app.go` 中 CORS 政策被註解 |
| 本地語言模型 | 開發中 | ONNX LM 路由存在但未啟用 |
| 地圖寫入端點 | 未完整 | Write map endpoint 部分實作 |
| WebSocket 即時更新 | 未啟用 | 前端資料仍靠 Polling |

---

## 14. 專案統計

| 項目 | 數量 |
|------|------|
| 後端控制器 | 17 個檔案 |
| API 端點 | 40+ 個 |
| 前端 Vue 元件 | 30+ 個 |
| 圖表 Widget | 25+ 種 |
| Pinia Store | 6 個 |
| Airflow DAG | 150+ 個（台北市）|
| 資料庫表 | 20+ 個（橫跨 2 個 DB）|
| 後端 Go 模組 | 20+ 個 |
| 前端主要套件 | 10 個 |
| DE Python 套件 | 30+ 個 |
| 估計程式碼行數 | ~200,000 LOC |

---

## 15. 改善建議

### 15.1 高優先度

1. **啟用 CORS 設定**
   - `app.go` 中 CORS middleware 被註解，正式部署前需配置
   - 建議使用環境變數控制允許的 Origin

2. **JWT_SECRET 強化**
   - `.env.template` 預設值為 `secret`，生產環境必須換成高強度隨機值
   - 考慮加入 JWT Token Rotation 機制

3. **WebSocket 即時更新**
   - 目前前端靠 Polling，啟用 WebSocket 可降低伺服器負載
   - `websocket.go` 已存在，需完成連接管理邏輯

### 15.2 中優先度

4. **本地 LM 路由**
   - ONNX LM 基礎設施已就位，補完 API 路由可降低對 TWCC 的依賴
   - 適合處理敏感或離線場景

5. **Airflow 監控**
   - 增加 DAG 失敗告警（Slack / Email 通知）
   - 考慮加入資料品質檢查步驟（Great Expectations 或自訂驗證）

6. **前端測試**
   - 目前僅有 ESLint，缺少 Vitest 單元測試和 E2E 測試（Playwright）

### 15.3 低優先度

7. **API 版本策略**
   - 目前固定為 `/api/v1/`，建議建立版本遷移計畫

8. **地圖 Write 端點完整化**
   - 部分地圖相關 Write 端點尚未完整實作

9. **日誌結構化**
   - 統一日誌格式（JSON structured logging），方便 Loki / ELK 收集

---

*本報告由自動化 codebase 分析產生，基於 2026-04-13 當日的程式碼狀態。*
