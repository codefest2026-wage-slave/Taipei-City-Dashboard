<!-- Search input that lets the user find a school by name. Lives inside the
     FoodSafetyControls card body, so styling is intentionally plain (no extra
     panel framing) to match the surrounding dashboard component card. -->
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
  <div class="fsm-search">
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
          s.properties.incident_status === "red" ? "事件" :
          s.properties.incident_status === "yellow" ? "疑慮" : "正常"
        }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.fsm-search {
	position: relative;
	width: 100%;
	box-sizing: border-box;
}
.fsm-search input {
	width: 100%;
	box-sizing: border-box;
	padding: 6px 10px;
	font-size: 12px;
	color: var(--color-normal-text, #d7e3f4);
	background: rgba(255, 255, 255, 0.03);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 3px;
	outline: none;
}
.fsm-search input:focus {
	border-color: rgba(0, 229, 255, 0.5);
}
.fsm-search input::placeholder {
	color: rgba(215, 227, 244, 0.4);
}
.fsm-search-dropdown {
	position: absolute;
	top: calc(100% + 2px);
	left: 0;
	right: 0;
	margin: 0;
	padding: 0;
	list-style: none;
	background: var(--color-component-background, #1f2125);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 3px;
	max-height: 240px;
	overflow-y: auto;
	z-index: 100;
}
.fsm-search-dropdown li {
	display: flex;
	justify-content: space-between;
	padding: 6px 10px;
	cursor: pointer;
	color: var(--color-normal-text, #d7e3f4);
	font-size: 12px;
}
.fsm-search-dropdown li:hover {
	background: rgba(255, 255, 255, 0.05);
}
.status-red    { color: #FF1744; }
.status-yellow { color: #FFC107; }
.status-green  { color: #8fa3c6; }
</style>