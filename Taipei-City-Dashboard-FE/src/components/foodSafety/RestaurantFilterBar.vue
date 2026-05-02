<!-- Top-center filter dropdowns for the restaurant map. Sets
     foodSafetyStore.restaurantFilters; the filter is applied via
     mapStore filter expression in Task 22. -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
</script>

<template>
  <div class="fsm-panel fsm-cyber-panel fsm-filter">
    <label>違規程度
      <select v-model="fs.restaurantFilters.severity">
        <option value="all">全部</option>
        <option value="high">高 (高危險 / 新興)</option>
        <option value="medium">中 (改善中)</option>
        <option value="low">低 (優良)</option>
      </select>
    </label>
    <label>時間區間
      <select v-model="fs.restaurantFilters.timeRange">
        <option value="3m">近 3 個月</option>
        <option value="6m">近 6 個月</option>
        <option value="1y">近 1 年</option>
        <option value="3y">近 3 年</option>
      </select>
    </label>
  </div>
</template>

<style scoped>
.fsm-filter {
	pointer-events: auto;
	position: absolute; top: 16px; left: 16px;
	display: flex; gap: 14px; padding: 10px 16px;
}
.fsm-filter label {
	display: flex; flex-direction: column;
	font-size: 10px; gap: 4px;
	color: rgba(255, 255, 255, 0.7);
	text-transform: uppercase; letter-spacing: 2px;
	font-weight: 600;
}
.fsm-filter select {
	background: rgba(0,0,0,0.35);
	border: 1px solid rgba(255, 255, 255, 0.15);
	color: #F5F5F5; padding: 5px 10px; border-radius: 3px;
	font-size: 12px; letter-spacing: 0.5px;
	transition: border-color 120ms ease, box-shadow 120ms ease;
	cursor: pointer;
}
.fsm-filter select:focus {
	outline: none;
	border-color: rgba(0, 229, 255, 0.5);
	box-shadow: 0 0 6px rgba(0, 229, 255, 0.3);
}
.fsm-filter select option {
	background: #1c1e24; color: #F5F5F5;
}
</style>
