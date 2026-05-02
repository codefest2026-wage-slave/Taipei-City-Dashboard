<!-- ApexCharts scatter visualizing 4-quadrant restaurant risk matrix.
     Receives 4 buckets (高危險店家 / 新興風險 / 改善中 / 優良店家) with counts;
     renders each bucket as N jittered scatter points within its quadrant.
     X-axis: 一年內違規（0/1, jittered around quadrant center）.
     Y-axis: 一年前違規（0/1, jittered around quadrant center）. -->
<script setup>
import { computed } from "vue";
import VueApexCharts from "vue3-apexcharts";

const props = defineProps([
	"chart_config", "activeChart", "series", "map_config", "map_filter", "map_filter_on",
]);

// 4 quadrant centers in chart space (X: -1 to 1, Y: -1 to 1)
//   X axis = 一年內 violation (right = yes), Y axis = 一年前 violation (top = yes)
const QUADRANTS = {
	"高危險店家": { x: 0.5, y: 0.5,   color: "#E53935" },  // 1y有 + 1y前有
	"新興風險":   { x: 0.5, y: -0.5,  color: "#FF9800" },  // 1y有 + 1y前無
	"改善中":     { x: -0.5, y: 0.5,  color: "#1565C0" },  // 1y無 + 1y前有
	"優良店家":   { x: -0.5, y: -0.5, color: "#43A047" },  // 1y無 + 1y前無
};

function jitter(c, n, spread = 0.35) {
	// Deterministic pseudo-random scatter around center
	const out = [];
	for (let i = 0; i < n; i++) {
		const a = (i * 2.39996323) % (2 * Math.PI);  // golden angle
		const r = spread * Math.sqrt((i + 1) / n);
		out.push({ x: c.x + r * Math.cos(a), y: c.y + r * Math.sin(a) });
	}
	return out;
}

const apexSeries = computed(() => {
	// props.series shape per chart pipeline:
	//   [{ name: '...', data: [{x: '高危險店家', y: 12}, ...] }]
	// or two_d row form: [{ name, data: [12, 8, 15, 65] }] with labels in chart_config.labels
	// Defensive: support both shapes
	const raw = props.series?.[0]?.data ?? [];
	const buckets = raw.map((d) => {
		if (typeof d === "object" && d !== null) return { name: d.x, count: d.y ?? d.data ?? 0 };
		return { name: d, count: 0 };
	});
	return Object.entries(QUADRANTS).map(([label, c]) => {
		const b = buckets.find((x) => x.name === label);
		const count = b ? b.count : 0;
		return {
			name: `${label} (${count})`,
			data: jitter(c, count).map((p) => ({ x: p.x, y: p.y, label })),
		};
	});
});

const chartOptions = computed(() => ({
	chart: {
		type: "scatter",
		zoom: { enabled: false },
		toolbar: { show: false },
		animations: { enabled: true, speed: 400 },
		background: "transparent",
	},
	colors: Object.values(QUADRANTS).map((q) => q.color),
	dataLabels: { enabled: false },
	grid: {
		xaxis: { lines: { show: false } },
		yaxis: { lines: { show: false } },
	},
	xaxis: {
		min: -1, max: 1, tickAmount: 2,
		labels: {
			formatter: (v) => v < 0 ? "一年內無違規" : v > 0 ? "一年內有違規" : "",
			style: { colors: "#aaa", fontSize: "11px" },
		},
		axisBorder: { show: false }, axisTicks: { show: false },
	},
	yaxis: {
		min: -1, max: 1, tickAmount: 2,
		labels: {
			formatter: (v) => v < 0 ? "一年前無違規" : v > 0 ? "一年前有違規" : "",
			style: { colors: "#aaa", fontSize: "11px" },
		},
	},
	annotations: {
		yaxis: [{ y: 0, borderColor: "#666", strokeDashArray: 3 }],
		xaxis: [{ x: 0, borderColor: "#666", strokeDashArray: 3 }],
	},
	legend: { show: true, position: "bottom", labels: { colors: "#ccc" } },
	tooltip: {
		custom: ({ seriesIndex, dataPointIndex, w }) => {
			const point = w.config.series[seriesIndex].data[dataPointIndex];
			return `<div class="chart-tooltip"><h6>${point.label}</h6></div>`;
		},
	},
	markers: { size: 6, strokeWidth: 0 },
}));
</script>

<template>
  <div v-if="activeChart === 'RiskMatrixChart'">
    <VueApexCharts
      width="100%"
      height="320"
      type="scatter"
      :options="chartOptions"
      :series="apexSeries"
    />
  </div>
</template>
