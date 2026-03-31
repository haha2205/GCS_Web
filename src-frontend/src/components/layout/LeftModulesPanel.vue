<template>
  <div class="modules-panel">
    <h3 class="panel-title">模块管理器</h3>
    
    <div class="content-scroll">
      <div class="modules-content">
      <!-- 硬件模块 -->
      <div class="modules-section">
      <h4 class="section-title">硬件模块</h4>
      <div class="module-list">
        <div v-for="module in hardwareModules" :key="module.id" class="module-item">
          <div class="module-info">
            <div class="module-name">{{ module.name }}</div>
            <div class="module-status" :class="{ active: module.enabled }">
              {{ module.enabled ? '已启用' : '已禁用' }}
            </div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="module.enabled" @change="toggleModule(module)" />
            <span class="slider"></span>
          </label>
        </div>
      </div>
    </div>

    <!-- 算法模块 -->
    <div class="modules-section">
      <h4 class="section-title">算法模块</h4>
      <div class="module-list">
        <div v-for="module in algorithmModules" :key="module.id" class="module-item">
          <div class="module-info">
            <div class="module-name">{{ module.name }}</div>
            <div class="module-status" :class="{ active: module.enabled }">
              {{ module.enabled ? '已启用' : '已禁用' }}
            </div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" v-model="module.enabled" @change="toggleModule(module)" />
            <span class="slider"></span>
          </label>
        </div>
      </div>
    </div>

    <!-- 模块健康状态 -->
    <div class="modules-section">
      <h4 class="section-title">健康状态</h4>
      <div class="health-grid">
        <div v-for="item in healthStatus" :key="item.name" class="health-item">
          <span class="health-label">{{ item.name }}</span>
          <span class="health-value" :class="item.status">{{ item.status }}</span>
        </div>
      </div>
    </div>

    <!-- 模块延迟 -->
    <div class="modules-section">
      <h4 class="section-title">模块延迟 (ms)</h4>
      <div class="latency-list">
        <div v-for="item in latencyStatus" :key="item.name" class="latency-item">
          <span class="latency-label">{{ item.name }}</span>
          <div class="latency-bar-container">
            <div 
              class="latency-bar" 
              :style="{ width: `${(item.value / 100) * 100}%` }"
              :class="{ warning: item.value > 50, critical: item.value > 80 }"
            ></div>
            <span class="latency-value">{{ item.value }}ms</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="modules-actions">
      <button class="action-btn restart" @click="restartAllModules">
        <span class="icon">↻</span>
        重启所有模块
      </button>
      <button class="action-btn reset" @click="resetModules">
        <span class="icon">✕</span>
        重置配置
      </button>
      </div>
    </div>
  </div>
</div>
</template>

<script setup>
import { ref } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

// 硬件模块
const hardwareModules = ref([
  { id: 'rtk_gps', name: 'RTK GPS', enabled: true },
  { id: 'imu', name: 'IMU', enabled: true },
  { id: 'compass', name: 'Magnetometer', enabled: true },
  { id: 'baro', name: 'Barometer', enabled: true },
  { id: 'lidar', name: 'LiDAR', enabled: false },
  { id: 'camera', name: 'Optical Camera', enabled: false },
  { id: 'gimbal', name: 'Gimbal', enabled: false }
])

// 算法模块
const algorithmModules = ref([
  { id: 'optical_flow', name: 'Optical Flow', enabled: false },
  { id: 'visual_odometry', name: 'Visual Odometry', enabled: false },
  { id: 'slam', name: 'SLAM', enabled: false },
  { id: 'tracking', name: 'Visual Tracking', enabled: false },
  { id: 'obstacle_avoid', name: 'Obstacle Avoidance', enabled: false }
])

// 健康状态
const healthStatus = ref([
  { name: 'IMU', status: 'OK' },
  { name: 'GPS', status: 'OK' },
  { name: 'Compass', status: 'Warning' },
  { name: 'Baro', status: 'OK' },
  { name: 'LiDAR', status: 'Offline' },
  { name: 'Camera', status: 'Offline' }
])

// 模块延迟
const latencyStatus = ref([
  { name: 'IMU', value: 2 },
  { name: 'GPS', value: 45 },
  { name: 'Compass', value: 5 },
  { name: 'Baro', value: 3 },
  { name: 'LiDAR', value: 0 },
  { name: 'Camera', value: 0 }
])

const toggleModule = (module) => {
  console.log(`Toggle module: ${module.id}, enabled: ${module.enabled}`)
  // 发送指令到飞控
}

const restartAllModules = () => {
  console.log('Restart all modules')
}

const resetModules = () => {
  console.log('Reset modules configuration')
}
</script>

<style scoped>
.modules-panel {
  padding: 15px;
  max-height: 100vh;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  max-height: 100vh;
  min-height: 0;
}

.modules-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #3288fa;
}

.modules-section {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.section-title {
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #333333;
}

.module-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.module-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background: rgba(30, 30, 30, 0.5);
  border-radius: 6px;
}

.module-info {
  flex: 1;
}

.module-name {
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
}

.module-status {
  color: #999999;
  font-size: 11px;
}

.module-status.active {
  color: #4caf50;
}

/* Toggle Switch */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #555555;
  transition: .3s;
  border-radius: 24px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

.toggle-switch input:checked + .slider {
  background-color: #3288fa;
}

.toggle-switch input:checked + .slider:before {
  transform: translateX(20px);
}

/* 健康状态网格 */
.health-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.health-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background: rgba(30, 30, 30, 0.5);
  border-radius: 4px;
}

.health-label {
  color: #cccccc;
  font-size: 12px;
}

.health-value {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 3px;
}

.health-value.OK {
  color: #4caf50;
  background: rgba(76, 175, 80, 0.2);
}

.health-value.Warning {
  color: #ff9800;
  background: rgba(255, 152, 0, 0.2);
}

.health-value.Error {
  color: #d32f2f;
  background: rgba(211, 47, 47, 0.2);
}

.health-value.Offline {
  color: #757575;
  background: rgba(117, 117, 117, 0.2);
}

/* 延迟列表 */
.latency-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.latency-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.latency-label {
  color: #cccccc;
  font-size: 12px;
}

.latency-bar-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.latency-bar {
  height: 6px;
  background: #4caf50;
  border-radius: 3px;
  transition: width 0.3s, background-color 0.3s;
  min-width: 20px;
}

.latency-bar.warning {
  background: #ff9800;
}

.latency-bar.critical {
  background: #d32f2f;
}

.latency-value {
  min-width: 40px;
  color: #ffffff;
  font-size: 11px;
  text-align: right;
}

/* 操作按钮 */
.modules-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(50, 136, 250, 0.2);
  border: 1px solid rgba(50, 136, 250, 0.5);
  border-radius: 6px;
  color: #3288fa;
  padding: 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(50, 136, 250, 0.3);
}

.action-btn.restart {
  border-color: #ff9800;
  color: #ff9800;
  background: rgba(255, 152, 0, 0.2);
}

.action-btn.restart:hover {
  background: rgba(255, 152, 0, 0.3);
}

.action-btn.reset {
  border-color: #757575;
  color: #757575;
  background: rgba(117, 117, 117, 0.2);
}

.action-btn.reset:hover {
  background: rgba(117, 117, 117, 0.3);
}

.icon {
  font-size: 14px;
}
</style>