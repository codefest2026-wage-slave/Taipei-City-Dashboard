<!-- L-01-1 複查優先佇列引擎 — 雙北雇主風險排序 + AI 解釋面板 + 權重滑桿 -->
<template>
  <div class="rpr-root">
    <!-- 權重滑桿（控制動態 re-rank） -->
    <div class="rpr-controls">
      <div class="rpr-slider">
        <label>違規頻率 <strong>{{ wFreq }}</strong></label>
        <input type="range" min="0" max="100" v-model.number="wFreq" />
      </div>
      <div class="rpr-slider">
        <label>距上次違規 <strong>{{ wRecency }}</strong></label>
        <input type="range" min="0" max="100" v-model.number="wRecency" />
      </div>
      <div class="rpr-slider">
        <label>員工規模 <strong>{{ wScale }}</strong></label>
        <input type="range" min="0" max="100" v-model.number="wScale" />
      </div>
      <div class="rpr-slider">
        <label>違規嚴重性 <strong>{{ wSeverity }}</strong></label>
        <input type="range" min="0" max="100" v-model.number="wSeverity" />
      </div>
    </div>

    <!-- 排名清單 -->
    <div class="rpr-list-wrap">
      <div class="rpr-list">
        <div
          v-for="(row, idx) in rankedRows"
          :key="row.company_name + idx"
          :class="['rpr-row', { selected: selectedIdx === idx }]"
          @click="select(idx)"
        >
          <div class="rpr-rank">{{ idx + 1 }}</div>
          <div class="rpr-info">
            <div class="rpr-name">
              <span :class="['rpr-city-tag', row.src_city || 'taipei']">{{ row.city }}</span>
              {{ row.company_name }}
            </div>
            <div class="rpr-meta">
              {{ row.industry }} · 違規 {{ row.total }} 件 · 距上次 {{ row.days_since || '?' }} 天
              <span v-if="row.disasters > 0" class="rpr-disaster"> · 職災 {{ row.disasters }}</span>
            </div>
          </div>
          <div class="rpr-score" :style="{ background: scoreColor(row.dynamic_score) }">
            {{ row.dynamic_score.toFixed(1) }}
          </div>
        </div>
      </div>
    </div>

    <!-- AI 解釋面板 -->
    <div class="rpr-ai-panel" v-if="selected">
      <div class="rpr-ai-head">
        <span class="material-icons">psychology</span>
        AI 排名解釋 — {{ selected.company_name }}
        <button
          class="rpr-ai-refresh"
          v-if="isLoggedIn && (explanation || error)"
          @click="fetchExplanation(selected, true)"
          :disabled="loading"
          title="重新產生"
        >
          <span class="material-icons">refresh</span>
        </button>
        <button class="rpr-ai-close" @click="closePanel" title="關閉解釋">
          <span class="material-icons">close</span>
        </button>
      </div>
      <div class="rpr-ai-body">
        <div v-if="!isLoggedIn" class="rpr-ai-login">
          <span class="material-icons">lock</span>
          AI 解釋需登入才能使用，請先登入後再點擊雇主。
        </div>
        <div v-else-if="!explanation && !loading && !error" class="rpr-ai-hint">
          <button class="rpr-ai-cta" @click="fetchExplanation(selected)">
            <span class="material-icons">auto_awesome</span> 產生 AI 解釋
          </button>
        </div>
        <div v-else-if="loading" class="rpr-ai-loading">
          <span class="material-icons rpr-spin">progress_activity</span> 產生中…
        </div>
        <div v-else-if="error" class="rpr-ai-error">{{ error }}</div>
        <div v-else-if="explanation" class="rpr-ai-text">{{ explanation }}</div>
      </div>
      <div class="rpr-disclaimer">
        ⓘ 估算工具，建議搭配實地確認；加權公式為示範性設計，可由勞動局主管調整。
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import http from "../../router/axios";
import { useAuthStore } from "../../store/authStore";

const props = defineProps({
  series: Array,
  chart_config: Object,
});

const authStore = useAuthStore();
const isLoggedIn = computed(() => Boolean(authStore.token && authStore.user?.user_id));

const wFreq = ref(40);
const wRecency = ref(30);
const wScale = ref(20);
const wSeverity = ref(10);

const selectedIdx = ref(null);
const explanation = ref("");
const loading = ref(false);
const error = ref("");
const explainCache = new Map();

function closePanel() {
  selectedIdx.value = null;
  explanation.value = "";
  error.value = "";
}

