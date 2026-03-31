<template>
  <div class="map-view">
    <div class="map-header">
      <h2>地图视图</h2>
      <div class="map-controls">
        <button class="control-btn" @click="centerOnDrone">定位到无人机</button>
        <button class="control-btn" @click="clearTrajectory">清除轨迹</button>
        <label class="checkbox-label">
          <input type="checkbox" v-model="showGrid" />
          显示网格
        </label>
      </div>
    </div>
    
    <div class="map-content">
      <div class="map-placeholder">
        <div class="map-info">
          <span class="map-icon">🗺️</span>
          <div class="map-coordinates">
            <div>无人机位置</div>
            <div class="coord-value">{{ dronePosition }}</div>
          </div>
        </div>
        <div class="map-legend">
          <div class="legend-item">
            <span class="legend-marker">🚁</span>
            <span>无人机位置</span>
          </div>
          <div class="legend-item">
            <span class="legend-marker">•</span>
            <span>飞行轨迹</span>
          </div>
          <div class="legend-item">
            <span class="legend-marker">★</span>
            <span>航点</span>
          </div>
          <div class="legend-item">
            <span class="legend-marker">🔵</span>
            <span>障碍物</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const dronePosition = ref('39.0900°N, 117.1230°E')
const showGrid = ref(true)

const centerOnDrone = () => {
  console.log('定位到无人机')
}

const clearTrajectory = () => {
  console.log('清除轨迹')
}
</script>

<style scoped>
.map-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0a0a0a 0%, #1a1a1a 100%);
}

.map-header {
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #333;
}

.map-header h2 {
  font-size: 18px;
  color: #ffffff;
  margin: 0;
}

.map-controls {
  display: flex;
  gap: 12px;
}

.control-btn {
  padding: 8px 16px;
  border: 1px solid #333;
  background: #1a1a1a;
  color: #00bcd4;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.control-btn:hover {
  background: #333;
  border-color: #00bcd4;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #b0b0b0;
  cursor: pointer;
}

.map-content {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.map-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}

.map-info {
  text-align: center;
}

.map-icon {
  font-size: 64px;
  margin-bottom: 32px;
}

.map-coordinates {
  color: #b0b0b0;
  font-size: 14px;
}

.coord-value {
  color: #00bcd4;
  font-weight: bold;
  font-size: 18px;
  margin-top: 8px;
}

.map-legend {
  margin-top: 32px;
  background: rgba(0, 0, 0, 0.5);
  padding: 16px 24px;
  border-radius: 8px;
  border: 1px solid #333;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #b0b0b0;
}

.legend-marker {
  font-size: 18px;
}
</style>