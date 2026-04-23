# AI Chat Integration 實作計畫

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 將已完整實作的後端 TWCC AI 對話功能接上前端 ChatBox，讓使用者能與 LLM 進行真實對話，並透過 Tool Calling 主動搜尋 Dashboard 元件。

**Architecture:** 後端新增 `search_components` 工具（封裝現有 Qdrant 搜尋），前端 `chatStore.js` 新增 `sendAIChat()` 方法呼叫 `/api/v1/ai/chat/twai`，`ChatBox.vue` 加入模式切換（向量快速推薦 vs AI 對話）與 SSE 串流顯示。

**Tech Stack:**
- Backend: Go/Gin，`app/services/ai/tools/registry.go`，`app/models/qdrant.go`
- Frontend: Vue 3 / Pinia，`src/store/chatStore.js`，`src/components/dialogs/ChatBox.vue`
- API: `POST /api/v1/ai/chat/twai`（已有），`POST /api/v1/vector/component`（已有）

---

## 範圍

本計畫分為 3 個 Phase，每個 Phase 可獨立交付：

| Phase | 功能 | 影響 |
|-------|------|------|
| **1** | 後端新增 `search_components` tool | AI 能主動搜尋元件 |
| **2** | 前端接上 AI 對話（非串流） | ChatBox 支援真實 LLM 對話 |
| **3** | 前端 SSE 串流顯示 | 更好的 UX，字元逐漸顯示 |

---

## Phase 1：後端 — 新增 `search_components` Tool

### Task 1：建立 `search_components` tool 檔案

**Files:**
- Create: `Taipei-City-Dashboard-BE/app/services/ai/tools/search.go`

**Step 1：建立 tool 檔案**

```go
package tools

import (
	"TaipeiCityDashboardBE/app/models"
	"context"
	"encoding/json"
	"fmt"
)

// SearchArgs defines the arguments for the search_components tool
type SearchArgs struct {
	Query string  `json:"query"`
	Limit int     `json:"limit"`
	Score float64 `json:"score"`
}

// SearchComponents queries Qdrant vector DB and returns matching dashboard components
func SearchComponents(ctx context.Context, args string) (string, error) {
	var params SearchArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	if params.Limit <= 0 || params.Limit > 20 {
		params.Limit = 10
	}
	if params.Score <= 0 || params.Score > 1 {
		params.Score = 0.78
	}

	results, err := models.GetComponentsByVector(params.Query, params.Limit, params.Score)
	if err != nil {
		return "", fmt.Errorf("搜尋元件失敗: %v", err)
	}
	if len(results) == 0 {
		return "找不到相關元件，請嘗試不同的關鍵字。", nil
	}

	type ComponentResult struct {
		ID    interface{} `json:"id"`
		Index string      `json:"index"`
		Name  string      `json:"name"`
		City  string      `json:"city"`
		Score float64     `json:"score"`
	}

	output := make([]ComponentResult, 0, len(results))
	for _, r := range results {
		output = append(output, ComponentResult{
			ID:    r["id"],
			Index: fmt.Sprintf("%v", r["index"]),
			Name:  fmt.Sprintf("%v", r["name"]),
			City:  fmt.Sprintf("%v", r["city"]),
			Score: r["score"].(float64),
		})
	}

	b, _ := json.MarshalIndent(output, "", "  ")
	return fmt.Sprintf("找到 %d 個相關元件：\n%s", len(output), string(b)), nil
}
```

**Step 2：在 `registry.go` 的 `init()` 中登錄此 tool**

修改 `Taipei-City-Dashboard-BE/app/services/ai/tools/registry.go`：

```go
func init() {
	Register("get_current_time", GetCurrentTime)
	Register("get_population_summary", GetPopulationSummary)
	Register("search_components", SearchComponents)  // 新增這行
}
```

**Step 3：確認 `models.GetComponentsByVector` 是否已存在**

查看 `Taipei-City-Dashboard-BE/app/models/qdrant.go`，確認：
- 若函式存在且回傳 `[]map[string]interface{}`，直接使用
- 若不存在，在 `qdrant.go` 中新增：

