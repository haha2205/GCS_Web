<template>
  <div class="mission-panel">
    <h3 class="panel-title">任务规划</h3>
    
    <div class="content-scroll">
      <div class="mission-content">
      <!-- 航点管理 -->
      <div class="mission-section">
        <h4 class="section-title">航点管理</h4>
        <div class="waypoint-list">
          <div v-for="(wp, index) in waypoints" :key="index" class="waypoint-item">
            <span class="wp-index">{{ index + 1 }}</span>
            <div class="wp-coords">
              <span class="wp-label">Lat:</span>
              <input v-model="wp.lat" type="number" class="wp-input" step="0.000001" placeholder="39.123456" />
              <span class="wp-label">Lon:</span>
              <input v-model="wp.lon" type="number" class="wp-input" step="0.000001" placeholder="117.123456" />
              <span class="wp-label">Alt:</span>
              <input v-model="wp.alt" type="number" class="wp-input" placeholder="50" />
            </div>
            <div class="wp-actions">
              <button class="icon-btn" @click="moveWaypoint(index, -1)" :disabled="index === 0" title="上移">↑</button>
              <button class="icon-btn" @click="moveWaypoint(index, 1)" :disabled="index === waypoints.length - 1" title="下移">↓</button>
              <button class="icon-btn edit" @click="editWaypoint(index)" title="编辑">✎</button>
              <button class="icon-btn delete" @click="removeWaypoint(index)" title="删除">✕</button>
            </div>
          </div>
          
          <div v-if="waypoints.length === 0" class="waypoint-empty">
            <span class="empty-icon">📍</span>
            <span class="empty-text">暂无航点</span>
            <button class="add-sample-btn" @click="addSampleWaypoint">添加示例航点</button>
          </div>
        </div>
        
        <div class="mission-actions">
          <button class="action-btn add" @click="addWaypoint" :disabled="!connected">
            <span>+</span> 添加航点
          </button>
          <button class="action-btn calculate" @click="calculateMission" :disabled="!connected || waypoints.length < 2">
            <span>📐</span> 计算航程
          </button>
          <button class="action-btn clear" @click="clearWaypoints" :disabled="waypoints.length === 0">
            <span>🗑</span> 清空
          </button>
          <span class="mission-summary">
            <span class="summary-label">总计:</span>
            <span class="summary-value">{{ totalDistance.toFixed(2) }} m</span>
            <span class="summary-divider">|</span>
            <span class="waypoints-count">{{ waypoints.length }} 个航点</span>
          </span>
        </div>
        
        <div class="mission-actions secondary">
          <button class="action-btn upload" @click="uploadMission" :disabled="!connected || waypoints.length === 0">
            <span>↑</span> 上传任务
          </button>
          <button class="action-btn download" @click="downloadMission">
            <span>↓</span> 导出任务
          </button>
        </div>
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
import { ref, computed, nextTick } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()
const connected = computed(() => droneStore.connected)

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
  if (confirm('确定要清空所有航点吗？')) {
    waypoints.value = []
    currentWaypointIndex.value = -1
    missionProgress.value = 0
    droneStore.addLog('航点列表已清空', 'warning')
  }
}

const calculateMission = () => {
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
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #4caf50;
}

.mission-section {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  color: #4caf50;
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

.waypoint-list {
  max-height: 280px;
  overflow-y: auto;
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
  border-top: 1px solid rgba(255, 255, 255, 0.1);
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
  background: transparent;
  border: 1px solid #666;
  border-radius: 4px;
  color: #999;
  width: 28px;
  height: 28px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.refresh:hover {
  background: #666;
  color: #fff;
  transform: rotate(180deg);
}
</style>