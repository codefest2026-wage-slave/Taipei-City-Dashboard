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
      <div class="badge-row">
        <span
          class="badge"
          :class="`hz-${restaurant.properties.hazard_level || 'info'}`"
        >{{
          (restaurant.properties.hazard_level || "info").toUpperCase()
        }}</span>
        <span
          v-if="restaurant.properties.business_type"
          class="biz-type"
        >{{ restaurant.properties.business_type }}</span>
      </div>
      <div class="stats">
        <span><label>違規</label>{{ restaurant.properties.fail_count || 0 }} 次</span>
        <span><label>稽查</label>{{ restaurant.properties.total_inspections || 0 }} 次</span>
        <span v-if="restaurant.properties.latest_fail_date">
          <label>最近</label>{{ restaurant.properties.latest_fail_date }}
        </span>
      </div>
      <h4>稽查歷史</h4>
      <ul
        v-if="inspection && inspection.history.length"
        class="history"
      >
        <li
          v-for="(h, i) in inspection.history"
          :key="i"
          :class="`row-${h.status.toLowerCase()}`"
        >
          <div class="history-head">
            <span class="date">{{ h.date }}</span>
            <span class="status">{{ h.status }}</span>
            <span class="issue">{{ h.issue }}</span>
          </div>
          <div
            v-if="h.product_name && h.product_name !== '-'"
            class="history-meta"
          >
            <label>產品</label>{{ h.product_name }}
          </div>
          <div
            v-if="h.hazard_basis"
            class="history-meta"
          >
            <label>判定依據</label>{{ h.hazard_basis }}
          </div>
        </li>
      </ul>
      <p
        v-else
        class="hint"
      >
        尚無稽查歷史紀錄
      </p>
    </div>
  </div>
</template>

<style scoped>
.fsm-inspection {
	pointer-events: auto;
	position: absolute; top: 16px; right: 16px; width: 320px;
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
.badge-row {
	display: flex; align-items: center; gap: 8px; margin: 6px 0;
	flex-wrap: wrap;
}
.badge {
	display: inline-block; padding: 3px 10px; border-radius: 2px;
	font-size: 11px; font-weight: 600;
	letter-spacing: 1px;
	font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.hz-critical { background: #FF1744; color: #fff; box-shadow: 0 0 10px rgba(255, 23, 68, 0.5); }
.hz-high     { background: #FF6D00; color: #fff; box-shadow: 0 0 10px rgba(255, 109, 0, 0.5); }
.hz-medium   { background: #FFC107; color: #0A1228; box-shadow: 0 0 10px rgba(255, 193, 7, 0.5); }
.hz-low      { background: #00E5FF; color: #0A1228; box-shadow: 0 0 8px rgba(0, 229, 255, 0.4); }
.hz-info     { background: rgba(255, 255, 255, 0.1); color: rgba(255, 255, 255, 0.7); }
.biz-type {
	font-size: 10px; color: rgba(255, 255, 255, 0.55);
	padding: 2px 6px; border: 1px solid rgba(255, 255, 255, 0.15);
	border-radius: 2px;
}
.stats {
	display: flex; gap: 14px; margin: 8px 0; padding: 6px 0;
	font-size: 12px; color: rgba(255, 255, 255, 0.85);
	border-top: 1px solid rgba(255, 255, 255, 0.08);
	border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.stats label {
	display: inline-block; margin-right: 4px;
	font-size: 10px; color: rgba(255, 255, 255, 0.5);
	letter-spacing: 1px;
}
.history { list-style: none; padding: 0; margin: 0; }
.history li {
	display: flex; flex-direction: column; gap: 3px;
	padding: 8px 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.08);
	font-size: 12px; color: #F5F5F5;
}
.history-head {
	display: grid; grid-template-columns: 90px 50px 1fr; gap: 6px;
}
.history-meta {
	font-size: 11px; color: rgba(255, 255, 255, 0.7);
	padding-left: 96px;
}
.history-meta label {
	display: inline-block; width: 60px;
	font-size: 9px; color: rgba(255, 255, 255, 0.45);
	letter-spacing: 1px; text-transform: uppercase;
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
