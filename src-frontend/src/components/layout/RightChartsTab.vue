<template>
  <div class="charts-content">
    <div class="chart-section">
      <h4 class="chart-title">速度曲线</h4>
      <div class="chart-placeholder">
        <div class="chart-grid">
          <div class="chart-axis-y">
            <span>50</span>
            <span>25</span>
            <span>0</span>
          </div>
          <div class="chart-waveform">
            <svg viewBox="0 0 300 100" class="waveform-svg">
              <path 
                d="M0 50 Q30 50 60 50 T120 50 T180 50 T240 50 T300 50"
                fill="none"
                stroke="#3288fa"
                stroke-width="2"
              />
              <path 
                d="M0 70 Q30 65 60 70 T120 70 T180 70 T240 70 T300 70"
                fill="none"
                stroke="#ff9800"
                stroke-width="2"
              />
            </svg>
          </div>
        </div>
        <div class="chart-legend">
          <span class="legend-item"><span class="color-dot" style="background: #3288fa;"></span>水平速度</span>
          <span class="legend-item"><span class="color-dot" style="background: #ff9800;"></span>垂直速度</span>
        </div>
      </div>
    </div>

    <div class="chart-section">
      <h4 class="chart-title">高度曲线</h4>
      <div class="chart-placeholder">
        <div class="chart-grid">
          <div class="chart-axis-y">
            <span>100</span>
            <span>50</span>
            <span>0</span>
          </div>
          <div class="chart-waveform">
            <svg viewBox="0 0 300 100" class="waveform-svg">
              <path 
                d="M0 80 Q40 75 80 70 T160 60 T240 50 T300 45"
                fill="none"
                stroke="#4caf50"
                stroke-width="2"
              />
            </svg>
          </div>
        </div>
        <div class="chart-legend">
          <span class="legend-item"><span class="color-dot" style="background: #4caf50;"></span>相对高度</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 曲线图表组件
// 后续可以集成 ECharts 实现更高级的图表功能
</script>

<style scoped>
/* ==================== 曲线图表 ==================== */
.chart-section {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.chart-title {
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 10px 0;
}

.chart-placeholder {
  height: 120px;
  background: rgba(30, 30, 30, 0.8);
  border-radius: 6px;
  padding: 10px;
}

.chart-grid {
  display: flex;
  height: 100%;
  gap: 10px;
}

.chart-axis-y {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  color: #666666;
  font-size: 10px;
  min-width: 25px;
}

.chart-waveform {
  flex: 1;
  position: relative;
}

.waveform-svg {
  width: 100%;
  height: 100%;
}

.chart-legend {
  display: flex;
  gap: 15px;
  justify-content: center;
  margin-top: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #999999;
  font-size: 11px;
}

.color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
</style>