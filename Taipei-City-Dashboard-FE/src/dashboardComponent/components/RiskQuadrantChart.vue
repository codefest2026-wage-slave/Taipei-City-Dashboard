<!-- Risk Quadrant Chart — 4 象限風險矩陣（食安違規業者，二元分類）

  cutoff = today - 1 year (2025-05-03)
    左上 持續違規 (一年前有 + 一年內有)  · 紅
    右上 新興風險 (一年前無 + 一年內有)  · 黃
    左下 改善中  (一年前有 + 一年內無)  · 藍
    右下 優良    (一年前無 + 一年內無)  · 綠

  - grid.padding.left=55 + yaxis.title.offsetX=5 → Y 軸標題完整顯示且往右
  - 4 角 badge label：象限名稱 + 業者數
  - Tooltip 用 ApexCharts 內建 fixed 模式，position 'topRight' + offsetY 60
    推到 chart 右側偏中，避開 4 角 label
  - 全局 CSS 強制 .apexcharts-tooltip z-index 99999，不被遮
-->

<script setup>
import { computed } from "vue";
import VueApexCharts from "vue3-apexcharts";

const props = defineProps([
	"chart_config",
	"activeChart",
	"series",
	"map_config",
	"map_filter",
	"map_filter_on",
]);

const COLORS = {
	persistent: "#E53935",
	emerging:   "#FBC02D",
	improving:  "#1E88E5",
	good:       "#43A047",
};
const COLOR_LIST = [COLORS.persistent, COLORS.emerging, COLORS.improving, COLORS.good];

function parsePoint(item) {
	const raw = String(item.x ?? "");
	const parts = raw.split("|");
	return {
		x: parseFloat(parts[0]),
		y: parseFloat(item.y),
		name: parts[1] || "—",
		h: parseInt((parts[2] ?? "h=0").replace("h=", ""), 10) || 0,
		r: parseInt((parts[3] ?? "r=0").replace("r=", ""), 10) || 0,
		gt: parseInt((parts[4] ?? "gt=0").replace("gt=", ""), 10) || 0,
	};
}

const goodsTotal = computed(() => {
	for (const pt of allPoints.value) {
		if (pt.gt > 0) return pt.gt;
	}
	return 0;
});

const allPoints = computed(() => {
	const list = [];
	for (const p of props.series?.[0]?.data ?? []) {
		const pt = parsePoint(p);
		if (Number.isNaN(pt.x) || Number.isNaN(pt.y)) continue;
		list.push(pt);
	}
	return list;
});

const grouped = computed(() => {
	const buckets = { persistent: [], emerging: [], improving: [], good: [] };
	for (const pt of allPoints.value) {
		const left = pt.x < 0;
		const top  = pt.y >= 0;
		const key = left && top  ? "persistent"
				: !left && top  ? "emerging"
				: left && !top  ? "improving"
				:                 "good";
		buckets[key].push(pt);
	}
	return buckets;
});

const seriesGrouped = computed(() => [
	{ name: "持續違規", data: grouped.value.persistent },
	{ name: "新興風險", data: grouped.value.emerging },
	{ name: "改善中",   data: grouped.value.improving },
	{ name: "優良",     data: grouped.value.good },
]);

// 真正業者總數 = 違規業者(全顯示) + 優良業者(用 BE 回傳的總數，非抽樣展示數)
const totalCount = computed(() =>
	grouped.value.persistent.length +
	grouped.value.emerging.length +
	grouped.value.improving.length +
	(goodsTotal.value || grouped.value.good.length)
);

