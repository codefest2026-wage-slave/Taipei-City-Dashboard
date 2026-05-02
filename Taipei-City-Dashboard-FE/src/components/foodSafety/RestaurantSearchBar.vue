<!-- Search input for the 校外 mode — finds a business by name or address from
     the FAIL-bearing restaurants dataset. Selecting a result eases the map
     and populates the right-side RestaurantInspectionPanel. Lives inside
     the FoodSafetyExternalLegend dashboard chart card. -->
<script setup>
import { ref } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();
const focused = ref(false);
let blurTimer = null;

function onFocus() { focused.value = true; }
function onBlur() {
	blurTimer = setTimeout(() => { focused.value = false; }, 150);
}
function pick(restaurant) {
	if (blurTimer) clearTimeout(blurTimer);
	fs.selectRestaurant(restaurant);
	fs.restaurantSearchQuery = restaurant.properties.name;
	focused.value = false;
}
</script>

<template>
  <div class="fsm-search">
    <input
      v-model="fs.restaurantSearchQuery"
      type="text"
      placeholder="搜尋業者名稱或地址..."
      @focus="onFocus"
      @blur="onBlur"
    >
    <ul
      v-if="focused && fs.restaurantSearchResults.length"
      class="fsm-search-dropdown"
    >
      <li
        v-for="r in fs.restaurantSearchResults"
        :key="r.properties.id"
        @mousedown="pick(r)"
      >
        <span class="name">{{ r.properties.name }}</span>
        <span
          class="hz"
          :class="`hz-${r.properties.hazard_level || 'info'}`"
        >{{ (r.properties.hazard_level || "info").toUpperCase() }}</span>
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
.fsm-search input:focus { border-color: rgba(0, 229, 255, 0.5); }
.fsm-search input::placeholder { color: rgba(255, 255, 255, 0.4); }
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
	align-items: center;
	gap: 8px;
	padding: 6px 10px;
	cursor: pointer;
	color: var(--color-normal-text, #f5f5f5);
	font-size: 12px;
}
.fsm-search-dropdown li:hover { background: rgba(255, 255, 255, 0.08); }
.name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hz {
	font-size: 9px; font-weight: 600; letter-spacing: 1px;
	padding: 1px 5px; border-radius: 2px;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.hz-critical { background: #FF1744; color: #fff; }
.hz-high     { background: #FF6D00; color: #fff; }
.hz-medium   { background: #FFC107; color: #0A1228; }
.hz-low      { background: #00E676; color: #0A1228; }
.hz-info     { background: rgba(255, 255, 255, 0.12); color: rgba(255, 255, 255, 0.7); }
</style>
