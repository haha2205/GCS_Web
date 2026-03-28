<template>
  <div class="top-status-bar">
    <div class="status-section brand-section">
      <div class="logo-text">TJU-GCS</div>
      <div class="recording-strip">
        <select class="case-select" :value="selectedPlanCaseId" @change="changeExperimentCase($event.target.value)">
          <option value="">选择实验 Case</option>
          <option v-for="item in planCases" :key="item.case_id" :value="item.case_id">
            {{ item.case_id }} | {{ item.task_name }} | {{ item.scenario_name }}
          </option>
        </select>
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
          <span>{{ caseIdLabel }}</span>
          <span>{{ planCaseLabel }}</span>
          <span>{{ taskLabel }}</span>
          <span>{{ missionPhaseLabel }}</span>
          <span>{{ scenarioLabel }}</span>
          <span>{{ architectureLabel }}</span>
          <span>{{ elapsedLabel }}</span>
          <span>{{ currentSessionLabel }}</span>
          <span>{{ totalBytesLabel }}</span>
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

const updateTime = () => {
  const now = new Date()
  const hours = String(now.getHours()).padStart(2, '0')
  const minutes = String(now.getMinutes()).padStart(2, '0')
  const seconds = String(now.getSeconds()).padStart(2, '0')
  currentTime.value = `${hours}:${minutes}:${seconds}`
}

let timeInterval = null
let recordingPoll = null
let udpPoll = null

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  droneStore.fetchExperimentPlan()
  droneStore.fetchExperimentRuntime()
  droneStore.fetchRecordingStatus()
  droneStore.fetchUdpStatus()
  recordingPoll = setInterval(() => {
    droneStore.fetchRecordingStatus()
  }, 1500)
  udpPoll = setInterval(() => {
    droneStore.fetchUdpStatus()
  }, 1500)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
  if (recordingPoll) {
    clearInterval(recordingPoll)
  }
  if (udpPoll) {
    clearInterval(udpPoll)
  }
})

const udpClass = computed(() => {
  if (!droneStore.isUdpConnected) return 'poor'
  if (droneStore.systemStatus.linkQuality > 80) return 'good'
  if (droneStore.systemStatus.linkQuality > 50) return 'medium'
  return 'poor'
})

const udpStatusText = computed(() => (droneStore.isUdpConnected ? '已连接' : '未连接'))
const wsClass = computed(() => ({
  connected: droneStore.isConnected,
  disconnected: !droneStore.isConnected
}))
const wsStatusText = computed(() => (droneStore.isConnected ? '已连接' : '未连接'))
const recordingEnabled = computed(() => droneStore.dataRecording.enabled)
const currentSessionLabel = computed(() => droneStore.dataRecording.sessionId || '无会话')
const totalBytesLabel = computed(() => formatBytes(droneStore.dataRecording.totalBytes || 0))
const caseIdLabel = computed(() => droneStore.experimentContext.caseId || 'case001')
const planCaseLabel = computed(() => droneStore.experimentContext.planCaseId || 'UNPLANNED')
const missionPhaseLabel = computed(() => droneStore.experimentContext.missionPhase || 'idle')
const taskLabel = computed(() => droneStore.experimentContext.task.taskName || 'Idle')
const scenarioLabel = computed(() => droneStore.experimentContext.scenarioName || droneStore.experimentContext.scenarioId || 'scenario_default')
const architectureLabel = computed(() => droneStore.experimentContext.architecture.displayName || 'Baseline Balanced')
const planCases = computed(() => droneStore.experimentContext.availableCases || [])
const selectedPlanCaseId = computed(() => droneStore.experimentContext.selectedPlanCaseId || '')
const elapsedLabel = computed(() => {
  currentTime.value
  const startTime = droneStore.dataRecording.recordingStartTime
  if (!startTime) {
    return '00:00:00'
  }
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

const changeExperimentCase = async (caseId) => {
  if (!caseId || caseId === droneStore.experimentContext.selectedPlanCaseId) {
    return
  }
  await droneStore.selectExperimentCase(caseId)
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
  border-bottom: 0;
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

.case-select {
  min-width: 210px;
  max-width: 320px;
  height: 30px;
  padding: 0 8px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-primary);
  font-size: 11px;
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
  border-radius: 8px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
}

.record-btn.start {
  background: rgba(22, 163, 74, 0.1);
  color: #166534;
}

.record-btn.stop {
  background: rgba(220, 38, 38, 0.08);
  color: #b91c1c;
}

.record-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.record-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 11px;
  white-space: nowrap;
}

.link-section {
  display: flex;
  gap: 24px;
  align-items: center;
  flex-shrink: 0;
}


.status-label {
  color: var(--text-tertiary);
  font-weight: 400;
}

.status-text {
  color: var(--text-primary);
  font-weight: 500;
  font-family: 'Consolas', 'Monaco', monospace;
}

/* 链路状态样式 */
.link-section .status-item .good {
  color: var(--success-color);
  font-weight: 500;
}

.link-section .status-item .medium {
  color: var(--warning-color);
  font-weight: 500;
}

.link-section .status-item .poor {
  color: var(--error-color);
  font-weight: 500;
}

.ws-status.connected {
  color: var(--success-color);
}

.ws-status.disconnected {
  color: var(--error-color);
}

/* 系统模式样式 */
.mode-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mode-item .mode-realtime {
  color: var(--success-color);
  font-weight: 600;
}

.mode-item .mode-standby {
  color: var(--warning-color);
  font-weight: 600;
}

.time-section {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.time-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 400;
  font-family: 'Consolas', 'Monaco', monospace;
  letter-spacing: 0.3px;
}

@media (max-width: 1400px) {
  .top-status-bar {
    padding: 0 10px;
    gap: 8px;
  }

  .recording-strip {
    gap: 6px;
  }
}
</style>