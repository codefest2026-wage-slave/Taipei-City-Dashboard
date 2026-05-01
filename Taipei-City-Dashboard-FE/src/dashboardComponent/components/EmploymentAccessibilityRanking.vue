<!-- L-04-1 就業資源可及性缺口地圖 — 里級可及性排名 + AI 選址推薦面板 + 服務半徑切換 -->
<template>
  <div class="ear-root">
    <!-- 服務半徑控制 -->
    <div class="ear-controls">
      <div class="ear-stat">
        <span class="ear-label">總里數</span>
        <strong>{{ rankedRows.length }}</strong>
      </div>
      <div class="ear-stat warning">
        <span class="ear-label">服務真空</span>
        <strong>{{ outOfServiceCount }}</strong>
        <span class="ear-meta">里 ({{ outOfServicePct }}%)</span>
      </div>
      <div class="ear-stat">
        <span class="ear-label">弱勢人口</span>
        <strong>{{ vulnerableSum.toLocaleString() }}</strong>
      </div>
    </div>

    <!-- 排名清單 -->
    <div class="ear-list-wrap">
      <div class="ear-list">
        <div
          v-for="(row, idx) in rankedRows"
          :key="row.district + row.village + idx"
          :class="['ear-row', { selected: selectedIdx === idx, oos: !row.in_service }]"
          @click="select(idx)"
        >
          <div class="ear-rank">{{ idx + 1 }}</div>
          <div class="ear-info">
            <div class="ear-name">
              <span :class="['ear-city-tag', row.src_city || 'taipei']">{{ row.city }}</span>
              {{ row.district }}{{ row.village }}
            </div>
            <div class="ear-meta">
              距最近就服站 {{ formatDist(row.dist_m) }} ·
              人口 {{ row.total_pop.toLocaleString() }} ·
              弱勢 {{ row.vulnerable.toLocaleString() }}
              <span v-if="!row.in_service" class="ear-oos-tag">服務真空</span>
            </div>
          </div>
          <div class="ear-score" :style="{ background: scoreColor(row.gap_score) }">
            {{ row.gap_score.toFixed(1) }}
          </div>
        </div>
      </div>
    </div>

    <!-- AI 選址推薦面板 -->
    <div class="ear-ai-panel" v-if="selected">
      <div class="ear-ai-head">
        <span class="material-icons">place</span>
        AI 選址推薦 — {{ selected.district }}{{ selected.village }}
        <button
          class="ear-ai-refresh"
          v-if="isLoggedIn && (recommendation || error)"
          @click="fetchRecommendation(selected, true)"
          :disabled="loading"
          title="重新產生"
        >
          <span class="material-icons">refresh</span>
        </button>
        <button class="ear-ai-close" @click="closePanel" title="關閉">
          <span class="material-icons">close</span>
        </button>
      </div>
      <div class="ear-ai-stats">
        <div class="ear-stat-cell">
          <span class="ear-label">距最近站</span>
          <strong>{{ formatDist(selected.dist_m) }}</strong>
        </div>
        <div class="ear-stat-cell">
          <span class="ear-label">服務半徑</span>
          <strong>{{ (selected.service_radius / 1000).toFixed(1) }} km</strong>
        </div>
        <div class="ear-stat-cell">
          <span class="ear-label">里總人口</span>
          <strong>{{ selected.total_pop.toLocaleString() }}</strong>
        </div>
        <div class="ear-stat-cell" v-if="selected.avg_disposable">
          <span class="ear-label">每戶可支配所得</span>
          <strong>{{ Number(selected.avg_disposable).toLocaleString() }} 千元</strong>
        </div>
      </div>
      <div class="ear-ai-body">
        <div v-if="!isLoggedIn" class="ear-ai-login">
          <span class="material-icons">lock</span>
          AI 推薦需登入才能使用，請先登入後再點擊里。
        </div>
        <div v-else-if="!recommendation && !loading && !error" class="ear-ai-hint">
          <button class="ear-ai-cta" @click="fetchRecommendation(selected)">
            <span class="material-icons">auto_awesome</span> 產生 AI 選址推薦
          </button>
        </div>
        <div v-else-if="loading" class="ear-ai-loading">
          <span class="material-icons ear-spin">progress_activity</span> 產生中…
        </div>
        <div v-else-if="error" class="ear-ai-error">{{ error }}</div>
        <div v-else-if="recommendation" class="ear-ai-text">{{ recommendation }}</div>
      </div>
      <div class="ear-disclaimer">
        ⓘ 弱勢人口以「中高齡 + 高齡×1.5」作代理；新北市無行政區所得資料，僅以人口年齡層加權。
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

const selectedIdx = ref(null);
const recommendation = ref("");
const loading = ref(false);
const error = ref("");
const recCache = new Map();