```go
// GetComponentsByVector queries Qdrant and returns matching components
func GetComponentsByVector(query string, limit int, score float64) ([]map[string]interface{}, error) {
	// 重用現有的 GetComponentByQueryVector 邏輯
	// 參考 app/controllers/qdrant.go 的實作
}
```

> 若 `qdrant.go` 中已有類似函式（如 controller 直接呼叫 Qdrant HTTP API），將相同邏輯提取成 model 函式即可。

**Step 4：編譯確認無誤**

```bash
cd Taipei-City-Dashboard-BE
go build ./...
```
Expected: 無 error

**Step 5：Commit**

```bash
git add app/services/ai/tools/search.go app/services/ai/tools/registry.go
git commit -m "feat(ai): add search_components tool for LLM-driven component discovery"
```

---

### Task 2：撰寫 AI System Prompt（後端）

**Files:**
- Modify: `Taipei-City-Dashboard-BE/app/services/ai/ai_service.go`

目前 `injectInstructions()` 只注入工具使用規則。需加入角色定義與行為準則。

**Step 1：在 `ai_service.go` 的 `injectInstructions()` 中加入 system prompt**

找到 `injectInstructions()` 方法，在 `instruction` 變數前加入 `rolePrompt`：

```go
func (s *aiSession) injectInstructions() {
	toolNames := ""
	for i, t := range s.callOpts.Tools {
		if i > 0 { toolNames += ", " }
		toolNames += t.Function.Name
	}

	// 角色定義（新增）
	rolePrompt := `你是「臺北城市儀表板小幫手」，專門協助使用者探索台北市與新北市的開放資料儀表板。
請遵守以下規則：
- 所有回覆使用繁體中文
- 當使用者詢問城市數據、統計資料或想找特定主題的資料時，優先使用 search_components 工具搜尋相關元件
- 搜尋到元件後，用條列方式呈現，說明每個元件的用途
- 只回答與台北市、新北市城市治理、公共數據相關的問題
- 不支援一般聊天、創作或與城市資料無關的問答`

	instruction := fmt.Sprintf("\n\n工具使用規則：\n1. 只能使用：[%s]\n2. 不可巢狀呼叫工具\n3. 參數必須是字面值\n4. 有依賴關係的工具需依序呼叫\n5. 無法呼叫工具時用文字回應", toolNames)

	fullInstruction := rolePrompt + instruction  // 合併

	s.currentMessages = make([]llms.MessageContent, 0)
	merged := false
	for _, m := range s.req.Messages {
		if m.Role == llms.ChatMessageTypeSystem && !merged {
			s.currentMessages = append(s.currentMessages, mergeSystemMsg(m, "\n\n"+fullInstruction))
			merged = true
		} else {
			s.currentMessages = append(s.currentMessages, m)
		}
	}

	if !merged {
		s.currentMessages = append([]llms.MessageContent{{
			Role: llms.ChatMessageTypeSystem,
			Parts: []llms.ContentPart{llms.TextContent{Text: fullInstruction}},
		}}, s.currentMessages...)
	}
}
```

**Step 2：編譯確認**

```bash
go build ./...
```

**Step 3：Commit**

```bash
git add app/services/ai/ai_service.go
git commit -m "feat(ai): inject role-aware system prompt for Taipei Dashboard assistant"
```

---

## Phase 2：前端 — ChatStore AI 對話整合

