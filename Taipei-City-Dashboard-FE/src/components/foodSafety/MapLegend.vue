<!-- Sidebar legend panel for the school map. Shows only the visual semantics
     used in the simplified data point design: school colors, selected ring,
     supplier ring colors. -->
<script setup></script>

<template>
  <div class="fsm-panel fsm-cyber-panel fsm-legend">
    <h4>圖例</h4>
    <div class="legend-section">
      <div class="legend-title">
        學校
      </div>
      <div class="legend-row">
        <span class="dot s-normal" />
        <span>無事件</span>
      </div>
      <div class="legend-row">
        <span class="dot s-incident" />
        <span>曾有事件</span>
      </div>
      <div class="legend-row">
        <span class="ring-wrap"><span class="ring-outer" /><span class="ring-dot" /></span>
        <span>已選取</span>
      </div>
    </div>
    <div class="legend-section">
      <div class="legend-title">
        供應商
      </div>
      <div class="legend-row">
        <span class="ring-wrap"><span class="ring-outer ring-cyan" /><span class="ring-dot ring-dot-cyan" /></span>
        <span>無事件</span>
      </div>
      <div class="legend-row">
        <span class="ring-wrap"><span class="ring-outer ring-red" /><span class="ring-dot ring-dot-red" /></span>
        <span>有事件</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fsm-legend {
	pointer-events: auto;
	padding: 10px 14px;
	color: var(--fsm-text, #d7e3f4);
	font-size: 12px;
}
.fsm-legend h4 {
	margin: 0 0 6px;
	font-size: 13px;
	color: var(--fsm-cyan, #00e5ff);
	letter-spacing: 2px;
	text-transform: uppercase;
}
.legend-section { margin: 8px 0; }
.legend-title {
	font-size: 10px;
	color: #8fa3c6;
	text-transform: uppercase;
	letter-spacing: 1px;
	margin-bottom: 4px;
}
.legend-row {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 3px 0;
}
.dot {
	width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0;
}
.s-normal   { background: #00E5FF; box-shadow: 0 0 6px #00E5FF; }
.s-incident { background: #FF1744; box-shadow: 0 0 6px #FF1744; }
/* Selected school: dot inside an outer ring */
.ring-wrap {
	position: relative;
	width: 18px; height: 18px;
	flex-shrink: 0;
	display: inline-flex;
	align-items: center;
	justify-content: center;
}
.ring-outer {
	position: absolute;
	inset: 0;
	border-radius: 50%;
	border: 2px solid #00E5FF;
	box-shadow: 0 0 6px #00E5FF80;
}
.ring-outer.ring-cyan { border-color: #00E5FF; box-shadow: 0 0 6px #00E5FF80; }
.ring-outer.ring-red  { border-color: #FF1744; box-shadow: 0 0 6px #FF174480; }
.ring-dot {
	width: 5px; height: 5px; border-radius: 50%;
	background: #00E5FF;
}
.ring-dot.ring-dot-cyan { background: #00E5FF; }
.ring-dot.ring-dot-red  { background: #FF1744; }
</style>
