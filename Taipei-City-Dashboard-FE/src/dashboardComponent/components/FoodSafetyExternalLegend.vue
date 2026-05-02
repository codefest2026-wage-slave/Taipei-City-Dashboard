<!-- Dashboard chart for fsm_restaurant_map: business search bar + 5-tier
     hazard_level legend matching the fsm_restaurants Mapbox layer. -->
<script setup>
import RestaurantSearchBar from "../../components/foodSafety/RestaurantSearchBar.vue";

defineProps([
	"chart_config", "activeChart", "series", "map_config", "map_filter", "map_filter_on",
]);

const rows = [
	{ key: "critical", label: "重大危害", color: "#FF1744" },
	{ key: "high",     label: "高危害",   color: "#FF6D00" },
	{ key: "medium",   label: "中等危害", color: "#FFC107" },
	{ key: "low",      label: "低危害",   color: "#00E676" },
	{ key: "info",     label: "一般稽查", color: "#00E5FF" },
];
</script>

<template>
  <div
    v-if="activeChart === 'FoodSafetyExternalLegend'"
    class="fsm-ext-legend"
  >
    <RestaurantSearchBar />
    <div class="fsm-ext-legend-title">
      危害等級
    </div>
    <div class="fsm-ext-legend-rows">
      <div
        v-for="r in rows"
        :key="r.key"
        class="fsm-ext-legend-row"
      >
        <span
          class="dot"
          :style="{ background: r.color, boxShadow: `0 0 6px ${r.color}` }"
        />
        <span class="name">{{ r.label }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fsm-ext-legend {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: var(--font-s) 0;
	color: var(--color-normal-text, #f5f5f5);
}
.fsm-ext-legend-title {
	font-size: 10px;
	color: rgba(255, 255, 255, 0.65);
	text-transform: uppercase;
	letter-spacing: 2px;
	border-bottom: 1px solid rgba(255, 255, 255, 0.12);
	padding-bottom: 4px;
}
.fsm-ext-legend-rows {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 6px 12px;
}
.fsm-ext-legend-row {
	display: flex;
	align-items: center;
	gap: 8px;
	font-size: 12px;
}
.dot {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	flex-shrink: 0;
}
.name { color: var(--color-normal-text, #f5f5f5); }
</style>