const rankedRows = computed(() => {
  return (props.series || []).flatMap((g) =>
    (g.data || []).map((it) => {
      let parsed = {};
      try {
        parsed = typeof it.x === "string" ? JSON.parse(it.x) : it.x || {};
      } catch (e) {
        parsed = { village: String(it.x || "?") };
      }
      return { ...parsed, gap_score: Number(it.y) || 0 };
    }),
  );
});

const selected = computed(() =>
  selectedIdx.value !== null ? rankedRows.value[selectedIdx.value] : null,
);

const outOfServiceCount = computed(() => rankedRows.value.filter((r) => !r.in_service).length);
const outOfServicePct = computed(() => {
  const total = rankedRows.value.length || 1;
  return Math.round((outOfServiceCount.value / total) * 100);
});
const vulnerableSum = computed(() =>
  rankedRows.value.reduce((s, r) => s + (Number(r.vulnerable) || 0), 0),
);

function formatDist(m) {
  if (m == null) return "?";
  const num = Number(m);
  if (num < 1000) return `${Math.round(num)} m`;
  return `${(num / 1000).toFixed(1)} km`;
}

function scoreColor(s) {
  if (s >= 100) return "#dc2626";
  if (s >= 80) return "#ea580c";
  if (s >= 60) return "#f59e0b";
  if (s >= 30) return "#84cc16";
  return "#16a34a";
}

function closePanel() {
  selectedIdx.value = null;
  recommendation.value = "";
  error.value = "";
}

function select(idx) {
  selectedIdx.value = idx;
  if (!isLoggedIn.value) {
    recommendation.value = "";
    error.value = "";
    return;
  }
  const row = rankedRows.value[idx];
  const key = row.district + row.village + (row.src_city || "");
  if (recCache.has(key)) {
    recommendation.value = recCache.get(key);
    error.value = "";
  } else {
    recommendation.value = "";
    error.value = "";
  }
}