const chartOptions = computed(() => ({
	chart: {
		type: "scatter",
		zoom: { enabled: false },
		toolbar: { show: false },
		background: "transparent",
		animations: { enabled: false },
		parentHeightOffset: 0,
		selection: { enabled: false },
	},
	theme: { mode: "dark" },
	colors: [COLORS.persistent, COLORS.emerging, COLORS.improving, COLORS.good],
	grid: {
		show: true,
		borderColor: "#2a2a2a",
		xaxis: { lines: { show: false } },
		yaxis: { lines: { show: false } },
		// left 加大到 55px 給 Y 軸標題完整空間
		padding: { top: 0, right: 55, bottom: 0, left: 55 },
	},
	legend: { show: false },
	xaxis: {
		type: "numeric",
		min: -2.4,
		max: 2.4,
		tickAmount: 4,
		title: {
			text: "歷史違規有 ←｜→ 歷史違規無",
			style: { color: "#888", fontWeight: 400, fontSize: "10px" },
			offsetY: -4,
		},
		labels: { show: false },
		axisBorder: { show: false },
		axisTicks: { show: false },
		crosshairs: { show: false },
		tooltip: { enabled: false },
	},
	yaxis: {
		min: -2.4,
		max: 2.4,
		tickAmount: 4,
		title: {
			text: "近期違規有 ↑｜↓ 近期違規無",
			style: { color: "#888", fontWeight: 400, fontSize: "10px" },
			offsetX: 45, // 往右推 5px，避免被卡片左邊切到
		},
		labels: { show: false },
		axisBorder: { show: false },
		axisTicks: { show: false },
	},
	markers: {
		size: 3,
		strokeWidth: 0,
		fillOpacity: 0.55,
		hover: { size: 6, sizeOffset: 0 },
	},
	states: {
		normal: { filter: { type: "none" } },
		hover:  { filter: { type: "lighten", value: 0.3 } },
		active: { filter: { type: "none" } },
	},
	tooltip: {
		enabled: true,
		theme: "dark",
		// 不用 fixed → ApexCharts 預設跟著滑鼠/資料點移動
		intersect: true,
		shared: false,
		custom: ({ seriesIndex, dataPointIndex, w }) => {
			const series = w.config.series?.[seriesIndex];
			const point = series?.data?.[dataPointIndex];
			if (!point) return "";
			const color = COLOR_LIST[seriesIndex] || "#888";
			return (
				`<div class="rqc-tooltip" style="border-left-color:${color}">` +
				`<div class="rqc-tooltip-quadrant" style="color:${color}">${series.name}</div>` +
				`<div class="rqc-tooltip-name">${point.name}</div>` +
				`<div class="rqc-tooltip-meta">` +
				`一年前違規：<b>${point.h}</b> 次<br/>` +
				`一年內違規：<b>${point.r}</b> 次` +
				`</div>` +
				`</div>`
			);
		},
	},
	annotations: {
		// 中央切線 + 上下左右 4 條外框邊界 = 矩形外圍
		xaxis: [
			{ x: 0, borderColor: "#666", strokeDashArray: 3 },
			{ x: -2.4, borderColor: "#888", strokeDashArray: 0 },
			{ x:  2.4, borderColor: "#888", strokeDashArray: 0 },
		],
		yaxis: [
			{ y: 0, borderColor: "#666", strokeDashArray: 3 },
			{ y: -2.4, borderColor: "#888", strokeDashArray: 0 },
			{ y:  2.4, borderColor: "#888", strokeDashArray: 0 },
		],
		// 4 角 badge：point 設在每象限「左上角」邊界點，用 offsetX/Y 把 label 推進象限內
		// （ApexCharts label 預設在 point 上方，加 offsetY 正值推下 → label 進入象限）
		points: [
			{
				x: -2.4, y: 2.4, marker: { size: 0 },  // 持續違規象限左上角 (chart 左上)
				label: {
					text: `持續違規 (${grouped.value.persistent.length})`,
					borderColor: "transparent", borderWidth: 0,
					textAnchor: "start",
					offsetX: 5.5,
					offsetY: 18,
					style: { color: "#fff", background: COLORS.persistent,
					         fontSize: "10px", fontWeight: 600,
					         padding: { left: 6, right: 6, top: 2, bottom: 2 } },
				},
			},
			{
				x: 0, y: 2.4, marker: { size: 0 },     // 新興風險象限左上角 (中線+頂部)
				label: {
					text: `新興風險 (${grouped.value.emerging.length})`,
					borderColor: "transparent", borderWidth: 0,
					textAnchor: "start",
					offsetX: 5.5,
					offsetY: 18,
					style: { color: "#222", background: COLORS.emerging,
					         fontSize: "10px", fontWeight: 600,
					         padding: { left: 6, right: 6, top: 2, bottom: 2 } },
				},
			},
			{
				x: -2.4, y: 0, marker: { size: 0 },    // 改善中象限左上角 (左邊+中線)
				label: {
					text: `改善中 (${grouped.value.improving.length})`,
					borderColor: "transparent", borderWidth: 0,
					textAnchor: "start",
					offsetX: 5.5,
					offsetY: 18,
					style: { color: "#fff", background: COLORS.improving,
					         fontSize: "10px", fontWeight: 600,
					         padding: { left: 6, right: 6, top: 2, bottom: 2 } },
				},
			},
			{
				x: 0, y: 0, marker: { size: 0 },       // 優良象限左上角 (中央十字交點)
				label: {
					text: `優良 (${goodsTotal.value || grouped.value.good.length} / 每小時換)`,
					borderColor: "transparent", borderWidth: 0,
					textAnchor: "start",
					offsetX: 5.5,
					offsetY: 18,
					style: { color: "#fff", background: COLORS.good,
					         fontSize: "10px", fontWeight: 600,
					         padding: { left: 6, right: 6, top: 2, bottom: 2 } },
				},
			},
		],
	},
}));
</script>

