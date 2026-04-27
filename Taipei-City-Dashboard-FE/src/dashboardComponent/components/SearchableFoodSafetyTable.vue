<!-- Searchable food safety certification lookup for 食安風險追蹤器 -->
<template>
  <div class="sfst">
    <!-- 搜尋 + 篩選 -->
    <div class="sfst-controls">
      <div class="sfst-search">
        <span class="material-icons">search</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜尋餐廳或工廠名稱..."
          class="sfst-input"
        />
        <button v-if="searchQuery" class="sfst-clear-btn" @click="searchQuery = ''">
          <span class="material-icons">close</span>
        </button>
      </div>
      <div class="sfst-filters">
        <select v-model="filterDistrict" class="sfst-select">
          <option value="">全部行政區</option>
          <option v-for="d in availableDistricts" :key="d" :value="d">{{ d }}</option>
        </select>
        <select v-model="filterGrade" class="sfst-select">
          <option value="">全部評等</option>
          <option value="優">優等</option>
          <option value="良">良好</option>
        </select>
      </div>
    </div>

    <!-- 統計摘要 -->
    <div class="sfst-summary">
      <span>共 <strong>{{ filteredRows.length.toLocaleString() }}</strong> 筆</span>
      <span v-if="gradeCount['優']" class="sfst-stat-excellent">
        <span class="sfst-dot excellent"></span>優等 {{ gradeCount['優'].toLocaleString() }}
      </span>
      <span v-if="gradeCount['良']" class="sfst-stat-good">
        <span class="sfst-dot good"></span>良好 {{ gradeCount['良'].toLocaleString() }}
      </span>
      <span v-if="gradeCount['工廠']" class="sfst-stat-factory">
        <span class="sfst-dot factory"></span>工廠 {{ gradeCount['工廠'].toLocaleString() }}
      </span>
      <span v-if="isFiltered" class="sfst-clear-all" @click="clearAll">清除篩選</span>
    </div>

    <!-- 表格 -->
    <div class="sfst-table-wrapper">
      <table class="sfst-table">
        <thead>
          <tr>
            <th v-if="hasBothCities">城市</th>
            <th>評等</th>
            <th @click="sortBy('name')" class="sfst-sortable">
              名稱 <span class="material-icons">{{ sortIcon('name') }}</span>
            </th>
            <th @click="sortBy('district')" class="sfst-sortable">
              行政區 <span class="material-icons">{{ sortIcon('district') }}</span>
            </th>
            <th>地址</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in pagedRows" :key="i" class="sfst-row">
            <td v-if="hasBothCities">
              <span :class="['sfst-city-badge', row.city === '臺北' ? 'tpe' : 'ntpc']">
                {{ row.city === '臺北' ? '台北' : '新北' }}
              </span>
            </td>
            <td>
              <span
                v-if="row.grade && row.grade !== '—'"
                :class="['sfst-grade-badge', row.grade === '優' ? 'excellent' : 'good']"
              >{{ row.grade }}</span>
              <span v-else class="sfst-grade-badge factory">工廠</span>
            </td>
            <td class="sfst-name">{{ row.name }}</td>
            <td class="sfst-district">{{ row.district }}</td>
            <td class="sfst-address">{{ truncate(row.address, 30) }}</td>
          </tr>
          <tr v-if="pagedRows.length === 0">
            <td :colspan="hasBothCities ? 5 : 4" class="sfst-empty">找不到符合條件的記錄</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分頁 -->
    <div class="sfst-pagination" v-if="totalPages > 1">
      <button :disabled="page === 1" @click="page--">‹</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button :disabled="page === totalPages" @click="page++">›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({ series: Array });

// series = [{data: [{x: '{"name":...,"grade":...}', y: 1}, ...]}]
const allRows = computed(() =>
	(props.series || []).flatMap(group =>
		(group.data || []).map(item => {
			try { return JSON.parse(item.x); }
			catch { return null; }
		}).filter(Boolean)
	)
);

const hasBothCities = computed(() => {
	const cities = new Set(allRows.value.map(r => r.city).filter(Boolean));
	return cities.size > 1;
});

const searchQuery    = ref("");
const filterDistrict = ref("");
const filterGrade    = ref("");
const sortKey      = ref("grade");
const sortDir      = ref(1);
const page         = ref(1);
const PAGE_SIZE    = 20;

const availableDistricts = computed(() => {
	const districts = new Set(allRows.value.map(r => r.district).filter(Boolean));
	return [...districts].sort();
});

const isFiltered = computed(() =>
	searchQuery.value || filterDistrict.value || filterGrade.value
);

