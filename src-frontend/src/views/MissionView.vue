<template>
  <div class="mission-view">
    <div class="mission-header">
      <h2>任务规划</h2>
      <div class="mission-actions">
        <button class="btn primary">新建任务</button>
        <button class="btn secondary">导入任务</button>
        <button class="btn secondary">导出任务</button>
      </div>
    </div>
    
    <div class="mission-content">
      <!-- 航点列表 -->
      <div class="waypoints-container">
        <div class="waypoints-header">
          <h3>航点列表</h3>
          <div class="waypoints-stats">
            <span>共 {{ waypoints.length }} 个航点</span>
            <span>总距离: {{ totalDistance }} km</span>
          </div>
        </div>
        
        <div class="waypoints-list">
          <div 
            v-for="(wp, index) in waypoints" 
            :key="index"
            class="waypoint-item"
          >
            <div class="waypoint-number">{{ index + 1 }}</div>
            <div class="waypoint-info">
              <div class="waypoint-coords">
                <span class="coord-label">纬度:</span>
                <span class="coord-value">{{ wp.lat.toFixed(6) }}°</span>
              </div>
              <div class="waypoint-coords">
                <span class="coord-label">经度:</span>
                <span class="coord-value">{{ wp.lon.toFixed(6) }}°</span>
              </div>
              <div class="waypoint-coords">
                <span class="coord-label">高度:</span>
                <span class="coord-value">{{ wp.alt.toFixed(1) }} m</span>
              </div>
            </div>
            <div class="waypoint-actions">
              <button class="action-btn" @click="editWaypoint(index)">编辑</button>
              <button class="action-btn" @click="deleteWaypoint(index)">删除</button>
              <button class="action-btn" @click="moveUp(index)">↑</button>
              <button class="action-btn" @click="moveDown(index)">↓</button>
            </div>
          </div>
        </div>
        
        <div class="add-waypoint">
          <button class="btn primary" @click="showAddDialog">+ 添加航点</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const waypoints = ref([
  { lat: 39.0900, lon: 117.1230, alt: 100.0 },
  { lat: 39.0910, lon: 117.1240, alt: 110.0 },
  { lat: 39.0920, lon: 117.1250, alt: 115.0 },
  { lat: 39.0930, lon: 117.1260, alt: 120.0 }
])

const totalDistance = ref(2.5)

const editWaypoint = (index) => {
  console.log('编辑航点:', index)
}

const deleteWaypoint = (index) => {
  waypoints.value.splice(index, 1)
}

const moveUp = (index) => {
  if (index > 0) {
    const temp = waypoints.value[index]
    waypoints.value[index] = waypoints.value[index - 1]
    waypoints.value[index - 1] = temp
  }
}

const moveDown = (index) => {
  if (index < waypoints.value.length - 1) {
    const temp = waypoints.value[index]
    waypoints.value[index] = waypoints.value[index + 1]
    waypoints.value[index + 1] = temp
  }
}

const showAddDialog = () => {
  console.log('显示添加航点对话框')
}
</script>

<style scoped>
.mission-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0a0a0a 0%, #1a1a1a 100%);
}

.mission-header {
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #333;
}

.mission-header h2 {
  font-size: 24px;
  color: #ffffff;
  margin: 0;
}

.mission-actions {
  display: flex;
  gap: 12px;
}

.mission-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.waypoints-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.waypoints-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.waypoints-header h3 {
  font-size: 18px;
  color: #00bcd4;
  margin: 0;
}

.waypoints-stats {
  display: flex;
  gap: 24px;
  color: #b0b0b0;
  font-size: 14px;
}

.waypoints-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.waypoint-item {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 12px;
  gap: 16px;
}

.waypoint-number {
  width: 40px;
  height: 40px;
  background: #00bcd4;
  color: #ffffff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
}

.waypoint-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.waypoint-coords {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.coord-label {
  color: #808080;
  font-size: 12px;
}

.coord-value {
  color: #00bcd4;
  font-weight: bold;
  font-size: 14px;
  font-family: 'Courier New', monospace;
}

.waypoint-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-btn {
  padding: 4px 12px;
  border: 1px solid #333;
  background: #1a1a1a;
  color: #b0b0b0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #333;
  color: #00bcd4;
}

.add-waypoint {
  text-align: center;
  padding-top: 16px;
}

.btn {
  padding: 10px 24px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
  transition: all 0.2s;
}

.btn.primary {
  background: #00bcd4;
  color: #ffffff;
}

.btn.primary:hover {
  background: #008ba3;
}

.btn.secondary {
  background: #333;
  color: #b0b0b0;
}

.btn.secondary:hover {
  background: #444;
}
</style>