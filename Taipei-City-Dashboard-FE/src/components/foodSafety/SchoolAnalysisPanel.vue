<!-- Right-side analysis panel (校內 mode). Three covering views:
     - 'school'   → school name + supplier audit summary + latest nutrition
     - 'supplier' → supplier name + audit status + served schools list
     - 'incident' → incident card (kept from prior iteration) -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();
const f = computed(() => fs.analysisFocus);

// School view: connected suppliers (via supply chain). The "alert" status uses
// the observation-period rule: red if ANY of the supplier's latest 3 audits is
// FAIL. latestFail (if any) shown as the most recent FAIL within that window.
const connectedSuppliers = computed(() => {
	if (f.value?.type !== "school") return [];
	const schoolId = f.value.payload.properties.id;
	const arcs = fs.supplyChain.filter((a) => a.properties.school_id === schoolId);
	const ids = new Set(arcs.map((a) => a.properties.supplier_id));
	return fs.suppliers
		.filter((s) => ids.has(s.properties.id))
		.map((s) => {
			const audits = fs.supplierAudits[s.properties.id] || [];
			const last3 = audits.slice(0, 3);
			const latestFail = last3.find((r) => r.status === "FAIL");
			return {
				id: s.properties.id,
				name: s.properties.name,
				feature: s,
				latestFail,
			};
		});
});

// School view: latest nutrition record
const latestNutrition = computed(() => {
	if (f.value?.type !== "school") return null;
	const records = fs.schoolNutrition[f.value.payload.properties.id] || [];
	return records[0] || null;
});

// Supplier view: latest 3 audit records (already sorted desc in mock data)
const supplierRecentAudits = computed(() => {
	if (f.value?.type !== "supplier") return [];
	const audits = fs.supplierAudits[f.value.payload.properties.id] || [];
	return audits.slice(0, 3);
});

// Supplier view: ALL historical FAIL records (sorted desc), for total count + latest 3
const supplierAllFails = computed(() => {
	if (f.value?.type !== "supplier") return [];
	const audits = fs.supplierAudits[f.value.payload.properties.id] || [];
	return audits.filter((r) => r.status === "FAIL");
});

// Supplier view: served schools list (already implemented logic)
const supplierServedSchools = computed(() => {
	if (f.value?.type !== "supplier") return [];
	const ids = f.value.payload.properties.served_school_ids || [];
	return fs.schools.filter((s) => ids.includes(s.properties.id));
});

function pickSupplier(supplierFeature) { fs.selectSupplier(supplierFeature); }
function pickSchool(schoolFeature) { fs.selectSchool(schoolFeature); }
</script>

