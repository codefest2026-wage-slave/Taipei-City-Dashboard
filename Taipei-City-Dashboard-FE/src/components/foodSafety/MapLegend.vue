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
        <span class="truck truck-cyan" />
        <span>無事件</span>
      </div>
      <div class="legend-row">
        <span class="truck truck-red" />
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
	color: var(--color-normal-text, #f5f5f5);
	font-size: 12px;
}
.legend-col {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.legend-title {
	font-size: 10px;
	color: rgba(255, 255, 255, 0.7);
	text-transform: uppercase;
	letter-spacing: 1px;
	margin-bottom: 4px;
	border-bottom: 1px solid rgba(255, 255, 255, 0.12);
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
	background: radial-gradient(circle, #0288D1 0%, #0288D1 40%, rgba(79, 195, 247, 0.7) 75%, rgba(79, 195, 247, 0) 100%);
	box-shadow: 0 0 8px rgba(79, 195, 247, 0.7), 0 0 14px rgba(2, 136, 209, 0.5);
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
	border-color: #0288D1;
	box-shadow: 0 0 6px rgba(79, 195, 247, 0.7);
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
.ring-dot.ring-dot-cyan { background: #0288D1; }
.ring-dot.ring-dot-red { background: #FF1744; }
.truck {
	width: 18px;
	height: 14px;
	flex-shrink: 0;
	display: inline-block;
	-webkit-mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect x='2' y='12' width='8' height='10'/><rect x='11' y='8' width='17' height='14'/><circle cx='7' cy='25' r='2.5'/><circle cx='22' cy='25' r='2.5'/></svg>") center/contain no-repeat;
	mask: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect x='2' y='12' width='8' height='10'/><rect x='11' y='8' width='17' height='14'/><circle cx='7' cy='25' r='2.5'/><circle cx='22' cy='25' r='2.5'/></svg>") center/contain no-repeat;
}
.truck-cyan {
	background: #00E5FF;
	filter: drop-shadow(0 0 4px rgba(0, 229, 255, 0.7));
}
.truck-red {
	background: #FF1744;
	filter: drop-shadow(0 0 4px rgba(255, 23, 68, 0.7));
}
</style>
