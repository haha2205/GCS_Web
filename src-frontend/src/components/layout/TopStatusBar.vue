<template>
  <div class="top-status-bar">
    <div class="status-section brand-section">
      <div class="logo-text">TJU-GCS</div>
      <div class="recording-strip">
        <div class="recording-pill" :class="{ active: recordingEnabled }">
          <span class="record-dot"></span>
          <span>{{ recordingEnabled ? '记录中' : '未记录' }}</span>
        </div>
        <button class="record-btn start" @click="startRecording" :disabled="recordingEnabled || recordingLoading">
          开始记录
        </button>
        <button class="record-btn stop" @click="stopRecording" :disabled="!recordingEnabled || recordingLoading">
          停止记录
        </button>
        <div class="record-meta">
          <span>{{ elapsedLabel }}</span>
          <span>{{ currentSessionLabel }}</span>
          <span>{{ totalBytesLabel }}</span>
          <span>{{ listenPortLabel }}</span>
          <span>{{ planningPortLabel }}</span>
        </div>
      </div>
    </div>

    <div class="status-section link-section">
      <div class="status-item">
        <span class="status-label">UDP:</span>
        <span :class="udpClass">{{ udpStatusText }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">WS:</span>
        <span :class="wsClass">{{ wsStatusText }}</span>
      </div>
    </div>

    <div class="status-section time-section">
      <div class="time-text">{{ currentTime }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()
const currentTime = ref('')
const recordingLoading = ref(false)

let timeInterval = null
let recordingPoll = null
let udpPoll = null

const updateTime = () => {
  const now = new Date()
  currentTime.value = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  void droneStore.fetchRecordingStatus()
  void droneStore.fetchUdpStatus()
  recordingPoll = setInterval(() => {
    void droneStore.fetchRecordingStatus()
  }, 1500)
  udpPoll = setInterval(() => {
    void droneStore.fetchUdpStatus()
  }, 1500)
})

onUnmounted(() => {
  if (timeInterval) clearInterval(timeInterval)
  if (recordingPoll) clearInterval(recordingPoll)
  if (udpPoll) clearInterval(udpPoll)
})

const udpClass = computed(() => {
  if (!droneStore.isUdpConnected) return 'poor'
  if (droneStore.systemStatus.linkQuality > 80) return 'good'
  if (droneStore.systemStatus.linkQuality > 50) return 'medium'
  return 'poor'
})

const udpStatusText = computed(() => (droneStore.isUdpConnected ? '已连接' : '未连接'))
const wsClass = computed(() => ({ connected: droneStore.isConnected, disconnected: !droneStore.isConnected }))
const wsStatusText = computed(() => (droneStore.isConnected ? '已连接' : '未连接'))
const recordingEnabled = computed(() => droneStore.dataRecording.enabled)
const currentSessionLabel = computed(() => droneStore.dataRecording.sessionId || '无会话')
const totalBytesLabel = computed(() => formatBytes(droneStore.dataRecording.totalBytes || 0))
const listenPortLabel = computed(() => `飞控主入口 ${droneStore.config.hostPort || 30509}`)
const planningPortLabel = computed(() => `规划口 ${droneStore.config.planningRecvPort || 18511}`)
const elapsedLabel = computed(() => {
  currentTime.value
  const startTime = droneStore.dataRecording.recordingStartTime
  if (!startTime) return '00:00:00'
  const endTime = droneStore.dataRecording.enabled ? Date.now() : (droneStore.dataRecording.lastRecordTime || Date.now())
  const totalSeconds = Math.max(0, Math.floor((endTime - startTime) / 1000))
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0')
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
})

const formatBytes = (value) => {
  const bytes = Number(value || 0)
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${bytes}B`
}

const startRecording = async () => {
  recordingLoading.value = true
  try {
    await droneStore.startFullRecording()
  } finally {
    recordingLoading.value = false
  }
}

const stopRecording = async () => {
  recordingLoading.value = true
  try {
    await droneStore.stopFullRecording()
  } finally {
    recordingLoading.value = false
  }
}
</script>

<style scoped>
.top-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 0 14px;
  background-color: transparent;
  color: var(--text-primary);
  gap: 12px;
}

.status-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-section {
  min-width: 0;
  flex: 1;
}

.logo-text {
  flex-shrink: 0;
  white-space: nowrap;
  line-height: 1;
  font-size: 13px;
  font-weight: 700;
  color: var(--accent-color);
  letter-spacing: 0.8px;
  background: linear-gradient(135deg, #0f172a, #2563eb);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.recording-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}

.recording-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  background: #eef2f8;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  font-size: 11px;
  white-space: nowrap;
}

.recording-pill.active {
  background: rgba(22, 163, 74, 0.1);
  border-color: rgba(22, 163, 74, 0.25);
  color: #166534;
}

.record-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}

.recording-pill.active .record-dot {
  background: #16a34a;
}

.record-btn {
  height: 30px;
  padding: 0 12px;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}

.record-btn.start {
  background: #0f766e;
  color: #fff;
}

.record-btn.stop {
  background: #b91c1c;
  color: #fff;
}

.record-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.record-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 11px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.status-label {
  color: var(--text-secondary);
}

.connected,
.good {
  color: #15803d;
}

.medium {
  color: #b45309;
}

.disconnected,
.poor {
  color: #b91c1c;
}

.time-text {
  font-family: 'Roboto Mono', monospace;
  font-size: 14px;
  color: var(--text-primary);
}
</style>