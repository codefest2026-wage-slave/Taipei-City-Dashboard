<!-- Bottom-left legend panel. Static reference for color/shape semantics
     across schools, incidents, suppliers, and supply chain lines.
     Pure visual reference — no interactive state. -->
<script setup></script>

<template>
  <div class="fsm-panel fsm-legend">
    <h4>圖例</h4>
    <div class="legend-section">
      <div class="legend-title">
        學校
      </div>
      <div class="legend-row">
        <span class="dot s-normal" />一般學校
      </div>
      <div class="legend-row">
        <span class="dot s-warning" />供應商有疑慮
      </div>
      <div class="legend-row">
        <span class="dot s-incident" />曾發生食安事件
      </div>
    </div>
    <div class="legend-section">
      <div class="legend-title">
        事件等級
      </div>
      <div class="legend-row">
        <span class="dot sev-critical" />Critical
      </div>
      <div class="legend-row">
        <span class="dot sev-high" />High
      </div>
      <div class="legend-row">
        <span class="dot sev-medium" />Medium
      </div>
      <div class="legend-row">
        <span class="dot sev-low" />Low
      </div>
    </div>
    <div class="legend-section">
      <div class="legend-title">
        供應商
      </div>
      <div class="legend-row">
        <span class="dot p-normal" />正常
      </div>
      <div class="legend-row">
        <span class="dot p-bad" />有問題
      </div>
    </div>
    <div class="legend-section">
      <div class="legend-title">
        連線
      </div>
      <div class="legend-row">
        <span class="line line-arc" />供應鏈連線
      </div>
    </div>
  </div>
</template>

<style scoped>
.fsm-legend {
	pointer-events: auto;
	position: absolute; bottom: 16px; left: 16px;
	background: rgba(20,20,30,0.92); border-radius: 6px;
	padding: 10px 14px; color: #ddd; min-width: 160px;
	font-size: 12px;
}
.fsm-legend h4 { margin: 0 0 6px; font-size: 13px; color: #aaa; letter-spacing: 1px; }
.legend-section { margin: 8px 0; }
.legend-title { font-size: 10px; color: #888; text-transform: uppercase;
                letter-spacing: 1px; margin-bottom: 4px; }
.legend-row { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.s-normal   { background: #00E5FF; box-shadow: 0 0 6px #00E5FF; }
.s-warning  { background: #FFC107; box-shadow: 0 0 6px #FFC107; }
.s-incident { background: #FF1744; box-shadow: 0 0 6px #FF1744; }
.sev-critical { background: #FF1744; box-shadow: 0 0 6px #FF1744; }
.sev-high     { background: #FF6D00; box-shadow: 0 0 6px #FF6D00; }
.sev-medium   { background: #FFC107; box-shadow: 0 0 6px #FFC107; }
.sev-low      { background: #00E676; box-shadow: 0 0 6px #00E676; }
.p-normal { background: #FFD54F; box-shadow: 0 0 6px #FFD54F; }
.p-bad    { background: #FF1744; box-shadow: 0 0 6px #FF1744; }
.line { width: 18px; height: 2px; flex-shrink: 0;
        background: linear-gradient(90deg, #00E5FF, #FF1744);
        box-shadow: 0 0 4px rgba(0, 229, 255, 0.6); }
</style>