// Parse JSON-packed x_axis from series
const allRows = computed(() => {
  return (props.series || []).flatMap((g) =>
    (g.data || []).map((it) => {
      let parsed = {};
      try {
        parsed = typeof it.x === "string" ? JSON.parse(it.x) : it.x || {};
      } catch (e) {
        parsed = { company_name: String(it.x || "?") };
      }
      return { ...parsed, base_score: Number(it.y) || 0 };
    }),
  );
});

// Re-rank based on current sliders (normalized to original component weights)
const rankedRows = computed(() => {
  const total = wFreq.value + wRecency.value + wScale.value + wSeverity.value || 1;
  return allRows.value
    .map((r) => {
      const freqPart = Math.min((r.total || 0) / 10, 1) * (wFreq.value * 100 / total);
      const recencyPart = Math.max(0, 1 - (r.days_since || 730) / 730) * (wRecency.value * 100 / total);
      const scalePart = Math.min((r.capital || 0) / 50_000_000, 1) * (wScale.value * 100 / total);
      const sevPart =
        Math.min(((r.safety || 0) * 3 + (r.labor || 0) * 2 + (r.gender || 0) * 1) / 30, 1)
        * (wSeverity.value * 100 / total);
      const disasterBonus = (r.disasters || 0) * 5;
      return { ...r, dynamic_score: freqPart + recencyPart + scalePart + sevPart + disasterBonus };
    })
    .sort((a, b) => b.dynamic_score - a.dynamic_score);
});

const selected = computed(() =>
  selectedIdx.value !== null ? rankedRows.value[selectedIdx.value] : null,
);

function scoreColor(s) {
  if (s >= 90) return "#dc2626";
  if (s >= 70) return "#ea580c";
  if (s >= 50) return "#f59e0b";
  if (s >= 30) return "#84cc16";
  return "#22c55e";
}

function select(idx) {
  selectedIdx.value = idx;
  // 訪客只開面板顯示登入提示，不打 API
  if (!isLoggedIn.value) {
    explanation.value = "";
    error.value = "";
    return;
  }
  // 已登入：若已有快取就直接顯示，否則等使用者按「產生 AI 解釋」
  const row = rankedRows.value[idx];
  const key = row.company_name + (row.src_city || "");
  if (explainCache.has(key)) {
    explanation.value = explainCache.get(key);
    error.value = "";
  } else {
    explanation.value = "";
    error.value = "";
  }
}

async function fetchExplanation(row, force = false) {
  if (!row) return;
  if (!isLoggedIn.value) return;
  const key = row.company_name + (row.src_city || "");
  if (!force && explainCache.has(key)) {
    explanation.value = explainCache.get(key);
    error.value = "";
    return;
  }
  loading.value = true;
  error.value = "";
  explanation.value = "";
  const ctx = row.src_city === "newtaipei" ? "新北市製造業" : "臺北市服務業";
  const focus =
    row.src_city === "newtaipei"
      ? "請聚焦職業安全（機械、化學、墜落）與未足額投保等製造業常見違規。"
      : "請聚焦工時超時、未給加班費等服務業常見違規。";
  const prompt = `你是雙北勞動檢查員的智能助理。以下是某雇主的結構化風險特徵，請以 150 字內勞檢員視角的口吻解釋為什麼這家雇主排在本季複查優先清單，並指出最需要重點稽查的 1-2 個項目。${focus}

公司：${row.company_name}（行業：${row.industry}）
所在：${ctx}
總違規次數：${row.total}（勞基法 ${row.labor}，職安法 ${row.safety}，性平法 ${row.gender}）
距上次違規天數：${row.days_since}
累計罰款：${row.fine ? Number(row.fine).toLocaleString() : "未知"} 元
員工規模代理（資本額）：${row.capital ? (row.capital / 10000).toLocaleString() + " 萬元" : "未知"}
重大職災紀錄：${row.disasters} 件（死亡 ${row.deaths || 0}，受傷 ${row.injuries || 0}）

直接以白話寫一段建議，不要重複數字，只強調最關鍵的 1-2 個風險。`;
  try {
    const resp = await http.post("/ai/chat/twai", {
      messages: [
        { role: "system", content: "你是雙北勞動檢查員的智能助理。" },
        { role: "user", content: prompt },
      ],
      max_new_tokens: 300,
      temperature: 0.3,
    });
    const text =
      resp.data?.data?.message?.content ||
      resp.data?.message?.content ||
      resp.data?.data?.content ||
      resp.data?.content ||
      JSON.stringify(resp.data);
    explanation.value = String(text).trim();
    explainCache.set(key, explanation.value);
  } catch (e) {
    error.value = `AI 解釋失敗：${e?.response?.data?.message || e.message || "未知錯誤"}`;
  } finally {
    loading.value = false;
  }
}