<template>
  <div class="fsm-panel fsm-cyber-panel fsm-analysis">
    <div
      v-if="!f"
      class="fsm-empty"
    >
      請點選地圖上的學校、供應商或事件
    </div>

    <!-- School view -->
    <div
      v-else-if="f.type === 'school'"
      class="fsm-view"
    >
      <h3>{{ f.payload.properties.name }}</h3>
      <p class="meta">
        {{ f.payload.properties.city }} · {{ f.payload.properties.district }} · {{
          f.payload.properties.type === "elementary" ? "國小" : "國中"
        }}
      </p>

      <h4>食材供應商稽核狀況</h4>
      <ul
        v-if="connectedSuppliers.length"
        class="audit-list"
      >
        <li
          v-for="s in connectedSuppliers"
          :key="s.id"
          @click="pickSupplier(s.feature)"
        >
          <div class="audit-row">
            <span class="supplier-name">{{ s.name }}</span>
            <span
              v-if="s.latestFail"
              class="status-badge status-fail"
            >{{ s.latestFail.severity }}</span>
            <span
              v-else
              class="status-badge status-ok"
            >正常</span>
          </div>
          <div
            v-if="s.latestFail"
            class="audit-detail"
          >
            <span>{{ s.latestFail.date }}</span>
            <span>{{ s.latestFail.issue }}</span>
          </div>
        </li>
      </ul>
      <p
        v-else
        class="hint"
      >
        無串接的食材供應商資料
      </p>

      <h4>營養評分</h4>
      <div
        v-if="latestNutrition"
        class="nutrition-card"
      >
        <div class="nutrition-head">
          <span class="nutrition-date">{{ latestNutrition.date }}</span>
          <span class="nutrition-score">{{ latestNutrition.score }}<small>/5</small></span>
        </div>

        <div
          v-if="latestNutrition.dishes && latestNutrition.dishes.length"
          class="dish-list"
        >
          <div
            v-for="d in latestNutrition.dishes"
            :key="`${d.category}-${d.name}`"
            class="dish-row"
          >
            <span class="dish-cat">{{ d.category }}</span>
            <span class="dish-name">
              {{ d.name }}
              <span
                v-if="d.is_veg"
                class="dish-veg"
              >素</span>
            </span>
            <span
              class="dish-score"
              :class="`dish-score-${d.score}`"
            >{{ d.score }}</span>
          </div>
        </div>
        <div
          v-else
          class="nutrition-menu"
        >
          {{ latestNutrition.menu }}
        </div>

        <div
          v-if="latestNutrition.ai_review"
          class="ai-review"
        >
          <span class="ai-tag">AI 評語</span>
          <p>{{ latestNutrition.ai_review }}</p>
        </div>
      </div>
      <p
        v-else
        class="hint"
      >
        無營養評分資料
      </p>
    </div>

    <!-- Supplier view -->
    <div
      v-else-if="f.type === 'supplier'"
      class="fsm-view"
    >
      <h3>{{ f.payload.properties.name }}</h3>
      <p class="meta">
        {{ f.payload.properties.address }}
      </p>

      <h4>近 {{ supplierRecentAudits.length }} 筆稽核紀錄</h4>
      <ul
        v-if="supplierRecentAudits.length"
        class="audit-list"
      >
        <li
          v-for="(r, i) in supplierRecentAudits"
          :key="`recent-${i}`"
          :class="`row-${r.status.toLowerCase()}`"
        >
          <div class="audit-row">
            <span class="audit-date">{{ r.date }}</span>
            <span
              class="status-badge"
              :class="r.status === 'FAIL' ? 'status-fail' : 'status-ok'"
            >{{ r.status === "FAIL" ? r.severity : "PASS" }}</span>
          </div>
          <div
            v-if="r.status === 'FAIL'"
            class="audit-issue-line"
          >
            {{ r.issue }}
          </div>
        </li>
      </ul>
      <p
        v-else
        class="hint"
      >
        無稽核紀錄
      </p>

      <h4>
        歷史不合格紀錄
        <span class="fail-count">{{ supplierAllFails.length }} 筆</span>
      </h4>
      <ul
        v-if="supplierAllFails.length"
        class="audit-list"
      >
        <li
          v-for="(r, i) in supplierAllFails.slice(0, 3)"
          :key="`fail-${i}`"
          class="row-fail"
        >
          <div class="audit-row">
            <span class="audit-date">{{ r.date }}</span>
            <span class="status-badge status-fail">{{ r.severity }}</span>
          </div>
          <div class="audit-issue-line">
            {{ r.issue }}
          </div>
        </li>
      </ul>
      <p
        v-else
        class="hint"
      >
        無歷史不合格紀錄
      </p>

      <h4>供應學校清單 ({{ supplierServedSchools.length }})</h4>
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

    <!-- Incident view (kept as-is from prior iteration) -->
    <div
      v-else-if="f.type === 'incident'"
      class="fsm-view"
    >
      <h3>{{ f.payload.title }}</h3>
      <p class="meta">
        {{ f.payload.occurred_at }} · {{ f.payload.school_name }}
      </p>
      <div
        class="status-badge"
        :class="`sev-${f.payload.severity.toLowerCase()}`"
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
	position: absolute;
	top: 16px;
	right: 16px;
	width: 380px;
	max-height: calc(100vh - 200px);
	overflow-y: auto;
	padding: 14px;
	color: var(--fsm-text, #f5f5f5);
}
.fsm-empty {
	color: rgba(255, 255, 255, 0.5);
	font-size: 13px;
}
.fsm-view h3 {
	margin: 0 0 4px;
	font-size: 16px;
	color: #FFFFFF;
	letter-spacing: 1px;
}
.fsm-view h4 {
	margin: 14px 0 6px;
	font-size: 11px;
	color: rgba(255, 255, 255, 0.65);
	text-transform: uppercase;
	letter-spacing: 2px;
}
.fsm-view p {
	margin: 4px 0;
	font-size: 13px;
}
.meta { color: rgba(255, 255, 255, 0.55); font-size: 12px; }
.summary { font-style: italic; color: rgba(255, 255, 255, 0.75); }
.hint { color: rgba(255, 255, 255, 0.45); font-size: 12px; }