const filteredRows = computed(() => {
	let rows = allRows.value;
	const q = searchQuery.value.toLowerCase();
	if (q) rows = rows.filter(r =>
		r.name?.toLowerCase().includes(q) || r.address?.toLowerCase().includes(q)
	);
	if (filterDistrict.value) rows = rows.filter(r => r.district === filterDistrict.value);
	if (filterGrade.value)    rows = rows.filter(r => r.grade === filterGrade.value);

	return [...rows].sort((a, b) => {
		const av = a[sortKey.value] ?? "";
		const bv = b[sortKey.value] ?? "";
		return sortDir.value * String(av).localeCompare(String(bv), "zh-TW");
	});
});

const gradeCount = computed(() => {
	const counts = { 優: 0, 良: 0, 工廠: 0 };
	for (const r of filteredRows.value) {
		if (r.grade === "優") counts["優"]++;
		else if (r.grade === "良") counts["良"]++;
		else counts["工廠"]++;
	}
	return counts;
});

const totalPages = computed(() => Math.ceil(filteredRows.value.length / PAGE_SIZE));
const pagedRows  = computed(() =>
	filteredRows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
);

watch([searchQuery, filterDistrict, filterGrade], () => { page.value = 1; });

function sortBy(key) {
	if (sortKey.value === key) sortDir.value *= -1;
	else { sortKey.value = key; sortDir.value = 1; }
	page.value = 1;
}

function sortIcon(key) {
	if (sortKey.value !== key) return "unfold_more";
	return sortDir.value === 1 ? "expand_more" : "expand_less";
}

function truncate(s, n) {
	if (!s) return "—";
	return s.length > n ? s.slice(0, n) + "…" : s;
}

function clearAll() {
	searchQuery.value = "";
	filterDistrict.value = "";
	filterGrade.value = "";
}
</script>

<style scoped>
.sfst {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  font-size: 13px;
}

.sfst-controls { display: flex; flex-direction: column; gap: 8px; }

.sfst-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-component-background, #1e1e1e);
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  padding: 6px 10px;
}
.sfst-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text, #fff);
  font-size: 13px;
}
.sfst-clear-btn { background: none; border: none; cursor: pointer; color: #888; padding: 0; }

.sfst-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.sfst-select {
  background: var(--color-component-background, #1e1e1e);
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  color: var(--color-text, #fff);
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.sfst-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: #aaa;
  flex-wrap: wrap;
}
.sfst-stat-excellent { color: #81C784; display: flex; align-items: center; gap: 4px; }
.sfst-stat-good      { color: #FFB74D; display: flex; align-items: center; gap: 4px; }
.sfst-stat-factory   { color: #64B5F6; display: flex; align-items: center; gap: 4px; }
.sfst-dot {
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
}
.sfst-dot.excellent { background: #43A047; }
.sfst-dot.good      { background: #FFA000; }
.sfst-dot.factory   { background: #1565C0; }
.sfst-clear-all { color: #4fc3f7; cursor: pointer; text-decoration: underline; margin-left: 4px; }

.sfst-table-wrapper { flex: 1; overflow-y: auto; }
.sfst-table { width: 100%; border-collapse: collapse; }
.sfst-table th {
  position: sticky;
  top: 0;
  background: var(--color-component-background, #1e1e1e);
  color: #aaa;
  font-weight: 500;
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid #333;
  white-space: nowrap;
}
.sfst-sortable { cursor: pointer; user-select: none; }
.sfst-sortable:hover { color: #fff; }
.sfst-table th .material-icons { font-size: 14px; vertical-align: middle; }
.sfst-table td { padding: 7px 6px; border-bottom: 1px solid #222; vertical-align: top; }
.sfst-row:hover td { background: rgba(255,255,255,0.03); }

.sfst-city-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.sfst-city-badge.tpe  { background: #1565C0; color: #fff; }
.sfst-city-badge.ntpc { background: #E65100; color: #fff; }

.sfst-grade-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.sfst-grade-badge.excellent { background: rgba(67,160,71,0.25); color: #81C784; }
.sfst-grade-badge.good      { background: rgba(255,160,0,0.25);  color: #FFB74D; }
.sfst-grade-badge.factory   { background: rgba(21,101,192,0.25); color: #64B5F6; }

.sfst-name     { font-weight: 500; color: #fff; }
.sfst-district { white-space: nowrap; color: #aaa; }
.sfst-address  { color: #bbb; max-width: 180px; }
.sfst-empty    { text-align: center; color: #666; padding: 24px; }

.sfst-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.sfst-pagination button {
  background: none;
  border: 1px solid #444;
  color: #fff;
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 3px;
}
.sfst-pagination button:disabled { opacity: 0.3; cursor: default; }
</style>