### Task 3：chatStore 新增 `sendAIChat()` 方法

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/store/chatStore.js`

**Step 1：在 `chatStore.js` 中新增 `sendAIChat` 方法**

在 `saveChatLog` 函式之後、`return` 之前，新增：

```javascript
// AI 對話模式：呼叫 TWCC AI API
const sendAIChat = async (userText) => {
  // 1. 先顯示使用者訊息
  chatData.value.push({
    id: chatData.value.length + 1,
    isDefault: false,
    role: 'user',
    content: userText,
  });

  // 2. 顯示 loading 占位訊息
  const loadingId = chatData.value.length + 1;
  chatData.value.push({
    id: loadingId,
    isDefault: false,
    role: 'bot',
    loading: true,
    content: '',
  });

  try {
    // 3. 建構 messages：只傳最近 10 輪對話（避免 token 超量）
    const recentMessages = chatData.value
      .filter(m => !m.isDefault && !m.loading && (m.role === 'user' || m.role === 'bot') && m.content)
      .slice(-10)
      .map(m => ({
        role: m.role === 'bot' ? 'assistant' : 'user',
        content: m.content,
      }));

    // 4. 呼叫後端 AI API
    const response = await http.post('/ai/chat/twai', {
      messages: recentMessages,
      tool_choice: 'auto',
    });

    const aiAnswer = response.data?.data?.content || '抱歉，無法取得回應。';
    const toolUsed = response.data?.data?.tool_used || false;

    // 5. 移除 loading 訊息，加入真實回應
    const idx = chatData.value.findIndex(m => m.id === loadingId);
    if (idx !== -1) {
      chatData.value.splice(idx, 1, {
        id: loadingId,
        isDefault: false,
        role: 'bot',
        content: aiAnswer,
        toolUsed,
      });
    }
  } catch (error) {
    console.error('sendAIChat error:', error);
    const idx = chatData.value.findIndex(m => m.id === loadingId);
    if (idx !== -1) {
      chatData.value.splice(idx, 1, {
        id: loadingId,
        isDefault: false,
        role: 'bot',
        content: '抱歉，AI 服務暫時無法使用，請稍後再試。',
      });
    }
  }
};
```

**Step 2：將 `sendAIChat` 加入 return 物件**

```javascript
return { chatData, addChatData, addQueryData, saveChatLog, sendAIChat }
```

**Step 3：確認可正常引入（無語法錯誤）**

```bash
cd Taipei-City-Dashboard-FE
npm run lint
```
Expected: no errors

**Step 4：Commit**

```bash
git add src/store/chatStore.js
git commit -m "feat(chat): add sendAIChat() method to connect TWCC AI chat API"
```

---

### Task 4：ChatBox.vue 加入模式切換與 AI 對話 UI

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/components/dialogs/ChatBox.vue`

**Step 1：在 `<script setup>` 區塊加入 mode 狀態與 sendAIChat 引入**

在現有 `import` 區塊後加入：

```javascript
const { addChatData, addQueryData, saveChatLog, sendAIChat } = chatStore;
const chatMode = ref('vector'); // 'vector' | 'ai'
```

（同時移除原本的 `const { addChatData, addQueryData, saveChatLog } = chatStore;` 改成上面這行）

**Step 2：修改 `sendBtnHandler`，依模式決定呼叫哪個方法**

原本：
```javascript
const sendBtnHandler = (text) => {
  if (!text.trim()) return;
  addQueryData({ role: 'user', content: text });
  userMessage.value = '';
};
```

改成：
```javascript
const sendBtnHandler = (text) => {
  if (!text.trim()) return;
  if (chatMode.value === 'ai') {
    sendAIChat(text);
  } else {
    addQueryData({ role: 'user', content: text });
  }
  userMessage.value = '';
};
```

**Step 3：在 Header 區塊加入模式切換按鈕**

原本 `<div class="header">` 內只有 `<h3>`，改成：

```html
<div class="header">
  <h3>臺北城市儀表板小幫手</h3>
  <div class="mode-toggle">
    <button
      :class="{ active: chatMode === 'vector' }"
      @click="chatMode = 'vector'"
    >
      快速推薦
    </button>
    <button
      :class="{ active: chatMode === 'ai' }"
      @click="chatMode = 'ai'"
    >
      AI 對話
    </button>
  </div>
</div>
```

**Step 4：在 bot 訊息區塊加入 loading 狀態顯示**

在 `<div v-if="chat.role === 'bot'" class="bot">` 的 `.content` 內，`message--bubble` 之前加入：

```html
<div v-if="chat.loading" class="message--bubble loading-bubble">
  <p>思考中...</p>
</div>
```

