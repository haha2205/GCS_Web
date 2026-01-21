<template>
  <div class="dashboard">
    <!-- 欢迎标题 -->
    <div class="dashboard-header">
      <h1 class="dashboard-title">Apollo GCS 仪表板</h1>
      <p class="dashboard-subtitle">无人机实时监控数据</p>
    </div>

    <!-- 主要数据卡片 -->
    <div class="data-grid">
      <!-- 位置信息 -->
      <div class="data-card">
        <div class="card-header">
          <span class="card-icon">📍</span>
          <span class="card-title">位置信息</span>
        </div>
        <div class="card-content">
          <div class="data-row">
            <span class="data-label">纬度:</span>
            <span class="data-value">{{ latitudeFormat }}</span>
          </div>
          <div class="data-row">
            <span class="data-label">经度:</span>
            <span class="data-value">{{ longitudeFormat }}</span>
          </div>
          <div class="data-row">
            <span class="data-label">高度:</span>
            <span class="data-value highlight">{{ altitudeFormat }}</span>
          </div>
        </div>
      </div>

      <!-- 速度信息 -->
      <div class="data-card">
        <div class="card-header">
          <span class="card-icon">🚀</span>
          <span class="card-title">速度信息</span>
        </div>
        <div class="card-content">
          <div class="data-row">
            <span class="data-label">地速:</span>
            <span class="data-value highlight">{{ speedFormat }}</span>
          </div>
          <div class="data-row">
            <span class="data-label">VX:</span>
            <span class="data-value">{{ droneStore.velocity.x.toFixed(1) }} m/s</span>
          </div>
          <div class="data-row">
            <span class="data-label">VY:</span>
            <span class="data-value">{{ droneStore.velocity.y.toFixed(1) }} m/s</span>
          </div>
          <div class="data-row">
            <span class="data-label">VZ:</span>
            <span class="data-value">{{ droneStore.velocity.z.toFixed(1) }} m/s</span>
          </div>
        </div>
      </div>

      <!-- 姿态信息 -->
      <div class="data-card">
        <div class="card-header">
          <span class="card-icon">🔄</span>
          <span class="card-title">姿态信息</span>
        </div>
        <div class="card-content">
          <div class="data-row">
            <span class="data-label">横滚:</span>
            <span class="data-value">{{ droneStore.attitude.roll.toFixed(2) }}°</span>
          </div>
          <div class="data-row">
            <span class="data-label">俯仰:</span>
            <span class="data-value">{{ droneStore.attitude.pitch.toFixed(2) }}°</span>
          </div>
          <div class="data-row">
            <span class="data-label">偏航:</span>
            <span class="data-value highlight">{{ droneStore.attitude.yaw.toFixed(2) }}°</span>
          </div>
          <div class="data-row">
            <span class="data-label">角速度 X:</span>
            <span class="data-value">{{ droneStore.angularVelocity.p.toFixed(2) }} rad/s</span>
          </div>
        </div>
      </div>

      <!-- 系统状态 -->
      <div class="data-card">
        <div class="card-header">
          <span class="card-icon">⚡</span>
          <span class="card-title">系统状态</span>
        </div>
        <div class="card-content">
          <div class="status-item">
            <span class="status-label">连接状态:</span>
            <span class="status-value" :class="connectionClass">{{ droneStore.isConnectedText }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">避障系统:</span>
            <span class="status-value" :class="avoidanceClass">
              {{ avoidanceText }}
            </span>
          </div>
          <div class="status-item">
            <span class="status-label">操作模式:</span>
            <span class="status-value">{{ droneStore.currentModeText }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 实时状态指示器 -->
    <div class="status-indicators">
      <div class="indicator" :class="{ active: droneStore.isConnected }">
        <div class="indicator-dot"></div>
        <span>通信连接</span>
      </div>
      <div class="indicator" :class="{ active: droneStore.isConnected }">
        <div class="indicator-dot"></div>
        <span>数据接收</span>
      </div>
      <div class="indicator" :class="{ active: droneStore.avoidFlag.laserRadarEnabled }">
        <div class="indicator-dot"></div>
        <span>激光雷达</span>
      </div>
      <div class="indicator" :class="{ active: droneStore.avoidFlag.avoidanceFlag }">
        <div class="indicator-dot"></div>
        <span>避障激活</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

const latitudeFormat = computed(() => {
  if (droneStore.position.lat === 0) return 'N/A'
  console.log('[Dashboard] latitude:', droneStore.position.lat)
  return droneStore.position.lat.toFixed(6) + '°'
})

const longitudeFormat = computed(() => {
  if (droneStore.position.lon === 0) return 'N/A'
  console.log('[Dashboard] longitude:', droneStore.position.lon)
  return droneStore.position.lon.toFixed(6) + '°'
})

const altitudeFormat = computed(() => {
  console.log('[Dashboard] altitude:', droneStore.position.alt)
  return droneStore.position.alt.toFixed(1) + ' m'
})

const speedFormat = computed(() => {
  const speed = Math.sqrt(droneStore.velocity.x ** 2 + droneStore.velocity.y ** 2)
  return speed.toFixed(1) + ' m/s'
})

const connectionClass = computed(() => ({
  'status-active': droneStore.isConnected,
  'status-inactive': !droneStore.isConnected
}))

const avoidanceClass = computed(() => ({
  'status-active': droneStore.avoidFlag.laserRadarEnabled,
  'status-inactive': !droneStore.avoidFlag.laserRadarEnabled
}))

const avoidanceText = computed(() => {
  if (droneStore.avoidFlag.laserRadarEnabled) {
    return droneStore.avoidFlag.avoidanceFlag ? '已激活' : '已启用'
  }
  return '未启用'
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  gap: 24px;
}

.dashboard-header {
  text-align: center;
  margin-bottom: 16px;
}

.dashboard-title {
  font-size: 28px;
  font-weight: 600;
  color: #FFFFFF;
  margin: 0 0 8px 0;
}

.dashboard-subtitle {
  font-size: 14px;
  color: #999999;
  margin: 0;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.data-card {
  background-color: #1F1F1F;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s ease;
}

.data-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background-color: #2A2A2A;
  border-bottom: 1px solid #3A3A3A;
}

.card-icon {
  font-size: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #FFFFFF;
}

.card-content {
  padding: 20px;
}

.data-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #2A2A2A;
}

.data-row:last-child {
  border-bottom: none;
}

.data-label {
  font-size: 14px;
  color: #999999;
}

.data-value {
  font-size: 16px;
  font-weight: 500;
  color: #FFFFFF;
}

.data-value.highlight {
  color: #00BCD4;
  font-weight: 600;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #2A2A2A;
}

.status-item:last-child {
  border-bottom: none;
}

.status-label {
  font-size: 14px;
  color: #999999;
}

.status-value {
  font-size: 14px;
  font-weight: 500;
  padding: 4px 12px;
  border-radius: 4px;
  background-color: #0D0D0D;
}

.status-value.status-active {
  color: #00C853;
}

.status-value.status-inactive {
  color: #999999;
}

.status-indicators {
  display: flex;
  gap: 24px;
  justify-content: center;
  padding: 20px;
  background-color: #1F1F1F;
  border-radius: 8px;
}

.indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 6px;
  background-color: #2A2A2A;
  color: #999999;
  font-size: 14px;
  transition: all 0.3s ease;
}

.indicator.active {
  background-color: #3A3A3A;
  color: #00C853;
}

.indicator-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #666666;
  transition: all 0.3s ease;
}

.indicator.active .indicator-dot {
  background-color: #00C853;
  box-shadow: 0 0 8px rgba(0, 200, 83, 0.5);
}
</style>