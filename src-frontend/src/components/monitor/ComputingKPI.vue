<template>
  <div class="kpi-panel computing-panel">
    <div class="kpi-header">
      <div class="kpi-title">
        <span class="dimension-icon">⚙️</span>
        <span>算力资源 (Computing)</span>
      </div>
      <div class="kpi-score" :class="getScoreClass(score)">
        {{ (score * 100).toFixed(0) }}%
      </div>
    </div>

    <!-- CPU负载曲线 -->
    <EChartWrapper
      title="CPU负载"
      unit="%"
      :series="cpuSeries"
      :yMin="0"
      :yMax="100"
    />

    <!-- 指标详情 -->
    <div class="kpi-metrics-grid">
      <div class="metric-item">
        <div class="metric-label">实时负载</div>
        <div class="metric-value">{{ metrics.cpu_load_realtime }}%</div>
      </div>
      <div class="metric-item">
        <div class="metric-label">利用率评分</div>
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

const cpuSeries = ref([
  {
    name: 'CPU负载',
    data: [],
    lineStyle: { color: '#ff9f43' },
    itemStyle: { color: '#ff9f43' }
  }
])

const historyLength = 100
const historyData = ref([])

// 当前指标值
const metrics = computed(() => {
  return Object.assign({
    cpu_load_realtime: 0,
    score: 1.0
  }, props.dimensionData)
})

// 实时评分
const score = computed(() => {
  return metrics.value?.score || 0
})

// 监听数据更新
watch(() => props.dimensionData, (newData) => {
  if (newData && newData.cpu_load_realtime !== undefined) {
    updateHistory(newData)
  }
}, { immediate: true, deep: true })

const updateHistory = (data) => {
  if (!data) return
  
  // 添加新数据点
  historyData.value.push(data.cpu_load_realtime)
  
  // 保持历史数据长度
  if (historyData.value.length > historyLength) {
    historyData.value.shift()
  }
  
  // 更新图表数据
  cpuSeries.value[0].data = [...historyData.value]
}

const getScoreClass = (value) => {
  if (value >= 0.8) return 'score-good'
  if (value >= 0.6) return 'score-warning'
  return 'score-danger'
}
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
  grid-template-columns: repeat(2, 1fr);
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
</style>