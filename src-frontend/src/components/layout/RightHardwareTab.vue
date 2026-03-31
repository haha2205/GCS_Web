<template>
  <div class="hardware-content">
    <div class="hardware-section">
      <h4 class="hardware-title">系统模块</h4>
      <div class="hardware-list">
        <div class="hardware-item">
          <div class="hw-name">IMU</div>
          <div class="hw-status ok">正常</div>
          <div class="hw-delay">2 ms</div>
        </div>
        <div class="hardware-item">
          <div class="hw-name">GPS</div>
          <div class="hw-status ok">正常</div>
          <div class="hw-delay">50 ms</div>
        </div>
        <div class="hardware-item">
          <div class="hw-name">磁力计</div>
          <div class="hw-status ok">正常</div>
          <div class="hw-delay">5 ms</div>
        </div>
        <div class="hardware-item">
          <div class="hw-name">气压计</div>
          <div class="hw-status ok">正常</div>
          <div class="hw-delay">8 ms</div>
        </div>
        <div class="hardware-item">
          <div class="hw-name">LiDAR</div>
          <div class="hw-status warning">延迟</div>
          <div class="hw-delay">150 ms</div>
        </div>
        <div class="hardware-item">
          <div class="hw-name">相机</div>
          <div class="hw-status ok">正常</div>
          <div class="hw-delay">33 ms</div>
        </div>
      </div>
    </div>

    <div class="hardware-section">
      <h4 class="hardware-title">温度监控</h4>
      <div class="temp-monitors">
        <div class="temp-item">
          <span class="temp-label">CPU</span>
          <span class="temp-value">45°C</span>
          <div class="temp-bar"><div class="temp-fill" style="width: 45%;"></div></div>
        </div>
        <div class="temp-item">
          <span class="temp-label">飞控</span>
          <span class="temp-value">38°C</span>
          <div class="temp-bar"><div class="temp-fill" style="width: 38%;"></div></div>
        </div>
        <div class="temp-item">
          <span class="temp-label">电机</span>
          <span class="temp-value">52°C</span>
          <div class="temp-bar"><div class="temp-fill" style="width: 52%; background: #ff9800;"></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 硬件状态监控组件
</script>

<style scoped>
/* ==================== 硬件状态 ==================== */
.hardware-section {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.hardware-title {
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 10px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #3288fa;
}

.hardware-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hardware-item {
  display: grid;
  grid-template-columns: 1fr 60px 60px;
  align-items: center;
  background: rgba(30, 30, 30, 0.5);
  padding: 10px;
  border-radius: 6px;
  font-size: 12px;
}

.hw-name {
  color: #cccccc;
  font-weight: 500;
}

.hw-status {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  text-align: center;
}

.hw-status.ok {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.hw-status.warning {
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}

.hw-status.error {
  background: rgba(255, 87, 34, 0.2);
  color: #ff5722;
}

.hw-delay {
  color: #999999;
  text-align: right;
}

/* ==================== 温度监控 ==================== */
.temp-monitors {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.temp-item {
  background: rgba(30, 30, 30, 0.5);
  padding: 10px;
  border-radius: 6px;
}

.temp-label {
  color: #999999;
  font-size: 12px;
  display: block;
  margin-bottom: 6px;
}

.temp-value {
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  float: right;
}

.temp-bar {
  height: 6px;
  background: rgba(50, 50, 50, 0.8);
  border-radius: 3px;
  overflow: hidden;
  margin-top: 6px;
  clear: both;
}

.temp-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  border-radius: 3px;
  transition: width 0.3s ease;
}
</style>