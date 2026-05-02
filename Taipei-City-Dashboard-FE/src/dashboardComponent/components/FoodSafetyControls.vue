<!-- Dashboard chart component for the food-safety-monitor 校內 control panel.
     Renders LayerToggle + MapLegend inside a DashboardComponent body.
     Receives standard chart props (chart_config, activeChart, series, etc.)
     but ignores them — this is a UI control panel, not a data chart. -->
<script setup>
import LayerToggle from "../../components/foodSafety/LayerToggle.vue";
import MapLegend from "../../components/foodSafety/MapLegend.vue";

defineProps([
	"chart_config", "activeChart", "series", "map_config", "map_filter", "map_filter_on",
]);
</script>

<template>
  <div
    v-if="activeChart === 'FoodSafetyControls'"
    class="fsm-controls-content"
  >
    <LayerToggle />
    <MapLegend />
  </div>
</template>

<style scoped>
.fsm-controls-content {
	display: flex;
	flex-direction: column;
	gap: var(--font-s);
	padding: var(--font-s) 0;
}
</style>
