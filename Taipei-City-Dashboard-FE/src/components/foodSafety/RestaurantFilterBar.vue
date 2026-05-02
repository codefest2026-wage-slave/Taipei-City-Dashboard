<!-- Top-center filter dropdowns for the restaurant map. Sets
     foodSafetyStore.restaurantFilters; the filter is applied via
     mapStore filter expression in Task 22. -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
const districts = ['all', '臺北市', '新北市',
	'信義區','大安區','中正區','中山區','士林區','北投區','內湖區','南港區','文山區','松山區','萬華區','大同區',
	'板橋區','三重區','中和區','永和區','新莊區','新店區','蘆洲區','土城區','汐止區','樹林區','淡水區','三峽區'];
</script>

<template>
  <div class="fsm-panel fsm-filter">
    <label>區域
      <select v-model="fs.restaurantFilters.district">
        <option
          v-for="d in districts"
          :key="d"
          :value="d"
        >{{ d === 'all' ? '全部' : d }}</option>
      </select>
    </label>
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
	position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
	display: flex; gap: 10px; padding: 8px 14px;
	background: rgba(20,20,30,0.92); border-radius: 6px; color: #ccc;
}
.fsm-filter label { display: flex; flex-direction: column; font-size: 11px; gap: 2px; }
.fsm-filter select { background: rgba(40,40,55,0.95); border: 1px solid #444;
	color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
</style>
