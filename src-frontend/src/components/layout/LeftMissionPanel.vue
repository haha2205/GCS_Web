<template>
  <div class="mission-panel">
    <h3 class="panel-title">规划指令</h3>
    
    <div class="content-scroll">
      <div class="mission-content">
      <!-- 目标位置设置 -->
      <div class="mission-section">
        <h4 class="section-title">目标位置 (ENU坐标系)</h4>
        <div class="target-inputs">
          <div class="input-group">
            <label class="input-label">X (东向 m)</label>
            <input
              v-model.number="targetPos.x"
              type="number"
              class="coord-input"
              step="1"
              placeholder="0"
            />
          </div>
          <div class="input-group">
            <label class="input-label">Y (北向 m)</label>
            <input
              v-model.number="targetPos.y"
              type="number"
              class="coord-input"
              step="1"
              placeholder="0"
            />
          </div>
          <div class="input-group">
            <label class="input-label">Z (高度 m)</label>
            <input
              v-model.number="targetPos.z"
              type="number"
              class="coord-input"
              step="1"
              placeholder="100"
              :min="0"
            />
          </div>
        </div>
      </div>
      
      <!-- 速度设置 -->
      <div class="mission-section">
        <h4 class="section-title">速度设置</h4>
        <div class="input-group">
          <label class="input-label">巡航速度 (m/s)</label>
          <input
            v-model.number="cruiseSpeed"
            type="number"
            class="speed-input"
            step="0.5"
            placeholder="10.0"
            :min="0"
            :max="30"
          />
        </div>
      </div>
      
      <!-- 飞控指令关联 -->
      <div class="mission-section">
        <h4 class="section-title">飞控指令</h4>
        <div class="cmd-idx-info">
          <span class="info-label">当前指令:</span>
          <span class="info-value">{{ currentCmdIdxInfo }}</span>
        </div>
        <div class="info-hint">
          💡 请从"飞控指令"面板点击指令按钮，系统会自动关联
        </div>
      </div>
      
      <!-- 任务使能 -->
      <div class="mission-section">
        <div class="enable-control">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="enableMission"
              class="checkbox-input"
            />
            <span>使能任务执行</span>
          </label>
        </div>
      </div>
      
      <!-- 发送按钮 -->
      <div class="mission-actions">
        <button
          class="action-btn send-planning"
          @click="sendPlanningCommand"
          :disabled="!connected"
        >
          <span>🚀</span> 发送规划指令
        </button>
        <button
          class="action-btn clear"
          @click="resetInputs"
        >
          <span>🔄</span> 重置
        </button>
      </div>
      
      <!-- 当前航点信息 -->
      <div class="mission-section" v-if="currentWaypointIndex >= 0">
        <h4 class="section-title">当前航点</h4>
        <div class="current-wp-info">
          <div class="wp-number">航点 {{ currentWaypointIndex + 1 }} / {{ waypoints.length }}</div>
          <div class="wp-coords-display">
            <span class="coord-item">{{ waypoints[currentWaypointIndex]?.lat.toFixed(6) || '-' }}</span>
            <span class="coord-item">{{ waypoints[currentWaypointIndex]?.lon.toFixed(6) || '-' }}</span>
            <span class="coord-item">{{ waypoints[currentWaypointIndex]?.alt.toFixed(1) || '-' }} m</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: missionProgress + '%' }"></div>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()
const connected = computed(() => droneStore.connected)

// 目标位置（ENU坐标系）
const targetPos = ref({
  x: 100,
  y: 100,
  z: 10
})

// 巡航速度
const cruiseSpeed = ref(5.0)

// 任务使能标志
const enableMission = ref(false)

const normalizeCmdIdx = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : 0
}

const selectedCmdIdx = computed(() => normalizeCmdIdx(droneStore.selectedCmdIdx))
const telemetryCmdIdx = computed(() => normalizeCmdIdx(droneStore.lastTelemetryCmdIdx || droneStore.gcsData?.Tele_GCS_CmdIdx))
const planningCmdIdx = computed(() => normalizeCmdIdx(droneStore.latchedPlanningCmdIdx || droneStore.selectedCmdIdx || droneStore.lastTelemetryCmdIdx || droneStore.gcsData?.Tele_GCS_CmdIdx))

