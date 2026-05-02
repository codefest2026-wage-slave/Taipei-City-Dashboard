<!-- Right-side panel showing inspection history of selected restaurant.
     Reads from foodSafetyStore.selectedRestaurant + restaurantInspections cache. -->
<script setup>
import { computed } from "vue";
import { useFoodSafetyStore } from "../../store/foodSafetyStore";

const fs = useFoodSafetyStore();

const restaurant = computed(() => fs.selectedRestaurant);
const restaurantId = computed(() => {
	const r = restaurant.value;
	if (!r) return null;
	return r.properties.id || r.properties.name;
});
const inspection = computed(() => {
	const id = restaurantId.value;
	if (!id) return null;
	return fs.restaurantInspections[id] || null;
});
</script>

<template>
  <div class="fsm-panel fsm-cyber-panel fsm-inspection">
    <div
      v-if="!restaurant"
      class="fsm-empty"
    >
      點選地圖上的餐廳以檢視稽查歷史
    </div>
    <div
      v-else
      class="fsm-view"
    >
      <h3>{{ restaurant.properties.name }}</h3>
      <p>{{ restaurant.properties.address || `${restaurant.properties.city} · ${restaurant.properties.district}` }}</p>
      <div
        class="badge"
        :class="`grade-${restaurant.properties.grade}`"
      >
        {{ restaurant.properties.grade || '未評' }}
      </div>
      <h4>稽查歷史</h4>
      <ul
        v-if="inspection"
        class="history"
      >
        <li
          v-for="(h, i) in inspection.history"
          :key="i"
          :class="`row-${h.status.toLowerCase()}`"
        >
          <span class="date">{{ h.date }}</span>
          <span class="status">{{ h.status }}</span>
          <span class="issue">{{ h.issue }}</span>
        </li>
      </ul>
      <p
        v-else
        class="hint"
      >
        尚無此餐廳的稽查歷史 mock 資料。
      </p>
    </div>
  </div>
</template>

<style scoped>
.fsm-inspection {
	pointer-events: auto;
	position: absolute; top: 80px; right: 16px; width: 320px;
	max-height: calc(100vh - 280px); overflow-y: auto;
	padding: 14px;
}
.fsm-empty { color: rgba(255, 255, 255, 0.5); font-size: 13px; }
.fsm-view h3 {
	margin: 0; font-size: 18px;
	color: #FFFFFF; letter-spacing: 1px;
}
.fsm-view p  { margin: 4px 0; font-size: 12px; color: rgba(255, 255, 255, 0.55); }
.fsm-view h4 {
	margin: 12px 0 4px; font-size: 11px;
	color: rgba(255, 255, 255, 0.65);
	text-transform: uppercase; letter-spacing: 2px;
	font-weight: 600;
}
.badge {
	display: inline-block; padding: 3px 10px; border-radius: 2px;
	font-size: 11px; font-weight: 600; margin: 4px 0;
	letter-spacing: 1px;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.grade-優      { background: #00E676; color: #0A1228; box-shadow: 0 0 10px rgba(0,230,118,0.5); }
.grade-良      { background: #FFC107; color: #0A1228; box-shadow: 0 0 10px rgba(255,193,7,0.5); }
.grade-需改善  { background: #FF1744; color: #fff; box-shadow: 0 0 10px rgba(255,23,68,0.5); }
.history { list-style: none; padding: 0; margin: 0; }
.history li {
	display: grid; grid-template-columns: 90px 50px 1fr; gap: 6px;
	padding: 7px 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	font-size: 12px; color: #F5F5F5;
}
.history .date {
	color: rgba(255, 255, 255, 0.55);
	font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.history .status {
	font-family: 'JetBrains Mono', 'Courier New', monospace;
	letter-spacing: 1px;
}
.row-pass {
	background: linear-gradient(90deg, rgba(0,230,118,0.06), transparent);
}
.row-pass .status { color: #00E676; font-weight: 600; text-shadow: 0 0 6px rgba(0,230,118,0.5); }
.row-fail {
	background: linear-gradient(90deg, rgba(255,23,68,0.08), transparent);
}
.row-fail .status { color: #FF1744; font-weight: 600; text-shadow: 0 0 6px rgba(255,23,68,0.6); }
.hint { color: rgba(255, 255, 255, 0.5); font-size: 12px; }
</style>