**Step 5：在 `<style>` 區塊加入新樣式**

```scss
// 模式切換
.mode-toggle {
  display: flex;
  gap: 0.25rem;
  margin-top: 0.5rem;

  button {
    flex: 1;
    padding: 4px 8px;
    border-radius: 8px;
    border: 1px solid $border-color;
    background: transparent;
    color: $white;
    font-size: 12px;
    cursor: pointer;

    &.active {
      background: $border-color;
    }
    &:hover {
      filter: brightness(1.3);
    }
  }
}

// Loading 動畫
.loading-bubble {
  opacity: 0.6;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
```

**Step 6：確認無語法錯誤**

```bash
npm run lint
```

**Step 7：Commit**

```bash
git add src/components/dialogs/ChatBox.vue
git commit -m "feat(chat): add AI chat mode toggle and loading state to ChatBox"
```

---

## Phase 3：前端 SSE 串流顯示

### Task 5：chatStore 新增 `sendAIChatStream()` 串流方法

**Files:**
- Modify: `Taipei-City-Dashboard-FE/src/store/chatStore.js`
- Modify: `Taipei-City-Dashboard-FE/src/components/dialogs/ChatBox.vue`

> 此 Phase 需後端 `stream: true` 參數配合。後端已支援 SSE，只需前端實作。

**Step 1：在 chatStore.js 新增 `sendAIChatStream` 方法**

在 `sendAIChat` 之後新增：

```javascript
// AI 串流模式
const sendAIChatStream = async (userText) => {
  chatData.value.push({
    id: chatData.value.length + 1,
    isDefault: false,
    role: 'user',
    content: userText,
  });

  const streamId = chatData.value.length + 1;
  chatData.value.push({
    id: streamId,
    isDefault: false,
    role: 'bot',
    content: '',
    streaming: true,
  });

  const recentMessages = chatData.value
    .filter(m => !m.isDefault && !m.streaming && (m.role === 'user' || m.role === 'bot') && m.content)
    .slice(-10)
    .map(m => ({ role: m.role === 'bot' ? 'assistant' : 'user', content: m.content }));

  try {
    const authStore = useAuthStore();
    const response = await fetch(
      `${import.meta.env.VITE_API_URL}/ai/chat/twai`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authStore.token}`,
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          messages: recentMessages,
          stream: true,
          tool_choice: 'auto',
        }),
      }
    );

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // 保留不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const chunk = line.slice(6);
          if (chunk === '[DONE]') continue;
          // 直接累加串流文字
          const idx = chatData.value.findIndex(m => m.id === streamId);
          if (idx !== -1) {
            chatData.value[idx] = {
              ...chatData.value[idx],
              content: chatData.value[idx].content + chunk,
            };
          }
        }
      }
    }
  } catch (error) {
    console.error('sendAIChatStream error:', error);
  } finally {
    // 標記串流結束
    const idx = chatData.value.findIndex(m => m.id === streamId);
    if (idx !== -1) {
      chatData.value[idx] = { ...chatData.value[idx], streaming: false };
    }
  }
};
```

**Step 2：將 `sendAIChatStream` 加入 return**

```javascript
return { chatData, addChatData, addQueryData, saveChatLog, sendAIChat, sendAIChatStream }
```

**Step 3：ChatBox.vue 引入並在 AI 模式下使用串流**

在 ChatBox.vue `<script setup>` 更新引入：

```javascript
const { addChatData, addQueryData, saveChatLog, sendAIChat, sendAIChatStream } = chatStore;
```

更新 `sendBtnHandler`：

```javascript
const sendBtnHandler = (text) => {
  if (!text.trim()) return;
  if (chatMode.value === 'ai') {
    sendAIChatStream(text); // 改用串流版本
  } else {
    addQueryData({ role: 'user', content: text });
  }
  userMessage.value = '';
};
```

在 `message--bubble` 的 `<p>` 標籤加入串流游標效果：

```html
<div v-if="chat.content" class="message--bubble">
  <p>{{ chat.content }}<span v-if="chat.streaming" class="cursor">▌</span></p>