// 当前指令信息显示
const currentCmdIdxInfo = computed(() => {
  if (planningCmdIdx.value === 0) return '无指令'
  
  // 指令名称映射
  const cmdMap = {
    1: '外交控制',
    2: '混合控制',
    3: '程序控制',
    4: '爬升',
    5: '定高/平飞',
    6: '下滑',
    7: '断开定高',
    8: '定向/直飞',
    9: '左盘旋',
    10: '右盘旋',
    11: '航向保持',
    12: '开车准备',
    13: '停车',
    14: '自动起飞',
    15: '自动着陆',
    16: '悬停',
    17: '一键返航',
    18: '预控',
    19: '地速飞行',
    20: '空速飞行',
    21: '起飞准备',
    22: '人工起飞',
    23: '人工着陆',
    24: '避障开',
    25: '避障关'
  }
  
  const planningLabel = `规划发送 ID:${planningCmdIdx.value} ${cmdMap[planningCmdIdx.value] || '未知'}`
  const telemetryLabel = telemetryCmdIdx.value === 0
    ? '飞控回传: 无'
    : `飞控回传 ID:${telemetryCmdIdx.value} ${cmdMap[telemetryCmdIdx.value] || '未知'}`
  const selectedLabel = selectedCmdIdx.value === 0
    ? '前端选择: 无'
    : `前端选择 ID:${selectedCmdIdx.value} ${cmdMap[selectedCmdIdx.value] || '未知'}`
  return `${planningLabel} | ${selectedLabel} | ${telemetryLabel}`
})

// 序号计数器
const seqIdCounter = ref(0)

// 发送规划指令到规划模块
const sendPlanningCommand = async () => {
  if (!connected.value) {
    droneStore.addLog('未连接到后端，无法发送规划指令', 'warning')
    return
  }
  
  try {
    // 递增序号
    seqIdCounter.value = (seqIdCounter.value + 1) % 1000000
    const seqId = seqIdCounter.value
    
    const planningData = {
      seqId: seqId,
      targetX: targetPos.value.x,
      targetY: targetPos.value.y,
      targetZ: targetPos.value.z,
      cruiseSpeed: cruiseSpeed.value,
      enable: enableMission.value ? 1 : 0,
      cmdId: planningCmdIdx.value
    }

    const response = await droneStore.sendCommandREST('gcs_command', planningData)
    
    if (response && response.status === 'success') {
      droneStore.addLog(
        `发送规划指令到规划模块: 目标(${targetPos.value.x}, ${targetPos.value.y}, ${targetPos.value.z}), 速度=${cruiseSpeed.value}m/s, CmdIdx=${planningCmdIdx.value}`,
        'info'
      )
      console.log('规划指令发送成功:', planningData)
    } else {
      throw new Error(response?.message || '发送失败')
    }
  } catch (error) {
    console.error('发送规划指令失败:', error)
    droneStore.addLog(`发送规划指令失败: ${error.message || error}`, 'error')
  }
}

// 重置输入
const resetInputs = () => {
  targetPos.value = { x: 100, y: 100, z: 10 }
  cruiseSpeed.value = 5.0
  enableMission.value = false
  droneStore.addLog('规划指令已重置', 'info')
}

// 保留旧的航点相关变量以避免错误
const waypoints = ref([])
const currentWaypointIndex = ref(-1)
const missionProgress = ref(0)

const addWaypoint = () => {
  if (waypoints.value.length > 0) {
    const lastWp = waypoints.value[waypoints.value.length - 1]
    waypoints.value.push({
      lat: lastWp.lat,
      lon: lastWp.lon + 0.001,
      alt: lastWp.alt
    })
  } else {
    waypoints.value.push({ lat: 39.123456, lon: 117.123456, alt: 50 })
  }
}

const addSampleWaypoint = () => {
  waypoints.value = [
    { lat: 39.123456, lon: 117.123456, alt: 50 },
    { lat: 39.124456, lon: 117.124456, alt: 60 },
    { lat: 39.125456, lon: 117.125456, alt: 70 },
    { lat: 39.126456, lon: 117.126456, alt: 80 },
    { lat: 39.126456, lon: 117.127456, alt: 80 }
  ]
  calculateMission()
}

const removeWaypoint = (index) => {
  waypoints.value.splice(index, 1)
  if (currentWaypointIndex.value >= waypoints.value.length) {
    currentWaypointIndex.value = waypoints.value.length - 1
  }
}

