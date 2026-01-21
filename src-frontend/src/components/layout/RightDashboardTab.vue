<template>
  <div class="dashboard-content">
    <!-- 连接状态卡片 -->
    <div class="status-card">
      <div class="status-header">
        <span class="status-label">连接状态</span>
        <span class="status-indicator connected">已连接</span>
      </div>
      <div class="status-info">
        <div class="info-item">
          <span class="label">飞行模式</span>
          <span class="value">MANUAL</span>
        </div>
        <div class="info-item">
          <span class="label">数据率</span>
          <span class="value">50 Hz</span>
        </div>
      </div>
    </div>

    <!-- 姿态信息卡片 -->
    <div class="attitude-card">
      <h4 class="card-title">姿态信息</h4>
      <div class="attitude-grid">
        <div class="attitude-item">
          <span class="att-label">Roll</span>
          <span class="att-value">0.0°</span>
        </div>
        <div class="attitude-item">
          <span class="att-label">Pitch</span>
          <span class="att-value">0.0°</span>
        </div>
        <div class="attitude-item">
          <span class="att-label">Yaw</span>
          <span class="att-value">0.0°</span>
        </div>
      </div>
    </div>

    <!-- 电池状态卡片 -->
    <div class="battery-card">
      <h4 class="card-title">电池状态</h4>
      <div class="battery-level">
        <div class="battery-bar">
          <div class="battery-fill" style="width: 100%;"></div>
        </div>
        <span class="battery-text">100%</span>
      </div>
      <div class="battery-info">
        <span class="voltage">12.6 V</span>
        <span class="current">10.2 A</span>
      </div>
    </div>

    <!-- GPS 信息卡片 -->
    <div class="gps-card">
      <h4 class="card-title">GPS 状态</h4>
      <div class="gps-info">
        <div class="gps-item">
          <span class="gps-label">卫星数</span>
          <span class="gps-value">12</span>
        </div>
        <div class="gps-item">
          <span class="gps-label">信号强度</span>
          <span class="gps-value">强</span>
        </div>
        <div class="gps-item">
          <span class="gps-label">定位精度</span>
          <span class="gps-value">±2m</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 仪表盘组件
</script>

<style scoped>
/* ==================== 通用卡片样式 ==================== */
.card-title {
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 2px solid #3288fa;
}

.status-card, .attitude-card, .battery-card, .gps-card {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

/* ==================== 状态卡片 ==================== */
.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.status-label {
  color: #cccccc;
  font-size: 13px;
}

.status-indicator {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-indicator.connected {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
}

.status-indicator.disconnected {
  background: rgba(255, 87, 34, 0.2);
  color: #ff5722;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  color: #cccccc;
  font-size: 12px;
}

.info-item .value {
  color: #3288fa;
  font-weight: 500;
}

/* ==================== 姿态卡片 ==================== */
.attitude-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attitude-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(30, 30, 30, 0.5);
  padding: 10px;
  border-radius: 6px;
}

.att-label {
  color: #999999;
  font-size: 12px;
}

.att-value {
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
}

/* ==================== 电池卡片 ==================== */
.battery-level {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.battery-bar {
  flex: 1;
  height: 20px;
  background: rgba(30, 30, 30, 0.8);
  border-radius: 10px;
  overflow: hidden;
  position: relative;
}

.battery-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  border-radius: 10px;
  transition: width 0.3s ease;
}

.battery-text {
  color: #4caf50;
  font-size: 14px;
  font-weight: 600;
  min-width: 45px;
}

.battery-info {
  display: flex;
  justify-content: space-between;
  color: #cccccc;
  font-size: 12px;
}

/* ==================== GPS 卡片 ==================== */
.gps-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.gps-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(30, 30, 30, 0.5);
  padding: 10px;
  border-radius: 6px;
}

.gps-label {
  color: #999999;
  font-size: 12px;
}

.gps-value {
  color: #3288fa;
  font-size: 13px;
  font-weight: 500;
}
</style>