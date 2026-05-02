<!-- 2-column compact legend: 學校 (left) and 供應商 (right). -->
<script setup></script>

<template>
  <div class="fsm-legend">
    <div class="legend-col">
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
        <span class="ring-wrap"><span class="ring-outer ring-cyan" /><span class="ring-dot ring-dot-cyan" /></span>
        <span>已選取</span>
      </div>
    </div>
    <div class="legend-col">
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
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: var(--font-s);
	padding: var(--font-s) 0 0;
	color: #d7e3f4;
	font-size: 12px;
}
.legend-col {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.legend-title {
	font-size: 10px;
	color: #00E5FF;
	text-transform: uppercase;
	letter-spacing: 1px;
	margin-bottom: 4px;
	border-bottom: 1px solid rgba(0, 229, 255, 0.2);
	padding-bottom: 2px;
}
.legend-row {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 2px 0;
}
.dot {
	width: 10px;
	height: 10px;
	border-radius: 50%;
	display: inline-block;
	flex-shrink: 0;
}
.s-normal {
	background: radial-gradient(circle, #66F2FF 0%, #00E5FF 60%, rgba(0, 229, 255, 0) 100%);
	box-shadow: 0 0 8px #00E5FF, 0 0 14px rgba(0, 229, 255, 0.6);
}
.s-incident {
	background: radial-gradient(circle, #FF6B85 0%, #FF1744 60%, rgba(255, 23, 68, 0) 100%);
	box-shadow: 0 0 8px #FF1744, 0 0 14px rgba(255, 23, 68, 0.6);
}
.ring-wrap {
	position: relative;
	width: 16px;
	height: 16px;
	flex-shrink: 0;
	display: inline-flex;
	align-items: center;
	justify-content: center;
}
.ring-outer {
	position: absolute;
	inset: 0;
	border-radius: 50%;
	border: 1.5px solid #00E5FF;
}
.ring-outer.ring-cyan {
	border-color: #00E5FF;
	box-shadow: 0 0 6px rgba(0, 229, 255, 0.7);
}
.ring-outer.ring-red {
	border-color: #FF1744;
	box-shadow: 0 0 6px rgba(255, 23, 68, 0.7);
}
.ring-dot {
	width: 4px;
	height: 4px;
	border-radius: 50%;
}
.ring-dot.ring-dot-cyan { background: #00E5FF; }
.ring-dot.ring-dot-red { background: #FF1744; }
</style>
