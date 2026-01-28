<template>
  <div class="kpi-panel communication-panel">
    <div class="kpi-header">
      <div class="kpi-title">
        <span class="dimension-icon">📡</span>
        <span>通信资源 (Communication)</span>
      </div>
      <div class="kpi-score" :class="getScoreClass(score)">
        {{ (score * 100).toFixed(0) }}%
      </div>
    </div>

    <!-- 抖动曲线 -->
    <EChartWrapper
      title="网络抖动"
      unit="ms"
      :series="jitterSeries"
      :yMin="0"
      :yMax="50"
    />

    <!-- 丢包率曲线 -->
    <EChartWrapper
      title="丢包率"
      unit="%"
      :series="plrSeries"
      :yMin="0"
      :yMax="10"
    />

    <!-- 指标详情 -->
    <div class="kpi-metrics-grid">
      <div class="metric-item">
        <div class="metric-label">实时抖动</div>
        <div class="metric-value">{{ metrics.jitter_ms }} ms</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">实时丢包率</div>
        <div class="metric-value" :class="getPLRClass">
          {{ metrics.plr_percent }}%
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">通信评分</div>
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

const jitterSeries = ref([
  {
    name: '抖动',
    data: [],
    lineStyle: { color: '#5f27cd' },
    itemStyle: { color: '#5f27cd' }
  }
])

const plrSeries = ref([
  {
    name: '丢包率',
    data: [],
    lineStyle: { color: '#ff6b6b' },
    itemStyle: { color: '#ff6b6b' }
  }
])

const historyLength = 100
const jitterHistory = ref([])
const plrHistory = ref([])

// 当前指标值
const metrics = computed(() => {
  return Object.assign({
    jitter_ms: 0,
    plr_percent: 0,
    score: 1.0
  }, props.dimensionData)
})

// 实时评分
const score = computed(() => {
  return metrics.value?.score || 0
})

// 监听数据更新
watch(() => props.dimensionData, (newData) => {
  if (newData && newData.jitter_ms !== undefined) {
    updateHistory(newData)
  }
}, { immediate: true, deep: true })

const updateHistory = (data) => {
  if (!data) return
  
  // 添加新数据点
  jitterHistory.value.push(data.jitter_ms)
  plrHistory.value.push(data.plr_percent)
  
  // 保持历史数据长度
  if (jitterHistory.value.length > historyLength) {
    jitterHistory.value.shift()
  }
  if (plrHistory.value.length > historyLength) {
    plrHistory.value.shift()
  }
  
  // 更新图表数据
  jitterSeries.value[0].data = [...jitterHistory.value]
  plrSeries.value[0].data = [...plrHistory.value]
}

const getScoreClass = (value) => {
  if (value >= 0.8) return 'score-good'
  if (value >= 0.6) return 'score-warning'
  return 'score-danger'
}

const getPLRClass = computed(() => {
  const plr = metrics.value?.plr_percent || 0
  if (plr < 1) return 'plr-good'
  if (plr < 3) return 'plr-warning'
  return 'plr-danger'
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

.plr-good {
  color: #2ed573;
}

.plr-warning {
  color: #ffc107;
}

.plr-danger {
  color: #ff5252;
}
</style>