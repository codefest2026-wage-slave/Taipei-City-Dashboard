# Taipei City Dashboard — AI 功能完整分析與建議

**日期：** 2026-04-13
**版本：** 2.2.0
**分析範圍：** 全端 AI 功能（後端 / 前端 / 向量資料庫 / 工具系統）

---

## 目錄

1. [AI 系統架構總覽](#1-ai-系統架構總覽)
2. [語意搜尋（Vector Search）](#2-語意搜尋vector-search)
3. [AI 對話（TWCC LLaMA）](#3-ai-對話twcc-llama)
4. [工具呼叫系統（Tool Calling）](#4-工具呼叫系統tool-calling)
5. [AI 對話紀錄](#5-ai-對話紀錄)
6. [前端 AI 體驗](#6-前端-ai-體驗)
7. [目前限制](#7-目前限制)
8. [安全性評估](#8-安全性評估)
9. [效能評估](#9-效能評估)
10. [改善建議](#10-改善建議)

---

## 1. AI 系統架構總覽

```
使用者輸入
     │
     ├── 語意搜尋路徑
     │       ↓
     │   POST /api/v1/vector/component
     │       ↓
     │   ONNX E5 Embeddings（本地推理）
     │   768 維向量 → Qdrant Cosine 搜尋
     │       ↓
     │   返回最相似的 Dashboard Components
     │       ↓
     │   前端自動建立個人儀表板
     │
     └── AI 對話路徑
             ↓
         POST /api/v1/ai/chat/twai
             ↓
         Semaphore 並發控制（max 10）
             ↓
         TWCC API（llama3.3-ffm-70b-16k-chat）
             ↓
         Tool Calling Loop（最多 5 輪）
             ├── get_current_time
             └── get_population_summary
             ↓
         SSE 串流回應 + 記錄至 ai_chatlog
```

**三個核心 AI 子系統：**

| 子系統 | 技術 | 狀態 |
|--------|------|------|
| 語意向量搜尋 | E5 Multilingual + Qdrant | 生產就緒 |
| AI 對話 | TWCC LLaMA 3.3 + LangChainGo | 生產就緒 |
| 本地 LM | ONNX Runtime（E5 embeddings） | 運行中（embeddings only） |

---

## 2. 語意搜尋（Vector Search）

### 2.1 技術細節

**Embedding 模型：** `intfloat/multilingual-e5-base`
- 維度：**768 維**
- 格式：ONNX（本地推理，無需 GPU）
- Tokenizer：`sugarme/tokenizer`（HuggingFace 格式）

**向量生成流程：**

```
輸入文字
    → 加上前綴 "query: "
    → Tokenize → input_ids + attention_mask tensors
    → ONNX Runtime 推理
    → last_hidden_state [1, seq_len, 768]
    → Mean Pooling（排除 padding token）
    → L2 正規化
    → 768 維單位向量
```

**Qdrant Collection：**
- Collection 名稱：`query_charts`（可設定）
- 距離指標：Cosine Similarity
- Payload 欄位：id, index, name, city, long_desc, use_case

**向量搜尋 API：**

```
POST /api/v1/vector/component
Body:
  query: string       # 使用者查詢文字
  limit: int          # 1–30，預設 10
  score: float        # 閾值 0–1，預設 0.78（前端使用 0.80）

Response:
  [{ id, index, name, city, score }, ...]
```

### 2.2 Qdrant 索引重建機制

**自動觸發：** 每次元件新增或更新時自動重建
**手動觸發：** `POST /api/v1/qdrant/rebuild`（需管理員權限）

**重建流程：**
1. Atomic Lock 防止並發重建（409 Conflict 若正在進行中）
2. 從 Manager DB 取得所有公開元件（含 long_desc + use_case）
3. 批次生成 768 維向量
4. 刪除舊 Collection → 建立新 Collection → Upsert 全部點位
5. 失敗項目跳過並記錄，不中斷整體流程

**Python 初始化腳本**（`docker/qdrant-upgrade/upgrade_vector_db.py`）：
- 使用 `SentenceTransformer`（Python）建立初始向量庫
- 於 `docker compose --profile tools` 觸發

### 2.3 重要發現

> **⚠️ Embedding 模型版本不一致**
>
> - Go 後端：使用 ONNX 格式的 `e5` 模型，推斷來自 `multilingual-e5-base`
> - Python 初始化腳本：明確使用 `intfloat/multilingual-e5-base`
>
> 如果兩者使用不同版本或不同的 pooling 策略，查詢向量與索引向量的分佈會不一致，導致搜尋結果品質下降。建議明確鎖定相同版本並驗證向量相似度。

---

## 3. AI 對話（TWCC LLaMA）

### 3.1 技術架構

**LLM 框架：** `tmc/langchaingo` v0.1.14
**外部模型：** `llama3.3-ffm-70b-16k-chat`（TWCC Taiwan Computing Cloud）
**串流方式：** SSE（Server-Sent Events）

**可設定參數：**

| 參數 | 說明 |
|------|------|
| `max_new_tokens` | 最大輸出 Token 數 |
| `temperature` | 隨機性（0=確定性，1=創意） |
| `top_p` | 核採樣 |
| `top_k` | Top-K 採樣 |
| `frequency_penalty` | 重複懲罰 |
| `stop_sequences` | 停止符號列表 |
| `seed` | 隨機種子（可重現） |

**訊息角色支援：**
```
system / user / assistant / tool
```

### 3.2 TWCC Provider 實作細節

**並發控制：**
```go
// Semaphore 限制同時處理的 AI 請求
TWCC_MAX_CONCURRENT=10   // 預設值，可設定
```

**重試策略：**
- `TWCC_MAX_RETRY=2`（最多 2 次重試）
- `TWCC_TIMEOUT=60`（秒）

**串流處理：**
- `streamProcessor` 解析 SSE chunks
- 自動偵測 Tool Call vs. 文字生成
- 累積 Tool 參數（跨多個 chunks）
- Buffer flush 保證順序輸出

**XML Cleanup：**
- 清除 LLM 幻覺產生的 `<function=...>` 標籤
- 支援 XML fallback 解析 malformed tool calls

### 3.3 Request / Response 格式

**Input（AIChatInput）：**
```json
{
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "台北市人口現況？" }
  ],
  "tool_choice": "auto",
  "max_new_tokens": 1024,
  "temperature": 0.7
}
```

**Output：**
```json
{
  "answer": "台北市目前總人口...",
  "tool_used": true,
  "input_tokens": 245,
  "output_tokens": 189,
  "total_tokens": 434,
  "latency_ms": 3240,
  "model": "llama3.3-ffm-70b-16k-chat",
  "provider": "twcc",
  "session_id": "abc-123"
}
```

---

## 4. 工具呼叫系統（Tool Calling）

### 4.1 架構設計

**位置：** `Taipei-City-Dashboard-BE/app/services/ai/tools/registry.go`

**Agentic Loop：**
```
使用者問題
    → LLM 決定是否呼叫工具
    → 解析 Tool Call（JSON 或 XML fallback）
    → 執行工具函式
    → 將結果注入下一輪 LLM 輸入
    → 最多 5 輪迭代
    → 返回最終文字回應
```

**System Prompt 注入（工具使用規則）：**
- 只能呼叫白名單內的工具
- 禁止巢狀工具呼叫
- 參數必須是字面值（不可是函式呼叫）
- 有依賴關係的工具需依序呼叫
- 無法呼叫工具時退回文字回應

### 4.2 現有工具

**Tool 1：`get_current_time`**
```
功能：取得台北時區當前時間
回傳：Asia/Taipei 時區的 ISO 時間戳記
用途：讓 LLM 能感知當前時間
```

**Tool 2：`get_population_summary`**
```
功能：查詢台北市或新北市人口年齡分布
參數：
  city: "taipei" | "new_taipei"
  year: int（年份）
資料表：
  taipei     → population_age_distribution_tpe
  new_taipei → population_age_distribution_new_tpe
回傳：幼齡、工作年齡、老年人口統計（中文格式）
```

### 4.3 工具擴充機制

新增工具只需實作 `ToolFunc` 簽名並在 registry 中登錄，架構非常易於擴充：

```go
// 新增工具的最小實作範例
tools.Register(tools.ToolDefinition{
    Name:        "get_air_quality",
    Description: "Get current air quality index for Taipei districts",
    Parameters:  schema,
    Function:    myToolFunction,
})
```

---

## 5. AI 對話紀錄

### 5.1 雙層紀錄架構

**舊版（向量搜尋用）：** `chat_logs` 表
```sql
session, question, answer, ip_address, user_id, created_at
```

**新版（AI 對話用）：** `ai_chatlog` 表
```sql
session_id, user_id, provider, model,
question, answer, tool_used, tools (JSONB),
input_tokens, output_tokens, total_tokens, latency_ms,
status,        -- "success" | "error"
error_code, error_message,
ip_address, created_at
```
索引：`idx_ai_chatlog_session`, `idx_ai_chatlog_user`

### 5.2 可觀察性能力

| 指標 | 記錄方式 |
|------|---------|
| Token 用量 | input/output/total tokens 欄位 |
| 延遲 | latency_ms 欄位 |
| 工具使用 | tool_used + tools JSONB |
| 錯誤追蹤 | status + error_code + error_message |
| 身分審計 | user_id + ip_address |

---

## 6. 前端 AI 體驗

### 6.1 ChatBox 元件功能

**位置：** `src/components/dialogs/ChatBox.vue`

**使用者流程：**
1. 點擊 ChatBot 圖示開啟對話框
2. 輸入自然語言查詢（例：「台北市空氣品質相關資料」）
3. 系統呼叫 `/api/v1/vector/component`（score 閾值 0.80）
4. 顯示推薦 Component 表格（排名、城市、名稱、相似度分數）
5. 點擊「建立儀表板」 → 自動建立個人儀表板

**去重邏輯：**
```javascript
// 同一 component index 出現在多個城市時
// 優先保留 'metrotaipei' 版本
deduplicateByIndex(results) {
  // prefer 'metrotaipei' over 'taipei'
}
```

**限制：** 最多 20 個個人儀表板（建立前驗證）

### 6.2 前端 AI 限制

| 限制 | 說明 |
|------|------|
| 純向量搜尋 | ChatBox 目前**只用向量搜尋**，不呼叫 TWCC AI 對話 |
| 無多輪對話 | 每次查詢獨立，無上下文記憶 |
| 固定閾值 | score 閾值硬編碼為 0.80 |
| SessionStorage | 對話僅存於瀏覽器，重啟後消失 |

> **注意：** `/api/v1/ai/chat/twai` 已實作於後端，但**前端 ChatBox 目前並未呼叫此端點**。AI 對話功能尚未整合進前端 UI。

---

## 7. 目前限制

### 7.1 功能層面

| 限制 | 嚴重度 | 說明 |
|------|--------|------|
| 前端未整合 TWCC 對話 | 高 | 後端已就緒，前端 ChatBox 仍用純向量搜尋 |
| 工具數量僅 2 個 | 中 | 只有時間與人口工具，覆蓋率低 |
| 無使用者上下文 | 中 | LLM 不知道使用者當前看哪個儀表板 |
| 單一模型 | 低 | 執行期只能使用一個 TWCC 模型 |
| TWCC 外部依賴 | 中 | 服務可用性依賴台灣 AI 雲端 |

### 7.2 技術層面

| 問題 | 位置 | 說明 |
|------|------|------|
| Embedding 模型版本不一致 | go vs. python | Go ONNX 版本未明確標示 |
| Tool Calling Loop 上限 5 輪 | ai_service.go | 複雜任務可能不夠 |
| 無 RAG 架構 | 全系統 | 資料僅透過工具查詢，缺乏文件檢索 |
| 向量索引無增量更新 | qdrant.go | 每次元件變更都全量重建 |
| ChatBox 無 streaming 顯示 | ChatBox.vue | 後端支援串流但前端未實作 |

---

## 8. 安全性評估

| 項目 | 狀態 | 說明 |
|------|------|------|
| XSS 防護 | ✅ | `html.EscapeString()` 在 ai.go 中 |
| JWT 認證 | ✅ | AI 端點需登入 |
| 限流 | ✅ | `/chatlog POST` 限 60 req/min |
| 並發控制 | ✅ | Semaphore max 10 |
| Prompt Injection | ⚠️ | System Prompt 有工具白名單，但無對抗性測試 |
| API Key 保護 | ⚠️ | TWCC_API_KEY 在 .env 中明文儲存 |
| 審計日誌 | ✅ | ai_chatlog 記錄 user_id + ip + tokens |
| 輸出驗證 | ⚠️ | LLM 輸出未做結構化驗證 |

---

## 9. 效能評估

| 指標 | 現況 | 說明 |
|------|------|------|
| Embedding 推理 | 本地 ONNX，毫秒級 | 無網路延遲 |
| Qdrant 搜尋 | 毫秒級 | 768 維 Cosine，極快 |
| TWCC LLM 延遲 | 約 3–10 秒 | 視 token 數與網路 |
| 並發上限 | 10 個同時 AI 請求 | 可透過 env 調整 |
| 向量重建 | 全量重建，耗時 | 元件數量多時慢 |
| 前端無串流 | 需等待完整回應 | 使用者體驗較差 |

---

## 10. 改善建議

### 10.1 高優先度

#### A. 前端整合 AI 對話功能

後端 TWCC 對話端點已完整就緒，但前端 ChatBox 目前只呼叫向量搜尋。建議：

```
現況：ChatBox → /api/v1/vector/component（純向量搜尋）
目標：ChatBox → /api/v1/ai/chat/twai（LLM 對話 + Tool Calling）
```

實作要點：
1. 在 `chatStore.js` 新增 `sendAIChat()` 方法呼叫 TWCC 端點
2. ChatBox.vue 加入串流顯示（SSE）
3. 保留向量搜尋作為「快速推薦」捷徑
4. 維持 Session 歷史（從 `ai_chatlog` 拉取）

#### B. 增加 Dashboard-aware Tool

讓 LLM 能感知使用者當前的儀表板狀態：

```go
tools.Register(tools.ToolDefinition{
    Name:        "get_dashboard_components",
    Description: "List components in user's current dashboard",
    Parameters:  /* city, dashboard_id */,
    Function:    getDashboardComponents,
})
```

這使 AI 能回答「這個儀表板有哪些資料？」或「幫我解釋這些數字」。

#### C. 向量索引改為增量更新

目前每次元件變更都全量重建 Qdrant Collection，當元件數量增長後會有效能問題：

```go
// 現況：全量重建
func RebuildQdrantPublicCollection() { ... }

// 建議：增量 upsert
func UpsertComponentVector(componentID int) {
    // 只更新單一元件的向量
    qdrantClient.Upsert(collection, []Point{newPoint})
}
```

---

### 10.2 中優先度

#### D. 擴充工具庫

依照儀表板現有資料，優先新增以下工具：

| 工具名稱 | 資料來源 | 用途 |
|---------|---------|------|
| `get_air_quality` | 空氣品質元件 | 詢問當前空氣品質 |
| `get_traffic_status` | 交通元件 | 即時路況查詢 |
| `get_youbike_availability` | YouBike 元件 | 單車可借數量 |
| `search_components` | Qdrant（已有） | 讓 LLM 主動搜尋相關元件 |
| `get_incident_alerts` | incident 表 | 緊急事件通知 |

#### E. 前端 Streaming 顯示

後端已支援 SSE 串流，前端應實作對應的漸進顯示：

```javascript
// chatStore.js
async sendAIChat(message) {
  const response = await fetch('/api/v1/ai/chat/twai', {
    method: 'POST',
    headers: { 'Accept': 'text/event-stream' },
    body: JSON.stringify({ messages })
  })
  const reader = response.body.getReader()
  // 逐步更新 UI
}
```

#### F. Prompt Engineering 強化

目前系統 Prompt 主要做工具使用規範，建議加入：

```
1. 角色定義：「你是台北市智慧儀表板助理，專精城市數據分析」
2. 回應語言：預設回繁體中文
3. 引用數據時說明來源時間（可用 get_current_time）
4. 推薦相關儀表板（呼叫向量搜尋工具）
5. 拒絕回答與城市治理無關的問題
```

---

### 10.3 低優先度

#### G. 多模型支援

建立 Provider 抽象層，支援切換或同時使用多個 LLM：

```go
// 已有 providers/ 目錄，新增：
providers/
├── twcc/      # 現有
├── openai/    # GPT-4o
└── local/     # Ollama 本地模型
```

#### H. RAG 架構（文件檢索）

將政府公告、施政說明、資料字典等文件向量化存入 Qdrant，建立 RAG 流程，讓 LLM 能基於官方文件回答問題，而非純靠參數記憶。

#### I. Embedding 模型版本鎖定

明確對齊 Go ONNX 與 Python SentenceTransformer 使用的模型版本：

```python
# upgrade_vector_db.py - 明確版本
model = SentenceTransformer('intfloat/multilingual-e5-base', 
                             revision='e4ce9877abf3edfe10b0d82785e83bdcb973e22e')
```

對應 Go 端的 ONNX 模型也需確認從相同 commit 匯出。

#### J. 向量搜尋結果解釋性

在搜尋結果旁顯示為何推薦此元件（目前只顯示 score 數字）：

```javascript
// 顯示關鍵詞匹配片段
{ name: "空氣品質指標", score: 0.92, matchedText: "PM2.5 空污..." }
```

---

## 小結

| 面向 | 評分 | 說明 |
|------|------|------|
| 架構設計 | ★★★★☆ | 模組清晰，Provider 模式易擴充 |
| 向量搜尋 | ★★★★☆ | 本地推理快，但需對齊模型版本 |
| AI 對話後端 | ★★★★☆ | Tool Calling、串流、日誌齊備 |
| 前端整合 | ★★☆☆☆ | 後端就緒但前端未使用 AI 對話 |
| 工具覆蓋率 | ★★☆☆☆ | 僅 2 個工具，覆蓋範圍有限 |
| 安全性 | ★★★☆☆ | 基礎防護到位，Prompt Injection 待測 |
| 可觀察性 | ★★★★☆ | Token/延遲/工具使用皆有記錄 |

**最重要的下一步：將 ChatBox 前端整合至已就緒的 TWCC 對話 API，並新增 Dashboard-aware Tools。**

---

*本報告基於 2026-04-13 當日的程式碼狀態，由 Claude Code 自動分析產生。*
