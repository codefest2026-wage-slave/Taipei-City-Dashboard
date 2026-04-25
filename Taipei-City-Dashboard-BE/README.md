# 台北城市儀表板 — 後端

[台北城市儀表板](https://citydashboard.taipei) 的 Go REST API 後端，由[台北市都市智慧中心 (TUIC)](https://tuic.gov.taipei) 開發。

## 技術架構

| 層級 | 技術 |
|---|---|
| Web 框架 | [Gin](https://github.com/gin-gonic/gin) |
| 資料庫 | PostgreSQL（透過 [GORM](https://gorm.io)） |
| 快取 / 流量限制 | Redis（`go-redis`） |
| 向量資料庫 | [Qdrant](https://qdrant.tech) |
| 嵌入模型 | multilingual-e5-base（ONNX Runtime） |
| AI / LLM | TWCC（國家高速網路中心）透過 [langchaingo](https://github.com/tmc/langchaingo) |
| 身份驗證 | JWT（HS256，8 小時有效期）+ TaipeiPass OAuth |
| CLI | [Cobra](https://github.com/spf13/cobra) |
| 排程 | [robfig/cron](https://github.com/robfig/cron) |

## 目錄結構

```
Taipei-City-Dashboard-BE/
├── main.go                     # 程式進入點
├── go.mod / go.sum             # Go 模組
├── Dockerfile                  # 多階段建置（Python 模型匯出 → Go 建置 → Runtime）
├── Makefile                    # 建置指令
├── requirements.txt            # ONNX 模型匯出所需 Python 套件
├── export_model.py             # 將 multilingual-e5-base 匯出為 ONNX 格式
├── cmd/
│   └── root.go                 # CLI 指令（serve、migrateDB、initDashboard）
├── global/
│   ├── consts.go               # 流量限制常數、JWT 設定
│   └── global.go               # 設定結構與環境變數載入
├── logs/
│   └── logs.go                 # 結構化日誌
└── app/
    ├── app.go                  # 應用程式啟動（DB、Redis、Gin、伺服器）
    ├── routes/
    │   └── router.go           # 路由定義
    ├── initial/
    │   ├── initial.go          # 資料庫 Schema 建立與樣本資料載入
    │   └── cron.go             # 排程工作（聊天記錄清理）
    ├── middleware/
    │   ├── auth.go             # JWT 驗證
    │   ├── common.go           # CORS、IsLoggedIn、IsSysAdm 守衛
    │   ├── rateLimit.go        # 每個端點及全域請求限制
    │   └── sanitizeXForwardedFor.go
    ├── controllers/            # HTTP 請求處理器
    ├── models/                 # GORM 資料模型與查詢函式
    ├── services/
    │   ├── ai/
    │   │   ├── ai_service.go   # AI 會話編排、工具呼叫迴圈
    │   │   ├── providers/twcc/ # TWCC LLM 提供者（串流與標準模式）
    │   │   └── tools/registry.go # 內建 AI 工具
    │   └── qdrant.go           # 向量集合重建服務
    ├── cache/
    │   └── redis.go            # Redis 客戶端
    └── util/                   # JWT 產生、驗證工具函式
```

## 資料庫

後端連接**兩個** PostgreSQL 資料庫：

| 環境變數前綴 | 預設資料庫名稱 | 用途 |
|---|---|---|
| `DB_MANAGER_*` | `dashboardmanager` | 使用者、角色、群組、元件與儀表板設定、問題回報 |
| `DB_DASHBOARD_*` | `dashboard` | 城市統計資料、圖表與地圖資料 |

## 環境變數

複製 Docker 環境範本開始設定：

```bash
cp ../docker/.env.template ../docker/.env
```

| 變數 | 預設值 | 說明 |
|---|---|---|
| `GIN_DOMAIN` | `` | 監聽位址（空白 = 所有介面） |
| `GIN_PORT` | `8080` | HTTP 監聽埠 |
| `JWT_SECRET` | | HS256 簽名金鑰 |
| `IDNO_SALT` | | ID 雜湊鹽值 |
| `DB_MANAGER_HOST` | `postgres-manager` | Manager DB 主機 |
| `DB_MANAGER_PORT` | `5432` | Manager DB 連接埠 |
| `DB_MANAGER_USER` | | Manager DB 使用者名稱 |
| `DB_MANAGER_PASSWORD` | | Manager DB 密碼 |
| `DB_MANAGER_DBNAME` | `dashboardmanager` | Manager DB 資料庫名稱 |
| `DB_MANAGER_SSLMODE` | `disable` | SSL 模式 |
| `DB_DASHBOARD_HOST` | `postgres-data` | Dashboard DB 主機 |
| `DB_DASHBOARD_PORT` | `5432` | Dashboard DB 連接埠 |
| `DB_DASHBOARD_USER` | | Dashboard DB 使用者名稱 |
| `DB_DASHBOARD_PASSWORD` | | Dashboard DB 密碼 |
| `DB_DASHBOARD_DBNAME` | `dashboard` | Dashboard DB 資料庫名稱 |
| `DB_DASHBOARD_SSLMODE` | `disable` | SSL 模式 |
| `REDIS_HOST` | `redis` | Redis 主機 |
| `REDIS_PORT` | `6379` | Redis 連接埠 |
| `REDIS_PASSWORD` | | Redis 密碼 |
| `REDIS_DB` | `0` | Redis DB 索引 |
| `QDRANT_URL` | `http://127.0.0.1:6333` | Qdrant 端點 |
| `QDRANT_COLLECTION` | | Qdrant 集合名稱 |
| `QDRANT_API_KEY` | | Qdrant API 金鑰 |
| `LM_MODEL_PATH` | `/opt/lm_model/onnx-e5/` | ONNX 嵌入模型路徑 |
| `TWCC_API_URL` | `https://api-ams.twcc.ai/api` | TWCC LLM 端點 |
| `TWCC_API_KEY` | | TWCC API 金鑰 |
| `TWCC_MODEL` | `llama3.3-ffm-70b-32k-chat` | 模型名稱 |
| `TWCC_TIMEOUT` | `60` | 請求逾時（秒） |
| `TWCC_MAX_RETRY` | `2` | 失敗重試次數 |
| `TWCC_MAX_CONCURRENT` | `100` | 最大並發 AI 請求數 |
| `ISSO_URL` | `https://id.taipei/isso` | TaipeiPass OAuth URL |
| `TAIPEIPASS_URL` | `https://id.taipei/tpcd` | TaipeiPass API URL |
| `ISSO_CLIENT_ID` | | OAuth 用戶端 ID |
| `ISSO_CLIENT_SECRET` | | OAuth 用戶端密鑰 |
| `DASHBOARD_DEFAULT_USERNAME` | | 初始管理員使用者名稱 |
| `DASHBOARD_DEFAULT_Email` | | 初始管理員電子信箱 |
| `DASHBOARD_DEFAULT_PASSWORD` | | 初始管理員密碼 |

## 啟動方式

### Docker Compose（建議）

```bash
# 從儲存庫根目錄執行
cp docker/.env.template docker/.env   # 填入設定值
make dev-start
```

停止服務：

```bash
make dev-stop
```

### 本機直接執行

需求：Go 1.24+、PostgreSQL、Redis、Qdrant

```bash
cd Taipei-City-Dashboard-BE

# 首次執行：匯出 ONNX 嵌入模型
pip install -r requirements.txt
python export_model.py

# 設定環境變數後啟動
go run main.go
```

### CLI 指令

```bash
# 啟動 API 伺服器（預設）
go run main.go

# 建立 / 更新 Manager DB Schema
go run main.go migrateDB

# 載入樣本儀表板資料至兩個資料庫
go run main.go initDashboard
```

## 程式碼品質

```bash
# 從儲存庫根目錄執行
make fmt      # go fmt 格式化
make lint     # golangci-lint（略過測試檔）
```

或在 BE 目錄中直接執行：

```bash
make fmt
make vet
make lint
make lint-all    # 包含測試檔
make lint-fix    # 自動修正
```

## API 端點

所有端點皆以 `/api/v1` 為前綴。

### 身份驗證

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| POST | `/auth/login` | — | 以電子信箱 + 密碼登入（Basic Auth） |
| GET | `/auth/callback` | — | TaipeiPass OAuth 回調 |
| POST | `/auth/logout` | — | 登出（TaipeiPass） |

### 使用者

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/user/me` | 登入 | 取得自身資料 |
| PATCH | `/user/me` | 登入 | 更新自身資料 |
| GET | `/user/` | 管理員 | 列出所有使用者 |
| PATCH | `/user/:id` | 管理員 | 更新指定使用者 |
| POST | `/user/:id/viewpoint` | 登入 | 儲存地圖視角 |
| GET | `/user/:id/viewpoint` | 登入 | 列出已儲存視角 |
| DELETE | `/user/:id/viewpoint/:viewpointid` | 登入 | 刪除指定視角 |

### 元件

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/component/` | — | 列出元件（支援篩選、排序、分頁） |
| GET | `/component/:id` | — | 取得元件設定 |
| GET | `/component/:id/all` | — | 取得元件及所有變體 |
| GET | `/component/:id/chart` | — | 取得圖表資料 |
| GET | `/component/:id/history` | — | 取得歷史資料 |
| POST | `/component/` | 管理員 | 建立元件 |
| PATCH | `/component/:id` | 管理員 | 更新元件 |
| PATCH | `/component/:id/chart` | 管理員 | 更新圖表設定 |
| PATCH | `/component/:id/map` | 管理員 | 更新地圖設定 |
| DELETE | `/component/:id` | 管理員 | 刪除元件 |

### 儀表板

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/dashboard/` | — | 列出使用者儀表板 |
| GET | `/dashboard/:index` | — | 取得儀表板與其元件 |
| POST | `/dashboard/` | 登入 | 建立個人儀表板 |
| PATCH | `/dashboard/:index` | 登入 | 更新儀表板 |
| DELETE | `/dashboard/:index` | 登入 | 刪除儀表板 |
| POST | `/dashboard/public` | 管理員 | 建立公開儀表板 |
| GET | `/dashboard/check-index/:index` | 管理員 | 檢查索引可用性 |

### 問題回報與事件

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| POST | `/issue/` | 登入 | 提交問題回報 |
| GET | `/issue/` | 管理員 | 列出所有問題 |
| PATCH | `/issue/:id` | 管理員 | 更新問題狀態 |
| GET | `/incident/` | 管理員 | 列出事件 |
| POST | `/incident/` | 管理員 | 建立事件 |
| PATCH | `/incident/:id` | 管理員 | 更新事件 |
| DELETE | `/incident/` | 管理員 | 刪除事件 |

### AI 與向量搜尋

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| POST | `/ai/chat/twai` | 登入 | 與 TWCC LLM 對話（支援串流） |
| POST | `/vector/component` | — | 語意元件搜尋 |

### 聊天記錄

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| POST | `/chatlog/` | 登入 | 記錄一則對話訊息 |
| GET | `/chatlog/session` | 登入 | 列出對話 Session |
| GET | `/chatlog/session/:session` | 登入 | 取得完整 Session 記錄 |

### 貢獻者

| 方法 | 路徑 | 權限 | 說明 |
|---|---|---|---|
| GET | `/contributor/` | — | 列出貢獻者 |
| POST | `/contributor/` | 管理員 | 新增貢獻者 |
| PATCH | `/contributor/:id` | 管理員 | 更新貢獻者 |
| DELETE | `/contributor/:id` | 管理員 | 刪除貢獻者 |

## 存取控制

角色採階層設計：**管理員** ⊃ **編輯者** ⊃ **檢視者**

- **公開**端點允許未驗證請求，使用公開群組的檢視者權限。
- **登入**端點需要有效的 JWT（`Authorization: Bearer <token>`）。
- **管理員**端點額外需要使用者帳號具備 `is_admin` 標記。

JWT Token 有效期為 **8 小時**，Claims 中已包含群組/角色權限集合，大多數授權檢查無需再次查詢資料庫。

## AI 功能

`/ai/chat/twai` 端點串接 TWCC LLM 服務，支援以下特性：

- **工具呼叫迴圈** — 每次請求最多執行 5 輪，已內建工具：
  - `get_current_time`：回傳台北時區當前時間
  - `get_population_summary`：查詢 Dashboard DB 中的人口統計資料
- **串流回應** — 支援 SSE 分塊輸出，即時顯示 AI 回覆
- **並發控制** — 透過 `TWCC_MAX_CONCURRENT` 設定最大並發數
- **稽核日誌** — 所有請求皆記錄至 `ai_chat_log`（含 Token 用量、延遲、錯誤）

## 嵌入模型

後端內建 `intfloat/multilingual-e5-base` 的 ONNX 格式，用於產生 Qdrant 向量搜尋所需的元件嵌入向量。模型於 Docker 建置時一併打包。

每當元件或儀表板被建立或更新時，Qdrant 集合會自動重建，並透過原子旗標確保並發安全。

## 排程工作

| 工作 | 排程 | 說明 |
|---|---|---|
| 聊天記錄清理 | 每日午夜 | 刪除 6 個月以前的聊天記錄 |

透過 Redis Lua 腳本實現分散式鎖，防止多實例同時執行。