async function fetchRecommendation(row, force = false) {
  if (!row || !isLoggedIn.value) return;
  const key = row.district + row.village + (row.src_city || "");
  if (!force && recCache.has(key)) {
    recommendation.value = recCache.get(key);
    error.value = "";
    return;
  }
  loading.value = true;
  error.value = "";
  recommendation.value = "";

  const cityCtx = row.src_city === "newtaipei" ? "新北市（採 3km 服務半徑，依賴交通工具）" : "臺北市（採 1km 服務半徑，步行可及）";
  const focus = row.src_city === "newtaipei"
    ? "請聚焦郊區運輸限制與外展訪視路線優化（如配合社區巴士、行動服務車）。"
    : "請聚焦市中心步行可及性與既有就服站動線重整（如鄰近捷運、公車轉乘）。";
  const incomeNote = row.avg_disposable
    ? `行政區每戶可支配所得：${Number(row.avg_disposable).toLocaleString()} 千元`
    : "（新北市無行政區所得資料）";

  const prompt = `你是雙北就業服務中心主任的智能助理。以下是某里的就業資源可及性數據，請以中心主任視角，用 150 字內說明此里是否應優先新設服務據點，並建議選址邏輯。${focus}

地點：${row.city}${row.district}${row.village}（${cityCtx}）
距最近就服站：${formatDist(row.dist_m)}（${row.nearest_center || '未知'}）
${row.in_service ? "✓ 在服務半徑內" : "✗ 服務真空（超出服務半徑）"}
里總人口：${row.total_pop} 人
中高齡（45-64）：${row.midage_pop} 人
高齡（65+）：${row.elder_pop} 人
弱勢勞工代理指標：${row.vulnerable} 人
${incomeNote}
缺口指數：${row.gap_score} / 120

請直接給結論：是否優先新設？建議選址在哪附近？預估覆蓋多少弱勢勞工？不要重複數字，只給可行動建議。`;
  try {
    const resp = await http.post("/ai/chat/twai", {
      messages: [
        { role: "system", content: "你是雙北就業服務中心主任的智能助理。" },
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
    recommendation.value = String(text).trim();
    recCache.set(key, recommendation.value);
  } catch (e) {
    error.value = `AI 推薦失敗：${e?.response?.data?.message || e.message || "未知錯誤"}`;
  } finally {
    loading.value = false;
  }
}

watch(() => props.series, () => {
  selectedIdx.value = null;
  recommendation.value = "";
  error.value = "";
});
</script>

<style scoped>
.ear-root {
  display: flex; flex-direction: column; height: 100%;
  font-size: 0.85rem; color: var(--color-component-text, #cdd5da);
}
.ear-controls {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem;
  padding: 0.5rem 0.75rem; border-bottom: 1px solid rgba(255,255,255,0.08);
}
.ear-stat {
  display: flex; flex-direction: column; align-items: flex-start;
  padding: 0.35rem 0.5rem; background: rgba(255,255,255,0.03); border-radius: 4px;
}
.ear-stat.warning { background: rgba(220,38,38,0.1); }
.ear-stat strong { font-size: 1.1rem; color: #f8fafc; font-variant-numeric: tabular-nums; }
.ear-label { font-size: 0.65rem; color: #94a3b8; }
.ear-meta { font-size: 0.65rem; color: #94a3b8; margin-left: 0.25rem; }

.ear-list-wrap { flex: 1; min-height: 0; overflow-y: auto; padding: 0.25rem 0; }
.ear-list { display: flex; flex-direction: column; }
.ear-row {
  display: grid; grid-template-columns: 28px 1fr 56px;
  gap: 0.5rem; align-items: center;
  padding: 0.4rem 0.75rem; cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  transition: background 0.15s;
}
.ear-row:hover { background: rgba(34, 197, 94, 0.08); }
.ear-row.selected { background: rgba(34, 197, 94, 0.18); }
.ear-row.oos { border-left: 2px solid #dc2626; }
.ear-rank {
  text-align: center; font-weight: 700; color: #94a3b8;
  font-variant-numeric: tabular-nums;
}
.ear-info { min-width: 0; }
.ear-name { font-weight: 600; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ear-meta { font-size: 0.7rem; color: #94a3b8; margin-top: 0.1rem; }
.ear-oos-tag {
  background: #dc2626; color: #fff; padding: 0 0.3rem;
  border-radius: 2px; font-size: 0.6rem; font-weight: 700;
  margin-left: 0.3rem;
}
.ear-city-tag {
  display: inline-block; padding: 0 0.35rem; margin-right: 0.35rem;
  font-size: 0.65rem; border-radius: 3px; font-weight: 600;
}
.ear-city-tag.taipei { background: #b45309; color: #fff; }
.ear-city-tag.newtaipei { background: #1d4ed8; color: #fff; }
.ear-score {
  text-align: center; padding: 0.25rem 0; border-radius: 4px;
  font-weight: 700; color: #fff; font-variant-numeric: tabular-nums;
}

.ear-ai-panel {
  border-top: 2px solid rgba(34, 197, 94, 0.4);
  padding: 0.5rem 0.75rem; background: rgba(0,0,0,0.2);
  max-height: 280px; overflow-y: auto;
}
.ear-ai-head {
  display: flex; align-items: center; gap: 0.4rem;
  font-weight: 700; color: #4ade80; margin-bottom: 0.4rem;
  font-size: 0.8rem;
}
.ear-ai-head .material-icons { font-size: 18px; }
.ear-ai-refresh, .ear-ai-close {
  background: transparent; border: none; cursor: pointer;
  padding: 2px;
}
.ear-ai-refresh { margin-left: auto; color: #4ade80; }
.ear-ai-refresh:disabled { opacity: 0.4; }
.ear-ai-close { color: #94a3b8; }
.ear-ai-close:hover { color: #f8fafc; }

.ear-ai-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.4rem;
  margin-bottom: 0.5rem;
}
.ear-stat-cell {
  background: rgba(255,255,255,0.03); padding: 0.3rem 0.5rem; border-radius: 3px;
}
.ear-stat-cell strong {
  display: block; font-size: 0.85rem; color: #f8fafc; font-variant-numeric: tabular-nums;
}

.ear-ai-text { font-size: 0.78rem; line-height: 1.55; color: #e2e8f0; white-space: pre-wrap; }
.ear-ai-loading { color: #94a3b8; display: flex; align-items: center; gap: 0.4rem; }
.ear-ai-error { color: #fca5a5; font-size: 0.78rem; }
.ear-ai-hint { color: #64748b; font-size: 0.78rem; }
.ear-ai-cta {
  display: inline-flex; align-items: center; gap: 0.35rem;
  background: linear-gradient(135deg, #16a34a, #15803d);
  color: #fff; border: none; padding: 0.4rem 0.8rem; border-radius: 4px;
  font-weight: 600; cursor: pointer; font-size: 0.78rem;
}
.ear-ai-cta:hover { background: linear-gradient(135deg, #22c55e, #16a34a); }
.ear-ai-cta .material-icons { font-size: 16px; }
.ear-ai-login {
  display: flex; align-items: center; gap: 0.4rem;
  color: #94a3b8; font-size: 0.78rem; padding: 0.5rem;
  background: rgba(245,158,11,0.08); border-radius: 4px;
}
.ear-ai-login .material-icons { font-size: 18px; color: #f59e0b; }
.ear-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.ear-disclaimer {
  margin-top: 0.4rem; font-size: 0.65rem; color: #64748b;
  border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 0.3rem;
}
</style>
