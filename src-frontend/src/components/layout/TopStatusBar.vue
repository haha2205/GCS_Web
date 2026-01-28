<template>
  <div class="top-status-bar">
    <!-- Logo -->
    <div class="status-section logo-section">
      <div class="logo-text">Apollo-GCS</div>
    </div>
   
    <!-- 链路状态 -->
    <div class="status-section link-section">
      <div class="status-item">
        <span class="status-label">UDP:</span>
        <span :class="udpClass">{{ udpStatusText }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">WS:</span>
        <span :class="wsClass">{{ wsStatusText }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">延迟:</span>
        <span class="status-text">{{ latency }}ms</span>
      </div>
    </div>
    
    <!-- 系统模式 -->
    <div class="status-section mode-section">
      <div class="status-item mode-item">
        <span class="status-label">模式:</span>
        <span :class="systemModeClass">{{ systemModeText }}</span>
      </div>
    </div>
    
    <!-- 当前时间 -->
    <div class="status-section time-section">
      <div class="time-text">{{ currentTime }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

// 当前时间显示
const currentTime = ref('')
const latency = ref(0)

// 更新时间
const updateTime = () => {
  const now = new Date()
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  const seconds = String(now.getSeconds()).padStart(2, '0')
  currentTime.value = `${hours}:${minutes}:${seconds}`
}

let timeInterval = null
let lastPacketTime = null

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  
  // 监听数据包接收，计算延迟
  watch(() => [droneStore.position.lat, droneStore.position.lon], ([newLat, newLon]) => {
    if (newLat !== 0 || newLon !== 0) {
      lastPacketTime = Date.now()
    }
  }, { immediate: true })
  
  // 每秒检查链路延迟
  const latencyCheck = setInterval(() => {
    if (lastPacketTime && droneStore.isConnected) {
      latency.value = Date.now() - lastPacketTime
    } else {
      latency.value = 0
    }
  }, 1000)
  
  onUnmounted(() => {
    clearInterval(latencyCheck)
  })
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})

// UDP连接状态
const udpClass = computed(() => {
  if (droneStore.systemStatus.linkQuality > 80) return 'good'
  if (droneStore.systemStatus.linkQuality > 50) return 'medium'
  return 'poor'
})

const udpStatusText = computed(() => {
  if (!droneStore.isConnected) return '未连接'
  if (latency.value < 100) return '已连接'
  return '超时'
})

// WebSocket连接状态
const wsClass = computed(() => ({
  connected: droneStore.isConnected,
  disconnected: !droneStore.isConnected
}))

const wsStatusText = computed(() => {
  return droneStore.isConnected ? '已连接' : '未连接'
})

// 系统模式
const systemMode = computed(() => {
  return droneStore.systemMode || 'REALTIME'
})

const systemModeText = computed(() => {
  return systemMode.value === 'REALTIME' ? '实时' : '回放'
})

const systemModeClass = computed(() => {
  return {
    'mode-realtime': systemMode.value === 'REALTIME',
    'mode-replay': systemMode.value === 'REPLAY'
  }
})
</script>

<style scoped>
.top-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 24px;
  background-color: #1F1F1F;
  border-bottom: 1px solid #2A2A2A;
  color: #FFFFFF;
}

.status-section {
  display: flex;
  align-items: center;
  gap: 24px;
}

.logo-section .logo-text {
  font-size: 20px;
  font-weight: 700;
  color: #00BCD4;
  letter-spacing: 1.5px;
  background: linear-gradient(135deg, #00BCD4, #2196F3);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.link-section {
  display: flex;
  gap: 24px;
  align-items: center;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.status-label {
  color: #999999;
  font-weight: 400;
}

.status-text {
  color: #FFFFFF;
  font-weight: 500;
  font-family: 'Consolas', 'Monaco', monospace;
}

/* 链路状态样式 */
.link-section .status-item .good {
  color: #00C853;
  font-weight: 500;
}

.link-section .status-item .medium {
  color: #FFC107;
  font-weight: 500;
}

.link-section .status-item .poor {
  color: #FF5252;
  font-weight: 500;
}

.ws-status.connected {
  color: #00C853;
}

.ws-status.disconnected {
  color: #FF5252;
}

/* 系统模式样式 */
.mode-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mode-item .mode-realtime {
  color: #00C853;
  font-weight: 600;
}

.mode-item .mode-replay {
  color: #FFC107;
  font-weight: 600;
  animation: pulse-replay 2s ease-in-out infinite;
}

@keyframes pulse-replay {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.time-section {
  display: flex;
  align-items: center;
}

.time-text {
  font-size: 14px;
  color: #999999;
  font-weight: 400;
  font-family: 'Consolas', 'Monaco', monospace;
  letter-spacing: 0.5px;
}
</style>