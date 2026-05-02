<!-- Bottom horizontal strip of recent food-safety incidents. Default shows
     the 5 most recent; remaining items accessible via horizontal scroll
     (D2 in spec). Click a card → fs.selectIncident(...). -->
<script setup>
import { useFoodSafetyStore } from "../../store/foodSafetyStore";
const fs = useFoodSafetyStore();
</script>

<template>
  <div class="fsm-panel fsm-strip">
    <div
      v-for="inc in fs.recentIncidents"
      :key="inc.id"
      class="fsm-card"
      :class="`sev-${inc.severity.toLowerCase()}`"
      @click="fs.selectIncident(inc)"
    >
      <div class="card-head">
        <span class="date">{{ inc.occurred_at }}</span>
        <span class="severity">{{ inc.severity }}</span>
      </div>
      <div class="title">
        {{ inc.title }}
      </div>
      <div class="school">
        {{ inc.school_name }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.fsm-strip {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 50%;
	transform: translateX(-50%); width: 80%; min-width: 600px; max-width: 1100px;
	display: flex; gap: 10px; overflow-x: auto;
	background: rgba(20,20,30,0.85); border-radius: 6px;
	padding: 10px;
}
.fsm-card {
	flex: 0 0 200px; padding: 8px 10px; border-radius: 4px;
	background: rgba(40,40,55,0.95); border-left: 3px solid #43A047;
	cursor: pointer; transition: background 0.15s;
	color: #ddd;
}
.fsm-card:hover { background: rgba(60,60,80,0.95); }
.fsm-card.sev-critical { border-left-color: #E53935; }
.fsm-card.sev-high     { border-left-color: #FF6D00; }
.fsm-card.sev-medium   { border-left-color: #FFA000; }
.card-head { display: flex; justify-content: space-between; font-size: 11px;
             color: #888; }
.title { font-size: 12px; color: #fff; margin-top: 4px;
         display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
         overflow: hidden; }
.school { font-size: 11px; color: #aaa; margin-top: 4px; }
</style>