.status-badge {
	display: inline-block;
	padding: 2px 8px;
	border-radius: 10px;
	font-size: 11px;
	font-weight: 600;
}
.status-ok {
	background: rgba(0, 230, 118, 0.15);
	color: #00E676;
	border: 1px solid rgba(0, 230, 118, 0.5);
}
.status-fail {
	background: rgba(255, 23, 68, 0.15);
	color: #FF6B85;
	border: 1px solid rgba(255, 23, 68, 0.5);
}
.sev-critical { background: rgba(255, 23, 68, 0.2); color: #FF6B85; border: 1px solid #FF1744; }
.sev-high     { background: rgba(255, 109, 0, 0.2); color: #FFB180; border: 1px solid #FF6D00; }
.sev-medium   { background: rgba(255, 193, 7, 0.2); color: #FFE082; border: 1px solid #FFC107; }
.sev-low      { background: rgba(0, 230, 118, 0.2); color: #69F0AE; border: 1px solid #00E676; }

.audit-list, .served, .news {
	list-style: none;
	padding: 0;
	margin: 0;
}
.audit-list li, .served li {
	padding: 6px 0;
	border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	cursor: pointer;
	font-size: 12px;
}
.audit-list li.row-pass {
	cursor: default;
}
.served li:hover, .audit-list li:not(.row-pass):hover {
	background: rgba(255, 255, 255, 0.05);
}
.audit-issue-line {
	margin-top: 4px;
	font-size: 11px;
	color: rgba(255, 255, 255, 0.75);
}
.fail-count {
	display: inline-block;
	margin-left: 6px;
	padding: 1px 8px;
	font-size: 10px;
	color: #FF6B85;
	background: rgba(255, 23, 68, 0.12);
	border: 1px solid rgba(255, 23, 68, 0.4);
	border-radius: 10px;
	letter-spacing: 0;
}
.audit-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 8px;
}
.supplier-name {
	flex: 1;
	color: var(--fsm-text);
}
.audit-detail {
	display: flex;
	gap: 8px;
	margin-top: 4px;
	font-size: 11px;
	color: rgba(255, 255, 255, 0.55);
}
.audit-detail-block {
	padding: 8px 10px;
	border-radius: 4px;
	margin-bottom: 4px;
}
.status-fail-block {
	background: rgba(255, 23, 68, 0.06);
	border: 1px solid rgba(255, 23, 68, 0.25);
}
.status-ok-block {
	background: rgba(0, 230, 118, 0.06);
	border: 1px solid rgba(0, 230, 118, 0.25);
	display: flex;
	gap: 10px;
	align-items: center;
}
.audit-issue {
	font-size: 12px;
	color: var(--fsm-text);
	margin-top: 4px;
}
.status-ok-block .audit-issue { margin: 0; color: rgba(255, 255, 255, 0.55); }
.audit-date { font-size: 12px; color: rgba(255, 255, 255, 0.55); font-family: var(--fsm-mono, monospace); }

.nutrition-card {
	background: rgba(255, 255, 255, 0.04);
	border: 1px solid rgba(255, 255, 255, 0.1);
	border-radius: 4px;
	padding: 10px;
}
.nutrition-head {
	display: flex;
	justify-content: space-between;
	align-items: baseline;
	margin-bottom: 6px;
}
.nutrition-date { font-size: 11px; color: rgba(255, 255, 255, 0.55); }
.nutrition-score {
	font-family: var(--fsm-mono, monospace);
	font-size: 24px;
	color: #00E5FF;
	font-weight: 700;
	text-shadow: 0 0 8px rgba(0, 229, 255, 0.6);
}
.nutrition-score small {
	font-size: 12px;
	color: rgba(255, 255, 255, 0.45);
	font-weight: 400;
	margin-left: 2px;
}
.nutrition-menu {
	font-size: 12px;
	color: var(--fsm-text);
	margin: 4px 0 8px;
}
.dish-list {
	display: flex;
	flex-direction: column;
	gap: 4px;
	margin: 8px 0;
}
.dish-row {
	display: grid;
	grid-template-columns: 36px 1fr 22px;
	gap: 8px;
	align-items: center;
	padding: 4px 6px;
	background: rgba(255, 255, 255, 0.03);
	border-left: 2px solid rgba(255, 255, 255, 0.15);
	border-radius: 0 3px 3px 0;
	font-size: 12px;
}
.dish-cat {
	font-size: 10px;
	color: rgba(255, 255, 255, 0.55);
	letter-spacing: 1px;
}
.dish-name {
	color: var(--fsm-text);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.dish-veg {
	display: inline-block;
	margin-left: 4px;
	padding: 0 4px;
	font-size: 10px;
	color: #00E676;
	border: 1px solid rgba(0, 230, 118, 0.4);
	border-radius: 2px;
	background: rgba(0, 230, 118, 0.1);
}
.dish-score {
	font-family: var(--fsm-mono, monospace);
	font-size: 12px;
	font-weight: 600;
	text-align: center;
	padding: 1px 4px;
	border-radius: 2px;
}
.dish-score-0, .dish-score-1, .dish-score-2 {
	color: #FF1744;
	background: rgba(255, 23, 68, 0.12);
}
.dish-score-3 {
	color: #FFC107;
	background: rgba(255, 193, 7, 0.12);
}
.dish-score-4, .dish-score-5 {
	color: #00E676;
	background: rgba(0, 230, 118, 0.12);
}
.ai-review {
	margin-top: 8px;
	padding: 8px 10px;
	background: rgba(255, 255, 255, 0.04);
	border-left: 2px solid var(--fsm-cyan, #00E5FF);
	border-radius: 0 4px 4px 0;
	position: relative;
}
.ai-review .ai-tag {
	display: inline-block;
	font-size: 10px;
	font-weight: 600;
	color: #00E5FF;
	letter-spacing: 1px;
	padding: 1px 6px;
	margin-bottom: 4px;
	border: 1px solid rgba(0, 229, 255, 0.5);
	border-radius: 3px;
	background: rgba(0, 229, 255, 0.1);
	box-shadow: 0 0 6px rgba(0, 229, 255, 0.3);
}
.ai-review p {
	margin: 4px 0 0;
	font-size: 12px;
	line-height: 1.6;
	color: rgba(255, 255, 255, 0.78);
	font-style: italic;
}

.casualties {
	display: flex;
	gap: 14px;
	padding: 8px 0;
}
.casualties strong {
	font-size: 18px;
	color: var(--fsm-text);
	display: block;
	font-family: var(--fsm-mono, monospace);
}
.news a { color: #4FC3F7; text-decoration: none; }
.news a:hover { text-decoration: underline; }
</style>
