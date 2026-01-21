<template>
  <div class="pnc-monitor">
    <!-- Tab切换 -->
    <div class="monitor-tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        class="tab-btn"
        :class="{ active: currentTab === tab.id }"
        @click="currentTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab内容 -->
    <div class="tab-content">
      <!-- Control Tab -->
      <div v-show="currentTab === 'control'" class="tab-panel">
        <div class="charts-grid">
          <!-- Roll Response -->
          <div class="chart-section">
            <div class="chart-header">
              <span class="chart-title">Roll Response</span>
              <div class="stats-panel">
                <span class="stat-label">Err:</span>
                <span class="stat-value" :class="{ warning: rollErr > 5, error: rollErr > 10 }">{{ rollErr.toFixed(2) }}°</span>
              </div>
            </div>
            <EChartWrapper
              :series="rollResponse"
              title="Roll (°)"
              unit="°"
              :yMin="-15"
              :yMax="15"
            />
          </div>

          <!-- Pitch Response -->
          <div class="chart-section">
            <div class="chart-header">
              <span class="chart-title">Pitch Response</span>
              <div class="stats-panel">
                <span class="stat-label">Err:</span>
                <span class="stat-value" :class="{ warning: pitchErr > 5, error: pitchErr > 10 }">{{ pitchErr.toFixed(2) }}°</span>
              </div>
            </div>
            <EChartWrapper
              :series="pitchResponse"
              title="Pitch (°)"
              unit="°"
              :yMin="-15"
              :yMax="15"
            />
          </div>
        </div>
      </div>

      <!-- Nav Tab -->
      <div v-show="currentTab === 'nav'" class="tab-panel">
        <div class="charts-grid">
          <!-- Speed Tracking -->
          <div class="chart-section">
            <div class="chart-header">
              <span class="chart-title">Speed Tracking</span>
              <div class="stats-panel">
                <span class="stat-label">Err:</span>
                <span class="stat-value" :class="{ warning: speedErr > 2, error: speedErr > 5 }">{{ speedErr.toFixed(2) }} m/s</span>
              </div>
            </div>
            <EChartWrapper
              :series="speedTracking"
              title="Speed (m/s)"
              unit="m/s"
              :yMin="0"
              :yMax="25"
            />
          </div>

          <!-- Altitude Tracking -->
          <div class="chart-section">
            <div class="chart-header">
              <span class="chart-title">Altitude Tracking</span>
              <div class="stats-panel">
                <span class="stat-label">Err:</span>
                <span class="stat-value" :class="{ warning: altErr > 3, error: altErr > 10 }">{{ altErr.toFixed(2) }} m</span>
              </div>
            </div>
            <EChartWrapper
              :series="altitudeTracking"
              title="Altitude (m)"
              unit="m"
              :yMin="0"
              :yMax="200"
            />
          </div>

          <!-- Cross-track Error -->
          <div class="chart-section full-width">
            <div class="chart-header">
              <span class="chart-title">Cross-track Error</span>
              <div class="stats-panel">
                <span class="stat-label">XTE:</span>
                <span class="stat-value" :class="{ warning: Math.abs(crossTrackError) > 5, error: Math.abs(crossTrackError) > 10 }">
                  {{ crossTrackError > 0 ? '+' : '' }}{{ crossTrackError.toFixed(2) }} m
                </span>
              </div>
            </div>
            <EChartWrapper
              :series="crossTrackSeries"
              title="Cross-track (m)"
              unit="m"
              :yMin="-20"
              :yMax="20"
            />
          </div>
        </div>
      </div>

      <!-- Sys Tab -->
      <div v-show="currentTab === 'sys'" class="tab-panel">
        <div class="charts-grid">
          <!-- Vibration Analysis -->
          <div class="chart-section full-width">
            <div class="chart-header">
              <span class="chart-title">Vibration Analysis</span>
              <div class="stats-panel">
                <span class="stat-label">Max:</span>
                <span class="stat-value" :class="{ warning: maxVibration > 0.5, error: maxVibration > 1.0 }">
                  {{ maxVibration.toFixed(3) }} g
                </span>
              </div>
            </div>
            <EChartWrapper
              :series="vibrationSeries"
              title="Vibration (g)"
              unit="g"
              :yMin="0"
              :yMax="1.5"
            />
          </div>

          <!-- Voltage & Current -->
          <div class="chart-section">
            <div class="chart-header">
              <span class="chart-title">Power Status</span>
            </div>
            <EChartWrapper
              :series="voltageCurrentSeries"
              title="Voltage (V) / Current (A)"
              unit=""
              :yMin="0"
              :yMax="30"
            />
          </div>

          <!-- Battery Level -->
          <div class="chart-section">
            <div class="chart-header">
              <span class="chart-title">Battery Level</span>
              <div class="stats-panel">
                <span class="stat-label">Level:</span>
                <span class="stat-value" :class="{ 
                  warning: batteryLevel < 30 && batteryLevel > 15, 
                  error: batteryLevel <= 15 
                }">
                  {{ batteryLevel.toFixed(0) }}%
                </span>
              </div>
            </div>
            <EChartWrapper
              :series="batterySeries"
              title="Battery (%)"
              unit="%"
              :yMin="0"
              :yMax="100"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import EChartWrapper from '../monitor/EChartWrapper.vue'