const moveWaypoint = (index, direction) => {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= waypoints.value.length) return
  const temp = waypoints.value[index]
  waypoints.value[index] = waypoints.value[newIndex]
  waypoints.value[newIndex] = temp
  calculateMission()
}

const editWaypoint = (index) => {
  const wp = waypoints.value[index]
  const newLat = prompt('输入纬度:', wp.lat)
  if (newLat !== null) wp.lat = parseFloat(newLat) || 0
  
  const newLon = prompt('输入经度:', wp.lon)
  if (newLon !== null) wp.lon = parseFloat(newLon) || 0
  
  const newAlt = prompt('输入高度:', wp.alt)
  if (newAlt !== null) wp.alt = parseFloat(newAlt) || 50
  
  calculateMission()
}

const clearWaypoints = () => {
  if (waypoints.value.length < 2) {
    return
  }
  
  let totalDist = 0
  for (let i = 1; i < waypoints.value.length; i++) {
    const wp1 = waypoints.value[i - 1]
    const wp2 = waypoints.value[i]
    const dist = calculateDistance(wp1.lat, wp1.lon, wp2.lat, wp2.lon)
    totalDist += dist
  }
  
  droneStore.addLog(`计算航程完成: ${totalDist.toFixed(2)} m, ${waypoints.value.length} 个航点`, 'info')
}

const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = 6371000
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

const totalDistance = computed(() => {
  if (waypoints.value.length < 2) return 0
  let dist = 0
  for (let i = 1; i < waypoints.value.length; i++) {
    dist += calculateDistance(
      waypoints.value[i - 1].lat,
      waypoints.value[i - 1].lon,
      waypoints.value[i].lat,
      waypoints.value[i].lon
    )
  }
  return dist
})

const uploadMission = () => {
  if (waypoints.value.length === 0) {
    droneStore.addLog('无法上传空的任务', 'error')
    return
  }
  
  const missionData = {
    waypoints: waypoints.value,
    totalDistance: totalDistance.value
  }
  
  droneStore.sendCommand('upload_mission', missionData)
  droneStore.addLog(`任务已上传: ${waypoints.value.length} 个航点`, 'info')
}

const downloadMission = () => {
  if (waypoints.value.length === 0) {
    droneStore.addLog('没有可导出的任务数据', 'error')
    return
  }
  
  const data = JSON.stringify({
    version: '1.0',
    timestamp: new Date().toISOString(),
    waypoints: waypoints.value,
    totalDistance: totalDistance.value
  }, null, 2)
  
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `mission_${new Date().getTime()}.json`
  a.click()
  URL.revokeObjectURL(url)
  
  droneStore.addLog('任务已导出到本地', 'info')
}

</script>

<style scoped>
.mission-panel {
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

.mission-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--accent-color);
}

.mission-section {
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  color: var(--accent-color);
  font-size: 13px;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-icon {
  font-size: 14px;
}

/* 目标位置输入区域 */
.target-inputs {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-label {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.coord-input {
  background: var(--surface-elevated);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  transition: all 0.2s;
}

.coord-input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
}

.speed-input {
  background: var(--surface-elevated);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 8px 12px;
  font-size: 13px;
  transition: all 0.2s;
}

.speed-input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
}

/* 指令信息显示 */
.cmd-idx-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: var(--panel-muted);
  border-radius: 4px;
  border-left: 3px solid var(--accent-color);
}

.info-label {
  color: var(--text-tertiary);
  font-size: 12px;
}

.info-value {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
  font-family: 'Consolas', 'Monaco', monospace;
}

.info-hint {
  color: var(--accent-color);
  font-size: 11px;
  padding: 8px;
  background: rgba(37, 99, 235, 0.08);
  border-radius: 4px;
  margin-top: 8px;
}

/* 使能控制 */
.enable-control {
  display: flex;
  align-items: center;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.checkbox-input {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--accent-color);
}

