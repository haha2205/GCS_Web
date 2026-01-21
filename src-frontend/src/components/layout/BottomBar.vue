<template>
  <div class="bottom-bar">
    <!-- 左侧：操作按钮 -->
    <div class="command-section">
      <button 
        v-for="cmd in commands" 
        :key="cmd.id"
        :class="['command-btn', cmd.type]"
        @click="sendCommand(cmd.id)"
        :disabled="!isConnected"
      >
        <span class="cmd-icon">{{ cmd.icon }}</span>
        <span class="cmd-label">{{ cmd.label }}</span>
      </button>
    </div>
    
    <!-- 中间：任务进度 -->
    <div class="progress-section">
      <div class="mission-info">
        <span class="mission-status">{{ missionStatus }}</span>
        <span class="mission-progress">{{ missionProgress }}%</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: missionProgress + '%' }"></div>
      </div>
    </div>
    
    <!-- 右侧：最新日志 -->
    <div class="log-section">
      <div class="latest-log" :class="`log-${latestLog.level}`">
        <span class="log-time">{{ latestLog.time }}</span>
        <span class="log-message">{{ latestLog.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

const commands = [
  { id: 'takeoff', icon: '🚀', label: '起飞', type: 'primary' },
  { id: 'hover', icon: '⏸️', label: '悬停', type: 'normal' },
  { id: 'land', icon: '🛬', label: '降落', type: 'normal' },
  { id: 'rtl', icon: '🏠', label: '返航', type: 'danger' }
]

const missionStatus = computed(() => {
  return droneStore.missionStatus || '待命'
})

const missionProgress = computed(() => {
  return droneStore.missionProgress || 0
})

const latestLog = computed(() => {
  const logs = droneStore.logs || []
  return logs[logs.length - 1] || { time: '--:--', message: '暂无日志', level: 'info' }
})

const isConnected = computed(() => {
  return droneStore.connected
})

function sendCommand(cmdId) {
  console.log('发送指令:', cmdId)
  // TODO: 通过 WebSocket 发送指令
  droneStore.sendCommand(cmdId)
}
</script>

<style scoped>
/* ==================== 底部栏容器 ==================== */
.bottom-bar {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  gap: 30px;
}

/* ==================== 操作按钮区 ==================== */
.command-section {
  display: flex;
  gap: 10px;
}

.command-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px solid #333333;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  background: rgba(40, 40, 40, 0.5);
  color: #ffffff;
}

.command-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.command-btn:active:not(:disabled) {
  transform: translateY(0);
}

.command-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.command-btn.primary {
  background: linear-gradient(135deg, #3288fa, #2676ea);
  border-color: #3288fa;
}

.command-btn.primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #4695fb, #3288fa);
}

.command-btn.danger {
  background: linear-gradient(135deg, #ff5722, #f44336);
  border-color: #ff5722;
}

.command-btn.danger:hover:not(:disabled) {
  background: linear-gradient(135deg, #ff7043, #ff5722);
}

.cmd-icon {
  font-size: 16px;
}

.cmd-label {
  font-size: 13px;
}

/* ==================== 任务进度区 ==================== */
.progress-section {
  flex: 1;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mission-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.mission-status {
  color: #cccccc;
}

.mission-progress {
  color: #3288fa;
  font-weight: 600;
}

.progress-bar {
  height: 8px;
  background: rgba(30, 30, 30, 0.8);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3288fa, #4695fb);
  border-radius: 4px;
  transition: width 0.3s ease;
  position: relative;
}

.progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* ==================== 日志区 ==================== */
.log-section {
  max-width: 500px;
  min-width: 300px;
  display: flex;
  align-items: center;
}

.latest-log {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: rgba(30, 30, 30, 0.8);
  border-radius: 6px;
  font-size: 12px;
  border-left: 3px solid #666666;
}

.log-time {
  color: #999999;
  font-family: 'Consolas', 'Monaco', monospace;
  min-width: 70px;
}

.log-message {
  color: #cccccc;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-info {
  border-left-color: #4caf50;
}

.log-info .log-message {
  color: #ffffff;
}

.log-warning {
  border-left-color: #ff9800;
}

.log-warning .log-message {
  color: #ffcc80;
}

.log-error {
  border-left-color: #f44336;
}

.log-error .log-message {
  color: #ff8a80;
}
</style>