// Reset when data switches (e.g. taipei ↔ metrotaipei)
watch(() => props.series, () => {
  selectedIdx.value = null;
  explanation.value = "";
  error.value = "";
});
</script>

<style scoped>
.rpr-root {
  display: flex; flex-direction: column; height: 100%;
  font-size: 0.85rem; color: var(--color-component-text, #cdd5da);
}
.rpr-controls {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem 1rem;
  padding: 0.5rem 0.75rem; border-bottom: 1px solid rgba(255,255,255,0.08);
}
.rpr-slider label {
  display: flex; justify-content: space-between; font-size: 0.72rem;
  margin-bottom: 0.15rem; color: #9aa3ad;
}
.rpr-slider label strong { color: #f8fafc; font-weight: 600; }
.rpr-slider input[type="range"] { width: 100%; accent-color: #ea580c; }

.rpr-list-wrap { flex: 1; min-height: 0; overflow-y: auto; padding: 0.25rem 0; }
.rpr-list { display: flex; flex-direction: column; }
.rpr-row {
  display: grid; grid-template-columns: 28px 1fr 56px;
  gap: 0.5rem; align-items: center;
  padding: 0.4rem 0.75rem; cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  transition: background 0.15s;
}
.rpr-row:hover { background: rgba(234, 88, 12, 0.08); }
.rpr-row.selected { background: rgba(234, 88, 12, 0.18); }
.rpr-rank {
  text-align: center; font-weight: 700; color: #94a3b8;
  font-variant-numeric: tabular-nums;
}
.rpr-info { min-width: 0; }
.rpr-name { font-weight: 600; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rpr-meta { font-size: 0.7rem; color: #94a3b8; margin-top: 0.1rem; }
.rpr-disaster { color: #fca5a5; font-weight: 600; }
.rpr-city-tag {
  display: inline-block; padding: 0 0.35rem; margin-right: 0.35rem;
  font-size: 0.65rem; border-radius: 3px; font-weight: 600;
}
.rpr-city-tag.taipei { background: #b45309; color: #fff; }
.rpr-city-tag.newtaipei { background: #1d4ed8; color: #fff; }
.rpr-score {
  text-align: center; padding: 0.25rem 0; border-radius: 4px;
  font-weight: 700; color: #fff; font-variant-numeric: tabular-nums;
}

.rpr-ai-panel {
  border-top: 2px solid rgba(234, 88, 12, 0.4);
  padding: 0.5rem 0.75rem; background: rgba(0,0,0,0.2);
  max-height: 220px; overflow-y: auto;
}
.rpr-ai-head {
  display: flex; align-items: center; gap: 0.4rem;
  font-weight: 700; color: #fb923c; margin-bottom: 0.35rem;
  font-size: 0.8rem;
}
.rpr-ai-head .material-icons { font-size: 18px; }
.rpr-ai-refresh {
  margin-left: auto; background: transparent; border: none; cursor: pointer;
  color: #fb923c; padding: 2px;
}
.rpr-ai-refresh:disabled { opacity: 0.4; }
.rpr-ai-close {
  background: transparent; border: none; cursor: pointer;
  color: #94a3b8; padding: 2px;
}
.rpr-ai-close:hover { color: #f8fafc; }
.rpr-ai-cta {
  display: inline-flex; align-items: center; gap: 0.35rem;
  background: linear-gradient(135deg, #ea580c, #c2410c);
  color: #fff; border: none; padding: 0.4rem 0.8rem; border-radius: 4px;
  font-weight: 600; cursor: pointer; font-size: 0.78rem;
}
.rpr-ai-cta:hover { background: linear-gradient(135deg, #f97316, #ea580c); }
.rpr-ai-cta .material-icons { font-size: 16px; }
.rpr-ai-login {
  display: flex; align-items: center; gap: 0.4rem;
  color: #94a3b8; font-size: 0.78rem; padding: 0.5rem;
  background: rgba(245,158,11,0.08); border-radius: 4px;
}
.rpr-ai-login .material-icons { font-size: 18px; color: #f59e0b; }
.rpr-ai-text { font-size: 0.78rem; line-height: 1.55; color: #e2e8f0; white-space: pre-wrap; }
.rpr-ai-loading { color: #94a3b8; display: flex; align-items: center; gap: 0.4rem; }
.rpr-ai-error { color: #fca5a5; font-size: 0.78rem; }
.rpr-ai-hint { color: #64748b; font-size: 0.78rem; }
.rpr-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.rpr-disclaimer {
  margin-top: 0.4rem; font-size: 0.65rem; color: #64748b;
  border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 0.3rem;
}
</style>
