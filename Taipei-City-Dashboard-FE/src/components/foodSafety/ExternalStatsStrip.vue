<!-- Bottom strip with 4 stat cards (total / fail count / fail rate / high-risk
     district count) + a mini horizontal bar chart showing Top 5 violation
     categories. Reads externalStats getter + (Top 5 served from same data
     used in fsm_violation_rank if exposed; here kept as mini chart literal). -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
import VueApexCharts from "vue3-apexcharts";

const fs = useFoodSafetyStore();
const stats = computed(() => fs.externalStats);

// Top 5 mini chart — literal for restaurant overlay (independent from sidebar 1023);
// shows top 5 violation issues from restaurantInspections cache.
const top5 = computed(() => {
	const counter = {};
	Object.values(fs.restaurantInspections).forEach((r) => {
		(r.history || []).forEach((h) => {
			if (h.status === "FAIL" && h.issue !== "未發現問題") {
				counter[h.issue] = (counter[h.issue] || 0) + 1;
			}
		});
	});
	return Object.entries(counter)
		.sort((a, b) => b[1] - a[1])
		.slice(0, 5);
});

const top5Series = computed(() => [{
	name: "件數",
	data: top5.value.map((entry) => entry[1]),
}]);
const top5Options = computed(() => ({
	chart: { toolbar: { show: false } },
	colors: ["#E53935"],
	plotOptions: { bar: { borderRadius: 2, horizontal: true, distributed: false } },
	dataLabels: { enabled: false },
	grid: { show: false },
	xaxis: {
		categories: top5.value.map(([k]) => k),
		labels: { style: { colors: "#aaa", fontSize: "10px" } },
		axisBorder: { show: false }, axisTicks: { show: false },
	},
	yaxis: { labels: { style: { colors: "#ccc", fontSize: "11px" } } },
	tooltip: { enabled: false },
	legend: { show: false },
}));
</script>

<template>
  <div class="fsm-panel fsm-stats">
    <div class="cards">
      <div class="card">
        <div class="value">
          {{ stats.total.toLocaleString() }}
        </div>
        <div class="label">
          已抽驗餐廳
        </div>
      </div>
      <div class="card">
        <div class="value">
          {{ stats.fail.toLocaleString() }}
        </div>
        <div class="label">
          違規件數
        </div>
      </div>
      <div class="card">
        <div class="value">
          {{ stats.failRate }}%
        </div>
        <div class="label">
          違規率
        </div>
      </div>
      <div class="card">
        <div class="value">
          {{ stats.highRiskDistricts }}
        </div>
        <div class="label">
          高風險區
        </div>
      </div>
    </div>
    <div class="chart-area">
      <h4>近一年違規 Top 5</h4>
      <VueApexCharts
        v-if="top5.length"
        type="bar"
        height="120"
        :options="top5Options"
        :series="top5Series"
      />
      <p
        v-else
        class="hint"
      >
        尚無 mock 違規資料
      </p>
    </div>
  </div>
</template>

<style scoped>
.fsm-stats {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 50%;
	transform: translateX(-50%); width: 80%; min-width: 700px; max-width: 1100px;
	display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
	padding: 12px; background: rgba(20,20,30,0.92); border-radius: 6px;
}
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.card { padding: 10px; background: rgba(40,40,55,0.9); border-radius: 4px; text-align: center; }
.value { font-size: 22px; font-weight: 700; color: #fff; }
.label { font-size: 11px; color: #aaa; }
.chart-area h4 { margin: 0 0 4px; font-size: 11px; color: #aaa; }
.hint { color: #888; font-size: 12px; }
</style>
