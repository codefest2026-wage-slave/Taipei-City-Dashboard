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
  <div class="fsm-panel fsm-cyber-panel fsm-search">
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
	width: 320px; padding: 6px 10px;
}
.fsm-search input {
	width: 100%; background: rgba(0,0,0,0.35);
	border: 1px solid rgba(0,229,255,0.25);
	color: #D7E3F4; padding: 6px 10px; border-radius: 3px;
	font-size: 13px; letter-spacing: 0.5px;
	transition: border-color 120ms ease, box-shadow 120ms ease;
}
.fsm-search input::placeholder { color: #8FA3C6; }
.fsm-search input:focus {
	outline: none;
	border-color: #00E5FF;
	box-shadow: 0 0 8px rgba(0,229,255,0.45);
}
.fsm-search-dropdown {
	margin: 6px 0 0; padding: 0; list-style: none;
	background: rgba(10,18,40,0.95);
	border: 1px solid rgba(0,229,255,0.25);
	border-radius: 3px;
	max-height: 240px; overflow-y: auto;
}
.fsm-search-dropdown li {
	display: flex; justify-content: space-between; padding: 6px 10px;
	cursor: pointer; color: #D7E3F4;
	border-bottom: 1px solid rgba(0,229,255,0.08);
	font-size: 13px;
}
.fsm-search-dropdown li:last-child { border-bottom: none; }
.fsm-search-dropdown li:hover {
	background: rgba(0,229,255,0.08);
	color: #00E5FF;
}
.status { font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 11px; }
.status-red    { color: #FF1744; text-shadow: 0 0 6px rgba(255,23,68,0.6); }
.status-yellow { color: #FFC107; text-shadow: 0 0 6px rgba(255,193,7,0.6); }
.status-green  { color: #00E676; text-shadow: 0 0 6px rgba(0,230,118,0.6); }
</style>
