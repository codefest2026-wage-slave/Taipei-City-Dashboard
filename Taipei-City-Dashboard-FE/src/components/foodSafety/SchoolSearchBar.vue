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
.fsm-search {
	pointer-events: auto;
	width: 100%;
	background: rgba(10, 18, 40, 0.5);
	border: 1px solid rgba(0, 229, 255, 0.25);
	border-radius: 4px;
	padding: 6px 10px;
	position: relative;
}
.fsm-search input {
	width: 100%;
	background: transparent;
	border: 1px solid rgba(0, 229, 255, 0.35);
	color: #d7e3f4;
	padding: 6px 10px;
	border-radius: 4px;
	font-size: 12px;
	box-sizing: border-box;
	outline: none;
}
.fsm-search input:focus {
	border-color: #00E5FF;
	box-shadow: 0 0 8px rgba(0, 229, 255, 0.4);
}
.fsm-search input::placeholder {
	color: rgba(143, 163, 198, 0.6);
}
.fsm-search-dropdown {
	position: absolute;
	top: calc(100% + 4px);
	left: 0;
	right: 0;
	margin: 0;
	padding: 0;
	list-style: none;
	background: rgba(10, 18, 40, 0.95);
	border: 1px solid rgba(0, 229, 255, 0.35);
	border-radius: 4px;
	max-height: 240px;
	overflow-y: auto;
	z-index: 100;
}
.fsm-search-dropdown li {
	display: flex;
	justify-content: space-between;
	padding: 6px 10px;
	cursor: pointer;
	color: #d7e3f4;
	font-size: 12px;
}
.fsm-search-dropdown li:hover {
	background: rgba(0, 229, 255, 0.1);
}
.status-red    { color: #FF1744; }
.status-yellow { color: #FFC107; }
.status-green  { color: #00E5FF; }
</style>