const droneStore = useDroneStore()
const currentTab = ref('control')

const tabs = [
  { id: 'control', label: 'Control' },
  { id: 'nav', label: 'Navigation' },
  { id: 'sys', label: 'System' }
]

// 仿真数据（临时用于测试）
// 实际应用中，这些数据来自 drone store
const crossTrackError = ref(0)
const maxVibration = ref(0)
const vibrationHistory = ref([])
const crossTrackHistory = ref([])
const voltageCurrentHistory = ref([])
const batteryHistory = ref([])

// 计算误差
const rollErr = computed(() => {
  const history = droneStore.history.rollActual
  const target = droneStore.history.rollTarget
  if (history.length === 0 || target.length === 0) return 0
  return Math.abs(history[history.length - 1] - (target[target.length - 1] || 0))
})

const pitchErr = computed(() => {
  const history = droneStore.history.pitchActual
  const target = droneStore.history.pitchTarget
  if (history.length === 0 || target.length === 0) return 0
  return Math.abs(history[history.length - 1] - (target[target.length - 1] || 0))
})

const speedErr = computed(() => {
  const history = droneStore.history.speedActual
  const target = droneStore.history.speedTarget
  if (history.length === 0 || target.length === 0) return 0
  return Math.abs(history[history.length - 1] - (target[target.length - 1] || 0))
})

const altErr = computed(() => {
  const history = droneStore.history.altitudeActual
  const target = droneStore.history.altitudeTarget
  if (history.length === 0 || target.length === 0) return 0
  return Math.abs(history[history.length - 1] - (target[target.length - 1] || 0))
})

// Control 数据 - 从 drone store 构建图表数据
const rollResponse = computed(() => {
  const { rollTarget, rollActual } = droneStore.history
  return [
    {
      name: 'Target',
      data: rollTarget,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#ff9800', width: 2, type: 'dashed' }
    },
    {
      name: 'Actual',
      data: rollActual,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#3288fa', width: 2 }
    }
  ]
})

const pitchResponse = computed(() => {
  const { pitchTarget, pitchActual } = droneStore.history
  return [
    {
      name: 'Target',
      data: pitchTarget,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#ff9800', width: 2, type: 'dashed' }
    },
    {
      name: 'Actual',
      data: pitchActual,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#3288fa', width: 2 }
    }
  ]
})

// Nav 数据
const speedTracking = computed(() => {
  const { speedTarget, speedActual } = droneStore.history
  return [
    {
      name: 'Target',
      data: speedTarget,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#ff9800', width: 2, type: 'dashed' }
    },
    {
      name: 'Actual',
      data: speedActual,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#3288fa', width: 2 }
    }
  ]
})

const altitudeTracking = computed(() => {
  const { altitudeTarget, altitudeActual } = droneStore.history
  return [
    {
      name: 'Target',
      data: altitudeTarget,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#ff9800', width: 2, type: 'dashed' }
    },
    {
      name: 'Actual',
      data: altitudeActual,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#3288fa', width: 2 }
    }
  ]
})

const crossTrackSeries = computed(() => {
  return [{
    name: 'Cross-track',
    data: crossTrackHistory.value,
    type: 'line',
    smooth: true,
    lineStyle: { color: '#ff9800', width: 2 },
    areaStyle: {
      color: 'rgba(255, 152, 0, 0.1)'
    }
  }]
})

