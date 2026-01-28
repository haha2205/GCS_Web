<template>
  <div class="kpi-panel mission-panel">
    <div class="kpi-header">
      <div class="kpi-title">
        <span class="dimension-icon">🎯</span>
        <span>任务效能 (Mission)</span>
      </div>
      <div class="kpi-score" :class="getScoreClass(score)">
        {{ (score * 100).toFixed(0) }}%
      </div>
    </div>

    <!-- 进度曲线 -->
    <EChartWrapper
      title="任务进度"
      unit="%"
      :series="progressSeries"
      :yMin="0"
      :yMax="100"
    />

    <!-- 安全余量曲线 -->
    <EChartWrapper
      title="安全余量 (电量%)"
      unit="%"
      :series="safetySeries"
      :yMin="-10"
      :yMax="50"
    />

    <!-- 指标详情 -->
    <div class="kpi-metrics-grid">
      <div class="metric-item">
        <div class="metric-label">任务进度</div>
        <div class="metric-value" :class="getProgressClass">
          {{ metrics.progress }}%
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">安全余量</div>
        <div class="metric-value" :class="getSafetyClass">
          {{ metrics.safety_margin }}%
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">效能评分</div>
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

const progressSeries = ref([
  {
    name: '进度',
    data: [],
    lineStyle: { color: '#00d2d3' },
    itemStyle: { color: '#00d2d3' }
  }
])

const safetySeries = ref([
  {
    name: '安全余量',
    data: [],
    lineStyle: { color: '#ff6348' },
    itemStyle: { color: '#ff6348' }
  }
])

const historyLength = 100
const progressHistory = ref([])
const safetyHistory = ref([])

// 当前指标值
const metrics = computed(() => {
  return Object.assign({
    progress: 0,
    safety_margin: 0,
    score: 1.0
  }, props.dimensionData)
})

// 实时评分
const score = computed(() => {
  return metrics.value?.score || 0
})

// 监听数据更新
watch(() => props.dimensionData, (newData) => {
  if (newData && newData.progress !== undefined) {
    updateHistory(newData)
  }
}, { immediate: true, deep: true })

const updateHistory = (data) => {
  if (!data) return
  
  // 添加新数据点
  progressHistory.value.push(data.progress)
  safetyHistory.value.push(data.safety_margin)
  
  // 保持历史数据长度
  if (progressHistory.value.length > historyLength) {
    progressHistory.value.shift()
  }
  if (safetyHistory.value.length > historyLength) {
    safetyHistory.value.shift()
  }
  
  // 更新图表数据
  progressSeries.value[0].data = [...progressHistory.value]
  safetySeries.value[0].data = [...safetyHistory.value]
}

const getScoreClass = (value) => {
  if (value >= 0.8) return 'score-good'
  if (value >= 0.6) return 'score-warning'
  return 'score-danger'
}

const getProgressClass = computed(() => {
  const progress = metrics.value?.progress || 0
  if (progress >= 90) return 'progress-good'
  if (progress >= 50) return 'progress-warning'
  return 'progress-danger'
})

const getSafetyClass = computed(() => {
  const margin = metrics.value?.safety_margin || 0
  if (margin > 20) return 'safety-good'
  if (margin > 5) return 'safety-warning'
  return 'safety-danger'
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

.progress-good {
  color: #2ed573;
}

.progress-warning {
  color: #ffc107;
}

.progress-danger {
  color: #ff5252;
}

.safety-good {
  color: #2ed573;
}

.safety-warning {
  color: #ffc107;
}

.safety-danger {
  color: #ff5252;
}
</style>