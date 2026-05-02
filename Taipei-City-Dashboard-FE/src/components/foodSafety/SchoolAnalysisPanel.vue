<!-- Right-side analysis panel. Shows a single covering view based on
     foodSafetyStore.analysisFocus.type:
       - 'school'   → school details + history + AI summary
       - 'supplier' → supplier details + 危害等級 + served schools list
       - 'incident' → incident card + casualties + AI summary + news links -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();

const f = computed(() => fs.analysisFocus);

// Helpers for school view
const schoolHistory = computed(() => {
	if (f.value?.type !== "school") return [];
	const {id} = f.value.payload.properties;
	return fs.incidents.filter((i) => i.school_id === id || i.affected_school_ids.includes(id));
});

// Helpers for supplier view
const supplierServedSchools = computed(() => {
	if (f.value?.type !== "supplier") return [];
	const ids = f.value.payload.properties.served_school_ids || [];
	return fs.schools.filter((s) => ids.includes(s.properties.id));
});

function pickSchool(school) { fs.selectSchool(school); }
</script>

<template>
  <div class="fsm-panel fsm-cyber-panel fsm-analysis">
    <div
      v-if="!f"
      class="fsm-empty"
    >
      請點選地圖上的學校或事件卡以檢視詳情
    </div>

    <!-- School view -->
    <div
      v-else-if="f.type === 'school'"
      class="fsm-view"
    >
      <h3>{{ f.payload.properties.name }}</h3>
      <p>
        {{ f.payload.properties.city }} · {{ f.payload.properties.district }} · {{
          f.payload.properties.type === 'elementary' ? '國小' : '國中'
        }}
      </p>
      <div
        class="badge"
        :class="`badge-${f.payload.properties.incident_status}`"
      >
        {{ f.payload.properties.incident_status === 'red' ? 'Critical'
          : f.payload.properties.incident_status === 'yellow' ? 'Medium' : 'Low' }}
      </div>
      <h4>歷史食安事件 ({{ schoolHistory.length }})</h4>
      <ul class="history">
        <li
          v-for="i in schoolHistory"
          :key="i.id"
          @click="fs.selectIncident(i)"
        >
          <span class="date">{{ i.occurred_at }}</span>
          <span class="title">{{ i.title }}</span>
          <span
            class="severity"
            :class="`sev-${i.severity.toLowerCase()}`"
          >{{ i.severity }}</span>
        </li>
      </ul>
      <h4>AI 摘要</h4>
      <p class="summary">
        {{ schoolHistory[0]?.ai_summary || '尚無相關 AI 摘要。' }}
      </p>
    </div>

    <!-- Supplier view -->
    <div
      v-else-if="f.type === 'supplier'"
      class="fsm-view"
    >
      <h3>{{ f.payload.properties.name }}</h3>
      <p>{{ f.payload.properties.address }}</p>
      <div
        class="badge"
        :class="`badge-${f.payload.properties.hazard_level.toLowerCase()}`"
      >
        {{ f.payload.properties.hazard_level }}
      </div>
      <h4>稽查記錄</h4>
      <p>最近稽查：{{ f.payload.properties.last_inspection }} · {{ f.payload.properties.last_status }}</p>
      <h4>供應給以下學校 ({{ supplierServedSchools.length }})</h4>
      <ul class="served">
        <li
          v-for="s in supplierServedSchools"
          :key="s.properties.id"
          @click="pickSchool(s)"
        >
          {{ s.properties.name }}
        </li>
      </ul>
    </div>

    <!-- Incident view -->
    <div
      v-else-if="f.type === 'incident'"
      class="fsm-view"
    >
      <h3>{{ f.payload.title }}</h3>
      <p>{{ f.payload.occurred_at }} · {{ f.payload.school_name }}</p>
      <div
        class="badge"
        :class="`badge-${f.payload.severity.toLowerCase()}`"
      >
        {{ f.payload.severity }}
      </div>
      <div class="casualties">
        <div><strong>{{ f.payload.deaths }}</strong> 死亡</div>
        <div><strong>{{ f.payload.injured }}</strong> 受傷</div>
        <div><strong>{{ f.payload.hospitalized }}</strong> 住院</div>
      </div>
      <h4>確認問題食物</h4>
      <p>{{ f.payload.confirmed_food }}</p>
      <h4>疑似問題食物</h4>
      <p>{{ f.payload.suspected_food }}</p>
      <h4>AI 摘要</h4>
      <p class="summary">
        {{ f.payload.ai_summary }}
      </p>
      <h4>相關新聞</h4>
      <ul class="news">
        <li
          v-for="n in f.payload.news_links"
          :key="n.url"
        >
          <a
            :href="n.url"
            target="_blank"
            rel="noopener"
          >{{ n.title }}</a>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.fsm-analysis {
	pointer-events: auto;
	position: absolute; top: 16px; right: 16px; width: 380px;
	max-height: calc(100vh - 200px); overflow-y: auto;
	padding: 14px;
}
.fsm-empty { color: #8FA3C6; font-size: 13px; }
.fsm-view h3 {
	margin: 0 0 4px; font-size: 18px;
	color: #00E5FF;
	letter-spacing: 1px;
	text-shadow: 0 0 8px rgba(0,229,255,0.4);
}
.fsm-view h4 {
	margin: 12px 0 4px; font-size: 11px;
	color: #00E5FF; opacity: 0.85;
	text-transform: uppercase; letter-spacing: 2px;
	font-weight: 600;
}
.fsm-view p { margin: 4px 0; font-size: 13px; color: #D7E3F4; }
.summary {
	font-style: italic; color: #8FA3C6;
	background: rgba(0,229,255,0.04);
	border-left: 2px solid rgba(0,229,255,0.4);
	padding: 6px 10px;
}
.badge {
	display: inline-block; padding: 3px 10px; border-radius: 2px;
	font-size: 11px; font-weight: 600; margin: 4px 0;
	letter-spacing: 1px; text-transform: uppercase;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.badge-red, .badge-critical { background: #FF1744; color: #fff; box-shadow: 0 0 10px rgba(255,23,68,0.5); }
.badge-yellow, .badge-high  { background: #FF6D00; color: #fff; box-shadow: 0 0 10px rgba(255,109,0,0.5); }
.badge-medium               { background: #FFC107; color: #0A1228; box-shadow: 0 0 10px rgba(255,193,7,0.5); }
.badge-green, .badge-low    { background: #00E676; color: #0A1228; box-shadow: 0 0 10px rgba(0,230,118,0.5); }
.history, .served, .news { list-style: none; padding: 0; margin: 0; }
.history li, .served li {
	padding: 6px 0; border-bottom: 1px solid rgba(0,229,255,0.1); cursor: pointer;
	font-size: 12px; display: flex; gap: 8px; align-items: center;
	color: #D7E3F4;
}
.history li:hover, .served li:hover {
	background: rgba(0,229,255,0.06);
	color: #00E5FF;
}
.history .date {
	color: #8FA3C6; flex-shrink: 0;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.history .title { flex: 1; }
.severity {
	font-weight: 600; font-size: 11px;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
	letter-spacing: 1px;
}
.sev-critical { color: #FF1744; text-shadow: 0 0 6px rgba(255,23,68,0.6); }
.sev-high     { color: #FF6D00; text-shadow: 0 0 6px rgba(255,109,0,0.6); }
.sev-medium   { color: #FFC107; text-shadow: 0 0 6px rgba(255,193,7,0.6); }
.sev-low      { color: #00E676; text-shadow: 0 0 6px rgba(0,230,118,0.6); }
.casualties { display: flex; gap: 14px; padding: 8px 0; }
.casualties strong {
	font-size: 22px; color: #00E5FF; display: block;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
	text-shadow: 0 0 8px rgba(0,229,255,0.5);
}
.casualties div {
	font-size: 11px; color: #8FA3C6;
	text-transform: uppercase; letter-spacing: 1px;
}
.news a { color: #00E5FF; text-decoration: none; }
.news a:hover { text-decoration: underline; text-shadow: 0 0 6px rgba(0,229,255,0.5); }
</style>
