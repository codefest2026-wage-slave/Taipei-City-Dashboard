<!-- Dashboard chart component for fsm_school_map. Renders inside the card body
     when 校內食安地圖 is toggled on. Contains the search bar and the simplified
     2-column legend. Suppliers are click-driven (no manual toggle). -->
<script setup>
import SchoolSearchBar from "../../components/foodSafety/SchoolSearchBar.vue";
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
    <SchoolSearchBar />
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
