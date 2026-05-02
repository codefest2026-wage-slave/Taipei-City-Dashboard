<!-- Sidebar card mounted in MapView's .map-charts ABOVE the BE-driven dashboard
     components when dashboard 504 ('food_safety_monitor') is active and the
     校內 (school) layer is open. Visually mimics the .dashboardcomponent card
     frame so it sits naturally alongside the BE-driven chart cards. -->
<script setup>
import LayerToggle from "./LayerToggle.vue";
import MapLegend from "./MapLegend.vue";
</script>

<template>
  <div class="fsm-controls-card">
    <div class="fsm-controls-card-header">
      <h3>圖層與圖例</h3>
    </div>
    <div class="fsm-controls-card-body">
      <LayerToggle />
      <MapLegend />
    </div>
  </div>
</template>

<style scoped>
.fsm-controls-card {
	width: calc(100% - var(--font-m) * 2);
	max-width: calc(100% - var(--font-m) * 2);
	display: flex;
	flex-direction: column;
	padding: var(--font-m);
	border-radius: 5px;
	background-color: var(--color-component-background);
	position: relative;
	overflow: hidden;
	margin-bottom: var(--font-m);
}
.fsm-controls-card::before {
	content: '';
	position: absolute;
	top: 0; left: 0; right: 0;
	height: 1px;
	background: linear-gradient(90deg, transparent, #00E5FF, transparent);
	pointer-events: none;
}
.fsm-controls-card-header {
	display: flex;
	justify-content: space-between;
	overflow: visible;
	margin-bottom: var(--font-s);
}
.fsm-controls-card-header h3 {
	display: flex;
	font-size: var(--font-m);
	color: #00E5FF;
	text-transform: uppercase;
	letter-spacing: 2px;
	margin: 0;
}
.fsm-controls-card-body {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
</style>
