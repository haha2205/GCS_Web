<template>
  <div class="kpi-panel performance-panel">
    <div class="kpi-header">
      <div class="kpi-title">
        <span class="dimension-icon">✈️</span>
        <span>飞行性能 (Performance)</span>
      </div>
      <div class="kpi-score" :class="getScoreClass(score)">
        {{ (score * 100).toFixed(0) }}%
      </div>
    </div>

    <!-- 位置误差曲线 -->
    <EChartWrapper
      title="位置误差 (RMSE)"
      unit="m"
      :series="rmseSeries"
      :yMin="0"
      :yMax="3"
    />

    <!-- 指标详情 -->
    <div class="kpi-metrics-grid">
      <div class="metric-item">
        <div class="metric-label">实时误差</div>
        <div class="metric-value" :class="getRMSEClass">
          {{ metrics.rmse.toFixed(3) }} m
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">偏差方向</div>
        <div class="metric-value deviation-direction">
          {{ deviationDirection }}
        </div>
      </div>
      <div class="metric-item">
        <div class="metric-label">性能评分</div>
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

const rmseSeries = ref([
  {
    name: 'RMSE',
    data: [],
    lineStyle: { color: '#ee5a24' },
    itemStyle: { color: '#ee5a24' }
  }
])

const historyLength = 100
const rmseHistory = ref([])

// 当前指标值
const metrics = computed(() => {
  return Object.assign({
    rmse: 0,
    score: 1.0
  }, props.dimensionData)
})

// 实时评分
const score = computed(() => {
  return metrics.value?.score || 0
})

// 偏差方向（示例实现，实际可能需要更复杂的计算）
const deviationDirection = computed(() => {
  const rmse = metrics.value?.rmse || 0
  if (rmse < 0.5) return '优秀'
  if (rmse < 1.0) return '良好'
  if (rmse < 2.0) return '一般'
  return '较差'
})

// 监听数据更新
watch(() => props.dimensionData, (newData) => {
  if (newData && newData.rmse !== undefined) {
    updateHistory(newData)
  }
}, { immediate: true, deep: true })

const updateHistory = (data) => {
  if (!data) return
  
  // 添加新数据点
  rmseHistory.value.push(data.rmse)
  
  // 保持历史数据长度
  if (rmseHistory.value.length > historyLength) {
    rmseHistory.value.shift()
  }
  
  // 更新图表数据
  rmseSeries.value[0].data = [...rmseHistory.value]
}

const getScoreClass = (value) => {
  if (value >= 0.8) return 'score-good'
  if (value >= 0.6) return 'score-warning'
  return 'score-danger'
}

const getRMSEClass = computed(() => {
  const rmse = metrics.value?.rmse || 0
  if (rmse < 0.5) return 'rmse-good'
  if (rmse < 1.5) return 'rmse-warning'
  return 'rmse-danger'
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

.deviation-direction {
  color: #00d2d3;
}

.rmse-good {
  color: #2ed573;
}

.rmse-warning {
  color: #ffc107;
}

.rmse-danger {
  color: #ff5252;
}
</style>