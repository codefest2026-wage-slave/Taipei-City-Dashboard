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
	chart: { toolbar: { show: false }, background: "transparent" },
	colors: ["#FF1744"],
	plotOptions: { bar: { borderRadius: 2, horizontal: true, distributed: false } },
	dataLabels: { enabled: false },
	grid: { show: false },
	xaxis: {
		categories: top5.value.map(([k]) => k),
		labels: { style: { colors: "#8FA3C6", fontSize: "10px" } },
		axisBorder: { show: false }, axisTicks: { show: false },
	},
	yaxis: { labels: { style: { colors: "#D7E3F4", fontSize: "11px" } } },
	tooltip: { enabled: false },
	legend: { show: false },
}));
</script>

<template>
  <div class="fsm-panel fsm-cyber-panel fsm-stats">
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
	padding: 14px;
}
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.card {
	padding: 12px 10px;
	background: rgba(0,229,255,0.04);
	border: 1px solid rgba(0,229,255,0.18);
	border-radius: 3px; text-align: center;
	position: relative;
	transition: border-color 200ms ease, box-shadow 200ms ease;
}
.card:hover {
	border-color: rgba(0,229,255,0.5);
	box-shadow: 0 0 10px rgba(0,229,255,0.15);
}
.value {
	font-size: 26px; font-weight: 700; color: #00E5FF;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
	letter-spacing: 1px;
	text-shadow: 0 0 10px rgba(0,229,255,0.5);
	animation: fsm-pulse 3s ease-in-out infinite;
}
@keyframes fsm-pulse {
	0%, 100% { text-shadow: 0 0 10px rgba(0,229,255,0.5); }
	50%      { text-shadow: 0 0 14px rgba(0,229,255,0.8); }
}
.label {
	font-size: 10px; color: #8FA3C6;
	text-transform: uppercase; letter-spacing: 2px;
	margin-top: 4px;
}
.chart-area h4 {
	margin: 0 0 6px; font-size: 11px;
	color: #00E5FF; opacity: 0.85;
	text-transform: uppercase; letter-spacing: 2px;
	font-weight: 600;
}
.hint { color: #8FA3C6; font-size: 12px; }
</style>