<template>
	<div v-if="activeChart === 'RiskQuadrantChart'" class="riskquadrantchart">
		<div class="riskquadrantchart-title">
			<h5>業者總數</h5>
			<h6>{{ totalCount }} {{ chart_config.unit }}</h6>
		</div>
		<div class="riskquadrantchart-chart">
			<VueApexCharts
				width="100%"
				height="100%"
				type="scatter"
				:options="chartOptions"
				:series="seriesGrouped"
			/>
		</div>
	</div>
</template>


<style scoped lang="scss">
.riskquadrantchart {
	display: flex;
	flex-direction: column;
	height: 100%;
	width: 100%;
	overflow: visible;

	&-title {
		flex: 0 0 auto;
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin: 0 0 0.2rem;

		h5 {
			margin: 0;
			color: var(--color-complement-text);
			font-size: var(--font-s);
		}
		h6 {
			margin: 0;
			color: var(--color-complement-text);
			font-size: var(--font-s);
			font-weight: 400;
		}
	}

	&-chart {
		flex: 1 1 auto;
		min-height: 0;
		overflow: visible;
		position: relative;

	}
}
</style>

<!-- 非 scoped：強制 ApexCharts tooltip 跳脫 dashboard 卡片 overflow，固定 viewport 左下 -->
<style lang="scss">
/* :has(.rqc-tooltip) → 只影響本組件的 tooltip，不影響其他 chart */
/* tooltip 跟著資料點移動，用 margin 整體推到「點的左下方」（避開上方 dashboard 標題） */
.apexcharts-tooltip:has(.rqc-tooltip) {
	z-index: 999999 !important;
	overflow: visible !important;
	background: transparent !important;
	border: none !important;
	box-shadow: none !important;
	margin-left: -10px !important;   /* 從點往左推 220px */
	margin-top: 60px !important;       /* 從點往下推 40px */
}

.rqc-tooltip {
	background: rgba(15, 15, 15, 0.98);
	border: 1px solid #555;
	border-left: 4px solid #888;
	border-radius: 4px;
	padding: 10px 14px;
	color: #e0e0e0;
	font-size: 11px;
	line-height: 1.5;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.8);
	pointer-events: none;
	min-width: 180px;
	max-width: 260px;

	&-quadrant {
		font-size: 10px;
		font-weight: 600;
		margin-bottom: 3px;
	}
	&-name {
		font-weight: 600;
		margin-bottom: 6px;
		color: #fff;
		word-break: break-all;
		font-size: 12px;
	}
	&-meta {
		font-size: 10px;
		color: #cfcfcf;
		b { color: #fff; font-weight: 600; }
	}
}
</style>
