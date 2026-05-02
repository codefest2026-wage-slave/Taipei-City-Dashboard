<!-- Conditional overlay container for dashboard 504 (食安監控系統).
     Mounts inside MapView and uses pointer-events: none on root so that
     the underlying Mapbox stays interactive; child panels opt into pointer
     events via .fsm-panel class. -->
<script setup>
import { onMounted, onBeforeUnmount, watch } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
import { useMapStore } from "../../store/mapStore";

import SchoolSearchBar          from "./SchoolSearchBar.vue";
import LayerToggle              from "./LayerToggle.vue";
import SchoolAnalysisPanel      from "./SchoolAnalysisPanel.vue";
import RecentIncidentsStrip     from "./RecentIncidentsStrip.vue";
import RestaurantFilterBar      from "./RestaurantFilterBar.vue";
import RestaurantInspectionPanel from "./RestaurantInspectionPanel.vue";
import ExternalStatsStrip       from "./ExternalStatsStrip.vue";

const fs = useFoodSafetyStore();
const mapStore = useMapStore();

onMounted(async () => {
	await fs.loadAllMockData();
});

// Bind layer-scoped click handlers when mapStore is ready and layer is added.
// We attach to specific layer ids when they appear on the map (R1).
watch(
	() => [...mapStore.currentLayers],
	(layers) => {
		layers.forEach((l) => attachLayerClickHandler(l));
	},
	{ deep: false },
);

// Apply restaurant filter expression whenever the dropdown selection changes.
watch(
	() => ({ ...fs.restaurantFilters }),
	() => {
		if (fs.activeLayer === "restaurant") {
			fs.applyRestaurantFilters();
		}
	},
	{ deep: true },
);

// Also apply filter once when restaurant layer first appears.
watch(
	() => fs.activeLayer,
	(layer) => {
		if (layer === "restaurant") {
			// Slight delay to ensure layer is added by Mapbox pipeline first.
			setTimeout(() => fs.applyRestaurantFilters(), 700);
		}
	},
);

const attachedHandlers = new Set();
function attachLayerClickHandler(layerId) {
	if (attachedHandlers.has(layerId)) return;
	if (!mapStore.map) return;
	if (layerId.startsWith("fsm_schools-")) {
		mapStore.map.on("click", layerId, (e) => {
			e.preventDefault?.();
			const f = e.features?.[0];
			if (!f) return;
			fs.selectSchool(f);
		});
		attachedHandlers.add(layerId);
	} else if (layerId.startsWith("fsm_restaurants-")) {
		mapStore.map.on("click", layerId, (e) => {
			e.preventDefault?.();
			const f = e.features?.[0];
			if (!f) return;
			fs.selectRestaurant(f);
		});
		attachedHandlers.add(layerId);
	}
}

onBeforeUnmount(() => {
	fs.resetAll();
	attachedHandlers.clear();
});
</script>

<template>
  <div class="fsm-overlays">
    <!-- 校內 mode panels -->
    <template v-if="fs.activeLayer === 'school'">
      <SchoolSearchBar />
      <LayerToggle />
      <SchoolAnalysisPanel />
      <RecentIncidentsStrip />
    </template>

    <!-- 校外 mode panels -->
    <template v-else-if="fs.activeLayer === 'restaurant'">
      <RestaurantFilterBar />
      <RestaurantInspectionPanel />
      <ExternalStatsStrip />
    </template>
  </div>
</template>

<style scoped>
.fsm-overlays {
	position: absolute;
	inset: 0;
	pointer-events: none;
	z-index: 10;
}
</style>
