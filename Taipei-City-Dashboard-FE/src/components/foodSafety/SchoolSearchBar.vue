<!-- Top-center search bar that lets the user find a school by name. Uses
     foodSafetyStore.schoolSearchResults getter for filtered options.
     Selecting a result triggers selectSchool(school) which updates analysis
     focus, eases the map, and (if showSupplyChain on) draws supply arcs. -->
<script setup>
import { ref } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();
const focused = ref(false);

function pick(school) {
	fs.selectSchool(school);
	fs.schoolSearchQuery = school.properties.name;
	focused.value = false;
}
</script>

<template>
  <div class="fsm-panel fsm-search">
    <input
      v-model="fs.schoolSearchQuery"
      type="text"
      placeholder="搜尋學校名稱..."
      @focus="focused = true"
      @blur="setTimeout(() => focused = false, 150)"
    >
    <ul
      v-if="focused && fs.schoolSearchResults.length"
      class="fsm-search-dropdown"
    >
      <li
        v-for="s in fs.schoolSearchResults"
        :key="s.properties.id"
        @mousedown="pick(s)"
      >
        <span class="name">{{ s.properties.name }}</span>
        <span
          class="status"
          :class="`status-${s.properties.incident_status}`"
        >{{
          s.properties.incident_status === 'red' ? '事件' :
          s.properties.incident_status === 'yellow' ? '疑慮' : '正常'
        }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.fsm-panel { pointer-events: auto; }
.fsm-search {
	position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
	width: 320px; background: rgba(20,20,30,0.92);
	border-radius: 6px; padding: 6px 10px;
}
.fsm-search input {
	width: 100%; background: transparent; border: 1px solid #444;
	color: #fff; padding: 6px 10px; border-radius: 4px;
}
.fsm-search-dropdown {
	margin: 6px 0 0; padding: 0; list-style: none;
	background: rgba(20,20,30,0.95); border-radius: 4px;
	max-height: 240px; overflow-y: auto;
}
.fsm-search-dropdown li {
	display: flex; justify-content: space-between; padding: 6px 10px;
	cursor: pointer; color: #ddd;
}
.fsm-search-dropdown li:hover { background: rgba(60,60,80,0.6); }
.status-red    { color: #E53935; }
.status-yellow { color: #FFA000; }
.status-green  { color: #43A047; }
</style>