</div>
```

在 `<style>` 新增游標動畫：

```scss
.cursor {
  animation: blink 0.7s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
```

**Step 4：確認無語法錯誤**

```bash
npm run lint
```

**Step 5：Commit**

```bash
git add src/store/chatStore.js src/components/dialogs/ChatBox.vue
git commit -m "feat(chat): add SSE streaming display for AI chat responses"
```

---

## Phase 4（選配）：新增更多工具

### Task 6：新增 `get_youbike_availability` 工具

**Files:**
- Create: `Taipei-City-Dashboard-BE/app/services/ai/tools/citydata.go`

**Step 1：建立 citydata.go**

```go
package tools

import (
	"TaipeiCityDashboardBE/app/models"
	"context"
	"encoding/json"
	"fmt"
)

func init() {
	// 追加在 registry.go 之後，或直接在此 init 中登錄
}

type YouBikeArgs struct {
	District string `json:"district"` // 行政區（可選）
	Limit    int    `json:"limit"`
}

// GetYouBikeAvailability queries current YouBike station availability
func GetYouBikeAvailability(ctx context.Context, args string) (string, error) {
	var params YouBikeArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	if params.Limit <= 0 || params.Limit > 20 {
		params.Limit = 10
	}

	query := models.DBDashboard.Table("youbike_availability") // 資料表名稱需確認
	if params.District != "" {
		query = query.Where("district = ?", params.District)
	}
	query = query.Order("available_bikes DESC").Limit(params.Limit)

	var results []map[string]interface{}
	if err := query.Find(&results).Error; err != nil {
		return "", fmt.Errorf("查詢 YouBike 資料失敗: %v", err)
	}

	b, _ := json.MarshalIndent(results, "", "  ")
	return fmt.Sprintf("YouBike 站點可借數量（前 %d 名）：\n%s", params.Limit, string(b)), nil
}
```

> **注意：** 執行前需先確認 DB 中實際的 YouBike 資料表名稱（`\dt` in psql 查詢）

**Step 2：在 registry.go 中登錄**

```go
Register("get_youbike_availability", GetYouBikeAvailability)
```

**Step 3：Commit**

```bash
git add app/services/ai/tools/citydata.go app/services/ai/tools/registry.go
git commit -m "feat(ai): add get_youbike_availability tool"
```

---

## 手動測試 Checklist

完成各 Phase 後，請手動驗證：

### Phase 1 驗證
- [ ] `POST /api/v1/ai/chat/twai` 帶入 `search_components` 工具定義，確認 LLM 會呼叫
- [ ] 查詢「台北市空氣品質」，確認回傳相關元件列表
- [ ] 查詢「今天幾號」，確認 `get_current_time` 仍正常

### Phase 2 驗證
- [ ] ChatBox 右上角顯示「快速推薦」/「AI 對話」切換按鈕
- [ ] 切換到「AI 對話」模式後輸入問題，確認呼叫 `/api/v1/ai/chat/twai`
- [ ] 回應中出現 bot bubble 顯示 AI 回覆
- [ ] 切換回「快速推薦」，確認仍呼叫向量搜尋並顯示元件表格

### Phase 3 驗證
- [ ] AI 對話模式下，文字逐漸顯示（串流效果）
- [ ] 顯示游標 `▌` 閃爍直到回應完成
- [ ] 串流過程中 chatArea 自動捲動

---

## 相依性與注意事項

1. **後端需先部署 Phase 1** 才能使前端 AI 對話包含 `search_components` 能力
2. **TWCC_API_KEY** 必須在 `.env` 中正確設定，否則所有 AI 對話會失敗（`38c5ee00-...` 為示範值，請換成正式 key）
3. **串流（Phase 3）** 需前端能存取 `authStore.token`，確認 user 已登入
4. **YouBike 工具（Phase 4）** 需先確認實際 DB 資料表名稱再調整 SQL
5. 若 `models.GetComponentsByVector` 函式不存在，需先從 `controllers/qdrant.go` 提取邏輯

---

*計畫撰寫日期：2026-04-13*
