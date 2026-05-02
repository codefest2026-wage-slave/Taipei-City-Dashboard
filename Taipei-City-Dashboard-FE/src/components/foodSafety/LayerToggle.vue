<!-- Top-left layer-visibility controls for the school map.
     - showSchools: toggle schools layer visibility (default ON)
     - showSuppliers: toggle ALL suppliers visibility (default OFF)
     Click on a school always reveals its connected suppliers via arcs,
     independent of the suppliers toggle. -->
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
        :checked="fs.layerToggles.showSchools"
        @change="fs.toggleSubLayer('showSchools')"
      >
      <span class="dot dot-school" />
      顯示學校
    </label>
    <label>
      <input
        type="checkbox"
        :checked="fs.layerToggles.showSuppliers"
        @change="fs.toggleSubLayer('showSuppliers')"
      >
      <span class="dot dot-supplier" />
      顯示廠商
    </label>
  </div>
</template>

<style scoped>
.fsm-toggle {
	pointer-events: auto;
	position: absolute; top: 16px; left: 16px;
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 10px 14px; min-width: 160px; color: #ddd;
}
.fsm-toggle h4 { margin: 0 0 6px; font-size: 13px; color: #aaa; }
.fsm-toggle label { display: flex; align-items: center; gap: 6px;
	font-size: 13px; padding: 4px 0; cursor: pointer; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dot-school   { background: #00E5FF; box-shadow: 0 0 6px #00E5FF; }
.dot-supplier { background: #FFD54F; box-shadow: 0 0 6px #FFC107; }
</style>