// Sys 数据
const vibrationSeries = computed(() => {
  return [{
    name: 'Vibration',
    data: vibrationHistory.value,
    type: 'line',
    smooth: true,
    lineStyle: { color: '#9c27b0', width: 2 }
  }]
})

const voltageCurrentSeries = computed(() => {
  const voltage = voltageCurrentHistory.value.map(v => v.voltage)
  const current = voltageCurrentHistory.value.map(v => v.current)
  
  return [
    {
      name: 'Voltage',
      data: voltage,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#4caf50', width: 2 }
    },
    {
      name: 'Current',
      data: current,
      type: 'line',
      smooth: true,
      lineStyle: { color: '#2196f3', width: 2, type: 'dashed' }
    }
  ]
})

const batterySeries = computed(() => {
  return [{
    name: 'Battery',
    data: batteryHistory.value,
    type: 'line',
    smooth: true,
    lineStyle: { color: droneStore.systemStatus.battery < 30 ? '#d32f2f' : '#4caf50', width: 2 },
    areaStyle: {
      color: droneStore.systemStatus.battery < 30 ? 'rgba(211, 47, 47, 0.15)' : 'rgba(76, 175, 80, 0.15)'
    }
  }]
})

const batteryLevel = computed(() => droneStore.systemStatus.battery || 100)

// 仿真数据更新（实际应用中应由 drone store 提供）
let updateInterval = null

const updateSimulatedData = () => {
  // 更新振动数据
  const vibration = Math.random() * 0.3 + (Math.random() < 0.1 ? 0.5 : 0)
  vibrationHistory.value.push(vibration)
  if (vibrationHistory.value.length > 100) vibrationHistory.value.shift()
  maxVibration.value = Math.max(...vibrationHistory.value.slice(-10))
  
  // 更新偏航误差数据
  const xte = (Math.random() - 0.5) * 3
  crossTrackHistory.value.push(xte)
  if (crossTrackHistory.value.length > 100) crossTrackHistory.value.shift()
  crossTrackError.value = crossTrackHistory.value[crossTrackHistory.value.length - 1] || 0
  
  // 更新电压电流数据
  voltageCurrentHistory.value.push({
    voltage: droneStore.systemStatus.voltage + (Math.random() - 0.5) * 0.5,
    current: droneStore.systemStatus.current + (Math.random() - 0.5) * 0.3
  })
  if (voltageCurrentHistory.value.length > 100) voltageCurrentHistory.value.shift()
  
  // 更新电池数据
  batteryHistory.value.push(droneStore.systemStatus.battery)
  if (batteryHistory.value.length > 100) batteryHistory.value.shift()
}

onMounted(() => {
  // 初始化数据
  updateSimulatedData()
  
  // 启动定时更新（仅用于仿真）
  updateInterval = setInterval(updateSimulatedData, 1000)
})

onUnmounted(() => {
  if (updateInterval) clearInterval(updateInterval)
})
</script>

<style scoped>
.pnc-monitor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(30, 30, 30, 0.8);
  border-radius: 8px;
  overflow: hidden;
}

.monitor-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 12px;
  background: rgba(20, 20, 20, 0.9);
  border-bottom: 1px solid #3a3a3a;
}

.tab-btn {
  flex: 1;
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #999;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tab-btn:hover {
  background: rgba(50, 50, 50, 0.8);
  color: #ccc;
}

.tab-btn.active {
  background: rgba(50, 136, 250, 0.2);
  color: #3288fa;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.chart-section {
  background: rgba(25, 25, 25, 0.9);
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #333;
}

.chart-section.full-width {
  grid-column: 1 / -1;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
}

.stats-panel {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(50, 50, 50, 0.8);
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid #444;
}

.stat-label {
  font-size: 11px;
  color: #999;
  font-weight: 600;
}

.stat-value {
  font-size: 12px;
  font-weight: 700;
  color: #4caf50;
  font-family: 'Roboto', 'Segoe UI', monospace;
  min-width: 50px;
  text-align: right;
}

.stat-value.warning {
  color: #ff9800;
}

.stat-value.error {
  color: #d32f2f;
}

.tab-content::-webkit-scrollbar {
  width: 6px;
}

.tab-content::-webkit-scrollbar-track {
  background: rgba(20, 20, 20, 0.5);
}

.tab-content::-webkit-scrollbar-thumb {
  background: #3288fa;
  border-radius: 3px;
}

.tab-content::-webkit-scrollbar-thumb:hover {
  background: #2676ea;
}
</style>