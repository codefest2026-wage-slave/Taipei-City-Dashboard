<!-- Searchable violation lookup table for 工作安全燈號 dashboard -->
<template>
  <div class="searchable-violation-table">
    <div class="svt-controls">
      <div class="svt-search">
        <span class="material-icons">search</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="輸入公司名稱搜尋違規記錄..."
          class="svt-input"
        >
        <button
          v-if="searchQuery"
          class="svt-clear"
          @click="searchQuery = ''"
        >
          <span class="material-icons">close</span>
        </button>
      </div>
      <div class="svt-filters">
        <select
          v-model="filterCity"
          class="svt-select"
        >
          <option value="">
            全部城市
          </option>
          <option value="臺北">
            臺北市
          </option>
          <option value="新北">
            新北市
          </option>
        </select>
        <select
          v-model="filterLaw"
          class="svt-select"
        >
          <option value="">
            全部法規
          </option>
          <option value="勞基法">
            勞動基準法
          </option>
          <option value="性平法">
            性別平等工作法
          </option>
          <option value="職安法">
            職業安全衛生法
          </option>
        </select>
        <select
          v-model="filterYear"
          class="svt-select"
        >
          <option value="">
            全部年度
          </option>
          <option
            v-for="y in availableYears"
            :key="y"
            :value="y"
          >
            {{ y }}
          </option>
        </select>
      </div>
    </div>

    <div class="svt-result-count">
      共 <strong>{{ filteredRows.length.toLocaleString() }}</strong> 筆記錄
      <span
        v-if="isFiltered"
        class="svt-clear-all"
        @click="clearAll"
      >清除篩選</span>
    </div>

    <div class="svt-table-wrapper">
      <table class="svt-table">
        <thead>
          <tr>
            <th>城市</th>
            <th
              class="svt-sortable"
              @click="sortBy('penalty_date')"
            >
              日期 <span class="material-icons">{{ sortIcon('penalty_date') }}</span>
            </th>
            <th>公司名稱</th>
            <th>法規</th>
            <th>違規內容</th>
            <th
              class="svt-sortable"
              @click="sortBy('fine_amount')"
            >
              罰款 <span class="material-icons">{{ sortIcon('fine_amount') }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in pagedRows"
            :key="i"
            :class="['svt-row', row.law_category]"
          >
            <td>
              <span :class="['svt-city-badge', row.city === '臺北' ? 'tpe' : 'ntpc']">
                {{ row.city }}
              </span>
            </td>
            <td class="svt-date">
              {{ row.penalty_date || '—' }}
            </td>
            <td class="svt-company">
              {{ row.company_name }}
            </td>
            <td>
              <span :class="['svt-law-badge', row.law_category]">
                {{ row.law_category }}
              </span>
            </td>
            <td class="svt-content">
              {{ truncate(row.violation_content, 40) }}
            </td>
            <td class="svt-fine">
              {{ row.fine_amount ? '$' + Number(row.fine_amount).toLocaleString() : '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="totalPages > 1"
      class="svt-pagination"
    >
      <button
        :disabled="page === 1"
        @click="page--"
      >
        ‹
      </button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button
        :disabled="page === totalPages"
        @click="page++"
      >
        ›
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";

const props = defineProps({ series: Array });

// series = [{data: [{x: '{"company_name":...}', y: 30000}, ...]}]
const allRows = computed(() => {
	return (props.series || []).flatMap(group =>
		(group.data || []).map(item => {
			try { return JSON.parse(item.x); }
			catch { return null; }
		}).filter(r => r && r.company_name)
	);
});

const searchQuery = ref("");
const filterCity  = ref("");
const filterLaw   = ref("");
const filterYear  = ref("");
const sortKey     = ref("penalty_date");
const sortDir     = ref(-1);
const page        = ref(1);
const PAGE_SIZE   = 20;

const availableYears = computed(() => {
	const years = new Set(
		allRows.value
			.map(r => r.penalty_date?.slice(0, 4))
			.filter(Boolean)
	);
	return [...years].sort((a, b) => b - a);
});

const isFiltered = computed(() =>
	searchQuery.value || filterCity.value || filterLaw.value || filterYear.value
);

const filteredRows = computed(() => {
	let rows = allRows.value;
	const q = searchQuery.value.toLowerCase();
	if (q) rows = rows.filter(r => r.company_name?.toLowerCase().includes(q));
	if (filterCity.value) rows = rows.filter(r => r.city === filterCity.value);
	if (filterLaw.value)  rows = rows.filter(r => r.law_category === filterLaw.value);
	if (filterYear.value) rows = rows.filter(r => r.penalty_date?.startsWith(filterYear.value));

	return [...rows].sort((a, b) => {
		const av = a[sortKey.value] ?? "";
		const bv = b[sortKey.value] ?? "";
		if (sortKey.value === "fine_amount") {
			return sortDir.value * ((Number(bv) || 0) - (Number(av) || 0));
		}
		return sortDir.value * String(bv).localeCompare(String(av));
	});
});

const totalPages = computed(() => Math.ceil(filteredRows.value.length / PAGE_SIZE));
const pagedRows  = computed(() =>
	filteredRows.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
);

watch([searchQuery, filterCity, filterLaw, filterYear], () => { page.value = 1; });

function sortBy(key) {
	if (sortKey.value === key) sortDir.value *= -1;
	else { sortKey.value = key; sortDir.value = -1; }
	page.value = 1;
}

function sortIcon(key) {
	if (sortKey.value !== key) return "unfold_more";
	return sortDir.value === -1 ? "expand_more" : "expand_less";
}

function truncate(s, n) {
	if (!s) return "—";
	return s.length > n ? s.slice(0, n) + "…" : s;
}

function clearAll() {
	searchQuery.value = "";
	filterCity.value = "";
	filterLaw.value = "";
	filterYear.value = "";
}
</script>

<style scoped>
.searchable-violation-table {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  font-size: 13px;
}

.svt-controls { display: flex; flex-direction: column; gap: 8px; }

.svt-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-component-background, #1e1e1e);
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  padding: 6px 10px;
}
.svt-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text, #fff);
  font-size: 13px;
}
.svt-clear { background: none; border: none; cursor: pointer; color: #888; }

.svt-filters { display: flex; gap: 8px; flex-wrap: wrap; }
.svt-select {
  background: var(--color-component-background, #1e1e1e);
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  color: var(--color-text, #fff);
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.svt-result-count { color: #aaa; font-size: 12px; }
.svt-clear-all {
  margin-left: 8px;
  color: #4fc3f7;
  cursor: pointer;
  text-decoration: underline;
}

.svt-table-wrapper { flex: 1; overflow-y: auto; }
.svt-table { width: 100%; border-collapse: collapse; }
.svt-table th {
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
.svt-sortable { cursor: pointer; user-select: none; }
.svt-sortable:hover { color: #fff; }
.svt-table th .material-icons { font-size: 14px; vertical-align: middle; }

.svt-table td {
  padding: 7px 6px;
  border-bottom: 1px solid #222;
  vertical-align: top;
}
.svt-row:hover td { background: rgba(255,255,255,0.03); }

.svt-city-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.svt-city-badge.tpe { background: #1565C0; color: #fff; }
.svt-city-badge.ntpc { background: #E65100; color: #fff; }

.svt-law-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  white-space: nowrap;
}
.svt-law-badge.勞基法 { background: rgba(229,57,53,0.2); color: #EF9A9A; }
.svt-law-badge.性平法 { background: rgba(142,36,170,0.2); color: #CE93D8; }
.svt-law-badge.職安法 { background: rgba(255,109,0,0.2); color: #FFCC80; }

.svt-date  { white-space: nowrap; color: #aaa; }
.svt-company { font-weight: 500; color: #fff; }
.svt-content { color: #bbb; max-width: 200px; }
.svt-fine { white-space: nowrap; font-weight: 500; color: #EF9A9A; }

.svt-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.svt-pagination button {
  background: none;
  border: 1px solid #444;
  color: #fff;
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 3px;
}
.svt-pagination button:disabled { opacity: 0.3; cursor: default; }
</style>