/* 发送按钮样式 */
.action-btn.send-planning {
  background: linear-gradient(135deg, #9c27b0, #7b1fa2);
  flex: 2;
}

.action-btn.send-planning:hover:not(:disabled) {
  background: linear-gradient(135deg, #7b1fa2, #6a1b9a);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(156, 39, 176, 0.3);
}

.waypoint-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: rgba(30, 30, 30, 0.5);
  border-radius: 6px;
  margin-bottom: 8px;
  border-left: 3px solid #4caf50;
  transition: all 0.2s;
}

.waypoint-item:hover {
  background: rgba(40, 60, 30, 0.5);
}

.wp-index {
  background: #4caf50;
  color: #ffffff;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.wp-coords {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  flex-wrap: wrap;
}

.wp-label {
  color: #4caf50;
  font-size: 10px;
  font-weight: 600;
}

.wp-input {
  background: rgba(20, 20, 20, 0.8);
  border: 1px solid #444444;
  border-radius: 4px;
  color: #ffffff;
  padding: 4px 6px;
  font-size: 10px;
  width: 65px;
}

.wp-input:focus {
  outline: none;
  border-color: #4caf50;
}

.wp-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.waypoint-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  gap: 12px;
  color: #666;
}

.empty-icon {
  font-size: 40px;
  opacity: 0.5;
}

.empty-text {
  font-size: 12px;
}

.add-sample-btn {
  background: rgba(76, 175, 80, 0.2);
  border: 1px dashed #4caf50;
  border-radius: 6px;
  color: #4caf50;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s;
}

.add-sample-btn:hover {
  background: rgba(76, 175, 80, 0.3);
}

.icon-btn {
  background: rgba(50, 136, 250, 0.2);
  border: 1px solid rgba(50, 136, 250, 0.5);
  border-radius: 4px;
  color: #3288fa;
  width: 24px;
  height: 24px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.icon-btn:hover:not(:disabled) {
  background: rgba(50, 136, 250, 0.3);
  transform: scale(1.1);
}

.icon-btn.edit {
  border-color: #ff9800;
  color: #ff9800;
  background: rgba(255, 152, 0, 0.2);
}

.icon-btn.edit:hover {
  background: rgba(255, 152, 0, 0.3);
}

.icon-btn.delete {
  border-color: #d32f2f;
  color: #d32f2f;
  background: rgba(211, 47, 47, 0.2);
}

.icon-btn.delete:hover:not(:disabled) {
  background: rgba(211, 47, 47, 0.3);
}

.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  transform: none !important;
}

.mission-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 10px;
  margin-top: 10px;
  border-top: 1px solid var(--border-color);
}

.mission-actions.secondary {
  border-top: none;
  padding-top: 0;
  margin-top: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  color: #ffffff;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-2px);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none !important;
}

.action-btn.add {
  background: #4caf50;
  flex: 1;
}

.action-btn.add:hover:not(:disabled) {
  background: #3e8e41;
}

.action-btn.calculate {
  background: rgba(50, 136, 250, 0.2);
  border: 1px solid #3288fa;
  color: #3288fa;
  flex: 1;
}

.action-btn.calculate:hover:not(:disabled) {
  background: rgba(50, 136, 250, 0.3);
}

.action-btn.clear {
  background: rgba(158, 158, 158, 0.2);
  border: 1px solid #9e9e9e;
  color: #9e9e9e;
}

.action-btn.clear:hover:not(:disabled) {
  background: rgba(158, 158, 158, 0.3);
}

.action-btn.upload {
  background: rgba(156, 39, 176, 0.2);
  border: 1px solid #9c27b0;
  color: #9c27b0;
  flex: 1;
}

.action-btn.upload:hover:not(:disabled) {
  background: rgba(156, 39, 176, 0.3);
}

.action-btn.download {
  background: rgba(255, 152, 0, 0.2);
  border: 1px solid #ff9800;
  color: #ff9800;
  flex: 1;
}

.action-btn.download:hover:not(:disabled) {
  background: rgba(255, 152, 0, 0.3);
}

.mission-summary {
  color: #cccccc;
  font-size: 11px;
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.summary-label {
  color: #999;
}

.summary-value {
  color: #4caf50;
  font-weight: 700;
}

.summary-divider {
  color: #666;
}

.waypoints-count {
  color: #999;
  font-style: italic;
}

.current-wp-info {
  background: rgba(30, 30, 30, 0.5);
  border-radius: 6px;
  padding: 12px;
}

.wp-number {
  color: #4caf50;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 8px;
}

.wp-coords-display {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.coord-item {
  color: #ffffff;
  font-size: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
}

.progress-bar {
  height: 6px;
  background: rgba(60, 60, 60, 0.8);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  transition: width 0.5s ease;
  border-radius: 3px;
}

.refresh {
  background: var(--surface-elevated);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-secondary);
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.refresh:hover {
  background: rgba(37, 99, 235, 0.12);
  color: var(--accent-color);
  transform: rotate(180deg);
}
</style>