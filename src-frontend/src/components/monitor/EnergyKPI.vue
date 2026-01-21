<template>
  <div class="kpi-panel energy-panel">
    <div class="kpi-header">
      <div class="kpi-title">
        <span class="dimension-icon">🔋</span>
        <span>能耗指标 (Energy)</span>
      </div>
      <div class="kpi-score" :class="getScoreClass(score)">
        {{ (score * 100).toFixed(0) }}%
      </div>
    </div>

    <!-- 功率曲线 -->
    <EChartWrapper
      title="瞬时功率"
      unit="W"
      :series="powerSeries"
      :yMin="0"
      :yMax="500"
    />

    <!-- 指标详情 -->
    <div class="kpi-metrics-grid">
      <div class="metric-item">
        <div class="metric-label">瞬时功率</div>
        <div class="metric-value" :class="getPowerClass">
          {{ metrics.power_watts }} W
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">累计能耗</div>
        <div class="metric-value">
          {{ (metrics.total_joules / 1000).toFixed(1) }} kJ
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">能耗评分</div>
        <div class="metric-value" :class="getScoreClass(score)">
          {{ (score * 100).toFixed(1) }}%
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import EChartWrapper from './EChartWrapper.vue'

const props = defineProps({
  dimensionData: {
    type: Object,
    default: () => ({})
  }
})

const powerSeries = ref([
  {
    name: '功率',
    data: [],
    lineStyle: { color: '#ffa502' },
    itemStyle: { color: '#ffa502' }
  }
])

const historyLength = 100
const powerHistory = ref([])

// 当前指标值
const metrics = computed(() => {
  return props.dimensionData || {
    power_watts: 0,
    total_joules: 0,
    score: 1.0
  }
})

// 实时评分
const score = computed(() => {
  return metrics.value?.score || 0
})

// 监听数据更新
watch(() => props.dimensionData, (newData) => {
  if (newData && newData.power_watts !== undefined) {
    updateHistory(newData)
  }
}, { immediate: true, deep: true })

const updateHistory = (data) => {
  if (!data) return
  
  // 添加新数据点
  powerHistory.value.push(data.power_watts)
  
  // 保持历史数据长度
  if (powerHistory.value.length > historyLength) {
    powerHistory.value.shift()
  }
  
  // 更新图表数据
  powerSeries.value[0].data = [...powerHistory.value]
}

const getScoreClass = (value) => {
  if (value >= 0.8) return 'score-good'
  if (value >= 0.6) return 'score-warning'
  return 'score-danger'
}

const getPowerClass = computed(() => {
  const power = metrics.value?.power_watts || 0
  if (power < 200) return 'power-good'
  if (power < 350) return 'power-warning'
  return 'power-danger'
})
</script>

<style scoped>
.kpi-panel {
  background: rgba(20, 20, 25, 0.8);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid #333;
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #333;
}

.kpi-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
}

.dimension-icon {
  font-size: 18px;
}

.kpi-score {
  font-size: 16px;
  font-weight: bold;
  padding: 4px 12px;
  border-radius: 4px;
}

.score-good {
  background: rgba(46, 213, 115, 0.2);
  color: #2ed573;
}

.score-warning {
  background: rgba(255, 193, 7, 0.2);
  color: #ffc107;
}

.score-danger {
  background: rgba(255, 82, 82, 0.2);
  color: #ff5252;
}

.kpi-metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 12px;
}

.metric-item {
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
  border-radius: 6px;
}

.metric-label {
  font-size: 11px;
  color: #888;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
  color: #ffffff;
  font-family: 'Courier New', monospace;
}

.power-good {
  color: #2ed573;
}

.power-warning {
  color: #ffc107;
}

.power-danger {
  color: #ff5252;
}
</style>