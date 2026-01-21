<template>
  <div class="monitor-view">
    <div class="monitor-header">
      <h2>数据监控</h2>
    </div>
    
    <div class="monitor-content">
      <!-- 性能图表 -->
      <div class="monitor-card">
        <div class="card-header">
          <span>飞行性能</span>
          <span class="card-icon">📈</span>
        </div>
        <div class="chart-container">
          <div class="chart-placeholder">图表区域 - ECharts</div>
        </div>
      </div>
      
      <!-- 姿态历史 -->
      <div class="monitor-card">
        <div class="card-header">
          <span>姿态历史</span>
          <span class="card-icon">📊</span>
        </div>
        <div class="data-table">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>滚转(°)</th>
                <th>俯仰(°)</th>
                <th>偏航(°)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in attitudeHistory" :key="item.time">
                <td>{{ item.time }}</td>
                <td class="data-value">{{ item.roll.toFixed(2) }}</td>
                <td class="data-value">{{ item.pitch.toFixed(2) }}</td>
                <td class="data-value">{{ item.yaw.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 速度历史 -->
      <div class="monitor-card">
        <div class="card-header">
          <span>速度历史</span>
          <span class="card-icon">⚡</span>
        </div>
        <div class="data-table">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>Vx(m/s)</th>
                <th>Vy(m/s)</th>
                <th>Vz(m/s)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in velocityHistory" :key="item.time">
                <td>{{ item.time }}</td>
                <td class="data-value">{{ item.vx.toFixed(2) }}</td>
                <td class="data-value">{{ item.vy.toFixed(2) }}</td>
                <td class="data-value">{{ item.vz.toFixed(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const attitudeHistory = ref([
  { time: '10:30:15', roll: 2.5, pitch: -1.8, yaw: 15.7 },
  { time: '10:30:14', roll: 2.3, pitch: -2.0, yaw: 15.5 },
  { time: '10:30:13', roll: 2.1, pitch: -2.2, yaw: 15.3 },
  { time: '10:30:12', roll: 1.9, pitch: -2.4, yaw: 15.1 },
  { time: '10:30:11', roll: 1.7, pitch: -2.6, yaw: 14.9 }
])

const velocityHistory = ref([
  { time: '10:30:15', vx: 12.5, vy: 3.2, vz: -0.8 },
  { time: '10:30:14', vx: 12.3, vy: 3.1, vz: -0.7 },
  { time: '10:30:13', vx: 12.1, vy: 3.0, vz: -0.6 },
  { time: '10:30:12', vx: 11.9, vy: 2.9, vz: -0.5 },
  { time: '10:30:11', vx: 11.7, vy: 2.8, vz: -0.4 }
])
</script>

<style scoped>
.monitor-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #0a0a0a 0%, #1a1a1a 100%);
}

.monitor-header {
  padding: 24px;
}

.monitor-header h2 {
  color: #ffffff;
  margin: 0;
}

.monitor-content {
  flex: 1;
  padding: 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  overflow-y: auto;
}

.monitor-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid #333;
  border-radius: 8px;
  overflow: hidden;
}

.card-header {
  padding: 12px 16px;
  background: rgba(0, 188, 212, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  font-weight: bold;
  color: #00bcd4;
}

.card-icon {
  font-size: 20px;
}

.chart-container {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-placeholder {
  color: #808080;
  font-size: 14px;
}

.data-table {
  padding: 16px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th {
  padding: 8px;
  text-align: left;
  background: rgba(0, 0, 0, 0.05);
  color: #b0b0b0;
  font-size: 12px;
  border-bottom: 1px solid #444;
}

td {
  padding: 8px;
  text-align: center;
  color: #e0e0e0;
  font-size: 13px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-value {
  color: #00bcd4;
  font-weight: bold;
  font-family: 'Courier New', monospace;
}
</style>