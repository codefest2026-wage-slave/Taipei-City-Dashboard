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
  <div class="fsm-panel fsm-inspection">
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
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 14px; color: #ddd;
}
.fsm-empty { color: #888; font-size: 13px; }
.fsm-view h3 { margin: 0; font-size: 16px; color: #fff; }
.fsm-view p  { margin: 4px 0; font-size: 12px; color: #bbb; }
.fsm-view h4 { margin: 12px 0 4px; font-size: 12px; color: #aaa; text-transform: uppercase; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
         font-size: 11px; font-weight: 600; margin: 4px 0; }
.grade-優      { background: #43A047; color: #fff; }
.grade-良      { background: #FFA000; color: #fff; }
.grade-需改善  { background: #E53935; color: #fff; }
.history { list-style: none; padding: 0; margin: 0; }
.history li { display: grid; grid-template-columns: 90px 50px 1fr; gap: 6px;
              padding: 6px 0; border-bottom: 1px solid #333; font-size: 12px; }
.row-pass .status { color: #43A047; font-weight: 600; }
.row-fail .status { color: #E53935; font-weight: 600; }
.hint { color: #888; font-size: 12px; }
</style>
