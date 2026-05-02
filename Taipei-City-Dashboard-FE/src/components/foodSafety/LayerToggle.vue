<!-- Bottom-left sub-toggles for the school map. Two switches:
     - showSupplyChain: draw ArcLayer for selected school's suppliers.
     - showIncidentSchools: highlight schools with incident_status === 'red'. -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
</script>

<template>
  <div class="fsm-panel fsm-toggle">
    <h4>圖層</h4>
    <label>
      <input
        type="checkbox"
        :checked="fs.layerToggles.showSupplyChain"
        @change="fs.toggleSubLayer('showSupplyChain')"
      >
      顯示供應鏈連線
    </label>
    <label>
      <input
        type="checkbox"
        :checked="fs.layerToggles.showIncidentSchools"
        @change="fs.toggleSubLayer('showIncidentSchools')"
      >
      標示曾發生事件學校
    </label>
  </div>
</template>

<style scoped>
.fsm-toggle {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 16px;
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 10px 14px; min-width: 180px; color: #ddd;
}
.fsm-toggle h4 { margin: 0 0 6px; font-size: 13px; color: #aaa; }
.fsm-toggle label { display: flex; align-items: center; gap: 6px;
	font-size: 13px; padding: 4px 0; cursor: pointer; }
</style>
