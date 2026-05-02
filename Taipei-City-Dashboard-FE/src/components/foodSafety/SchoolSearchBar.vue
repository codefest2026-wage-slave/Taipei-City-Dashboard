<!-- Search input that lets the user find a school by name. Lives inside the
     FoodSafetyControls card body — the parent dashboardcomponent-chart has
     overflow-y: scroll, so the results dropdown is rendered INLINE (not
     absolute) so it can flow within the scroll area instead of being clipped. -->
<script setup>
import { ref } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();
const focused = ref(false);
let blurTimer = null;

function onFocus() {
	focused.value = true;
}
function onBlur() {
	// Slight delay so a @mousedown on a dropdown <li> can fire its pick()
	// before this handler hides the list.
	blurTimer = setTimeout(() => {
		focused.value = false;
	}, 150);
}
function pick(school) {
	if (blurTimer) clearTimeout(blurTimer);
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
      @focus="onFocus"
      @blur="onBlur"
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
          :class="`status-${s.properties.recent_alert}`"
        >{{
          s.properties.recent_alert === "red" ? "警示" : "正常"
        }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.fsm-search {
	width: 100%;
	box-sizing: border-box;
}
.fsm-search input {
	width: 100%;
	box-sizing: border-box;
	padding: 6px 10px;
	font-size: 12px;
	color: var(--color-normal-text, #f5f5f5);
	background: rgba(255, 255, 255, 0.03);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 3px;
	outline: none;
}
.fsm-search input:focus {
	border-color: rgba(0, 229, 255, 0.5);
}
.fsm-search input::placeholder {
	color: rgba(255, 255, 255, 0.4);
}
.fsm-search-dropdown {
	margin: 4px 0 0;
	padding: 0;
	list-style: none;
	background: rgba(255, 255, 255, 0.04);
	border: 1px solid rgba(255, 255, 255, 0.12);
	border-radius: 3px;
	max-height: 200px;
	overflow-y: auto;
}
.fsm-search-dropdown li {
	display: flex;
	justify-content: space-between;
	padding: 6px 10px;
	cursor: pointer;
	color: var(--color-normal-text, #f5f5f5);
	font-size: 12px;
}
.fsm-search-dropdown li:hover {
	background: rgba(255, 255, 255, 0.08);
}
.status-red    { color: #FF1744; }
.status-normal { color: rgba(255, 255, 255, 0.5); }
</style>
