<template>
  <div class="analysis-panel">
    <!-- 变量选择区 -->
    <div class="selector-section">
      <div class="selector-header">
        <h4>变量选择</h4>
        <div class="selector-actions">
          <button
            @click="fetchHeaders"
            class="refresh-variables-btn"
            :disabled="loading"
          >
            🔄 刷新
          </button>
          <button
            @click="applySelection"
            class="apply-btn"
            :disabled="loading || selectedCount === 0"
          >
            应用选择 ({{ selectedCount }})
          </button>
          <button
            @click="clearSelection"
            class="clear-btn-small"
          >
            清空
          </button>
        </div>
      </div>
      
      <!-- 搜索框 -->
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索变量..."
          class="search-input"
        />
        <span class="search-icon">🔍</span>
      </div>
      
      <!-- 变量分类列表 -->
      <div class="categories-container">
        <details
          v-for="(variables, category) in filteredCategories"
          :key="category"
          class="category-group"
          :open="expandedCategories[category]"
        >
          <summary
            @click.prevent="toggleCategory(category)"
            class="category-header"
          >
            <span class="category-icon">
              {{ expandedCategories[category] ? '▼' : '▶' }}
            </span>
            <span class="category-name">{{ category }}</span>
            <span class="category-count">({{ variables.length }})</span>
          </summary>
          <div class="category-content">
            <label
              v-for="variable in variables"
              :key="variable"
              class="variable-checkbox"
            >
              <input
                type="checkbox"
                :value="variable"
                v-model="tempSelectedVariables"
              />
              <span class="variable-text">{{ formatVariableName(variable) }}</span>
            </label>
          </div>
        </details>
      </div>
    </div>
    
    <!-- 图表显示区 -->
    <div class="charts-section">
      <div class="charts-header">
        <h3>分析图表</h3>
        <div class="time-info">{{ timeInfo }}</div>
      </div>
      
      <div v-if="!hasData" class="empty-state">
        <div class="empty-icon">📊</div>
        <p class="empty-text">请在上方选择变量并点击"应用选择"</p>
        <p class="empty-hint">已选择 {{ selectedCount }} 个变量</p>
      </div>
      
      <div v-else class="charts-container">
        <div
          v-for="variable in selectedVariables"
          :key="variable"
          class="chart-item"
        >
          <div class="chart-header">
            <span class="chart-title">{{ formatVariableName(variable) }}</span>
            <span class="chart-value">{{ chartValues[variable] || '-' }}</span>
          </div>
          <div
            :id="`chart-${variable}`"
            class="chart"
            :style="{ height: chartHeight }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, toRefs, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useDroneStore } from '@/store/drone'
import * as echarts from 'echarts'
 
const droneStore = useDroneStore()

// 确保 replayAnalysis 存在，否则使用默认值
const analysis = ref(droneStore.replayAnalysis || {
  categorizedVars: {},
  selectedVariables: [],
  loading: false,
  error: null,
  timeAxis: [],
  seriesData: {},
  allVariables: [],
  hasData: false
})

const status = ref(droneStore.replayStatus || {
  currentTime: 0,
  totalTime: 0
})

// 使用 toRefs 解构
const {
  timeAxis,
  seriesData,
  selectedVariables,
  loading,
  hasData,
  categorizedVars,
  allVariables
} = toRefs(analysis.value)

const { currentTime, totalTime } = toRefs(status.value)

// 监听 store 变化，同步到本地 ref
watch(() => droneStore.replayAnalysis, (newVal) => {
  if (newVal) {
    Object.assign(analysis.value, newVal)
  }
}, { deep: true })

watch(() => droneStore.replayStatus, (newVal) => {
  if (newVal) {
    Object.assign(status.value, newVal)
  }
}, { deep: true })
 
const chartHeight = ref('150px')
const chartInstances = ref({})
const chartValues = ref({})
const searchQuery = ref('')
const tempSelectedVariables = ref([])
const expandedCategories = ref({})
 
// 计算属性
const timeInfo = computed(() => {
  if (!hasData.value) return ''
  const current = formatTime(currentTime.value)
  const total = formatTime(totalTime.value)
  return `${current} / ${total}`
})

const filteredCategories = computed(() => {
  if (!categorizedVars.value) return {}
  const filtered = {}
  const query = searchQuery.value.toLowerCase()
  
  for (const [category, variables] of Object.entries(categorizedVars.value)) {
    const filteredVars = variables.filter(v =>
      v.toLowerCase().includes(query)
    )
    if (filteredVars.length > 0) {
      filtered[category] = filteredVars
    }
  }
  
  return filtered
})

const selectedCount = computed(() => {
  return tempSelectedVariables.value.length
})

// 方法
function formatTime(seconds) {
  if (!seconds || typeof seconds !== 'number') return '0:00'
  const min = Math.floor(seconds / 60)
  const sec = Math.floor(seconds % 60)
  return `${min}:${sec.toString().padStart(2, '0')}`
}

function formatVariableName(variable) {
  return variable.replace(/_/g, ' ')
}

function toggleCategory(category) {
  expandedCategories.value[category] = !expandedCategories.value[category]
}

// 变量选择方法
async function fetchHeaders() {
  await droneStore.fetchHeaders()
}

async function applySelection() {
  if (tempSelectedVariables.value.length === 0) {
    console.warn('请至少选择一个变量')
    return
  }
  
  await droneStore.fetchChartSeries(tempSelectedVariables.value)
}

function clearSelection() {
  tempSelectedVariables.value = []
}

function createChart(variable) {
  const chartRef = document.getElementById(`chart-${variable}`)
  if (!chartRef) return

  const chart = echarts.init(chartRef)
  chartInstances.value[variable] = chart

  const data = seriesData.value[variable] || []
  const option = {
    title: {
      show: false
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const time = params[0].value[0]
        const value = params[0].value[1]
        return `时间: ${formatTime(time)}<br/>数值: ${value.toFixed(4)}`
      }
    },
    grid: {
      left: '40px',
      right: '20px',
      top: '10px',
      bottom: '30px'
    },
    xAxis: {
      type: 'value',
      name: '时间(秒)',
      nameLocation: 'middle',
      nameGap: 20,
      min: 0,
      max: totalTime.value,
      axisLine: {
        lineStyle: { color: '#666' }
      },
      axisLabel: {
        color: '#999',
        formatter: (value) => formatTime(value)
      }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#999' },
      splitLine: {
        lineStyle: { color: '#333' }
      }
    },
    series: [
      {
        name: variable,
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: data.map((val, idx) => [timeAxis.value[idx], val]),
        lineStyle: {
          color: '#3274F6',
          width: 1.5
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(50, 116, 246, 0.3)' },
              { offset: 1, color: 'rgba(50, 116, 246, 0.05)' }
            ]
          }
        },
        markPoint: {
          data: [
            {
              name: '当前',
              xAxis: currentTime.value,
              yAxis: data[findClosestIndex(timeAxis.value, currentTime.value)] || 0,
              symbol: 'circle',
              symbolSize: 8,
              itemStyle: {
                color: '#ff6b6b',
                borderColor: '#fff',
                borderWidth: 2
              }
            }
          ],
          animation: false
        },
        markLine: {
          symbol: 'none',
          data: [
            { xAxis: currentTime.value }
          ],
          lineStyle: {
            color: '#ff6b6b',
            type: 'dashed',
            width: 2
          },
          label: {
            show: true,
            position: 'end',
            formatter: '当前',
            color: '#ff6b6b'
          },
          animation: false
        }
      }
    ]
  }

  chart.setOption(option)

  // 更新当前值
  updateChartValue(variable)
}

function findClosestIndex(arr, target) {
  if (!arr || arr.length === 0) return 0
  let closest = 0
  let minDiff = Math.abs(arr[0] - target)
  for (let i = 1; i < arr.length; i++) {
    const diff = Math.abs(arr[i] - target)
    if (diff < minDiff) {
      minDiff = diff
      closest = i
    }
  }
  return closest
}

function updateChartValue(variable) {
  const data = seriesData.value[variable] || []
  const timeData = timeAxis.value
  const idx = findClosestIndex(timeData, currentTime.value)
  chartValues.value[variable] = data[idx]?.toFixed(4) || '-'
}

function updateAllCharts() {
  for (const variable of selectedVariables.value) {
    const chart = chartInstances.value[variable]
    if (!chart) continue

    const data = seriesData.value[variable] || []
    const option = chart.getOption()

    // 更新 markPoint 和 markLine
    option.series[0].markPoint = {
      data: [
        {
          name: '当前',
          xAxis: currentTime.value,
          yAxis: data[findClosestIndex(timeAxis.value, currentTime.value)] || 0,
          symbol: 'circle',
          symbolSize: 8,
          itemStyle: {
            color: '#ff6b6b',
            borderColor: '#fff',
            borderWidth: 2
          }
        }
      ],
      animation: false
    }

    option.series[0].markLine = {
      symbol: 'none',
      data: [
        { xAxis: currentTime.value }
      ],
      lineStyle: {
        color: '#ff6b6b',
        type: 'dashed',
        width: 2
      },
      label: {
        show: true,
        position: 'end',
        formatter: '当前',
        color: '#ff6b6b'
      },
      animation: false
    }

    chart.setOption(option)
    updateChartValue(variable)
  }
}

function clearCharts() {
  for (const variable of Object.keys(chartInstances.value)) {
    const chart = chartInstances.value[variable]
    if (chart) {
      chart.dispose()
    }
  }
  chartInstances.value = {}
  chartValues.value = {}
}

function resizeCharts() {
  for (const chart of Object.values(chartInstances.value)) {
    if (chart) {
      chart.resize()
    }
  }
}

// 生命周期
onMounted(async () => {
  window.addEventListener('resize', resizeCharts)
  
  // 初始化时获取变量列表
  await droneStore.fetchHeaders()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  clearCharts()
})

// 监听数据变化
watch([timeAxis, seriesData], async () => {
  if (!hasData.value) return
  
  clearCharts()
  await nextTick()
  
  // 同步临时选择到实际选择
  tempSelectedVariables.value = [...selectedVariables.value]
  
  for (const variable of selectedVariables.value) {
    await nextTick()
    createChart(variable)
  }
}, { deep: true })

// 监听当前时间变化
watch(currentTime, () => {
  if (hasData.value) {
    updateAllCharts()
  }
})

// 监听选中变量变化（已移除，改为通过 applySelection 手动触发）
</script>

<style scoped>
/* 主面板 - 上下布局 */
.analysis-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #141414;
  color: #e0e0e0;
}

/* 上方变量选择区 */
.selector-section {
  display: flex;
  flex-direction: column;
  max-height: 40%;
  min-height: 200px;
  background: #1a1a1a;
  border-bottom: 2px solid #3274F6;
  overflow: hidden;
  padding: 0;
  flex-shrink: 0;
}

.selector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background: #252525;
  border-bottom: 1px solid #333;
  gap: 8px;
  flex-shrink: 0;
}

.selector-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #3274F6;
  flex: 1;
}

.selector-actions {
  display: flex;
  gap: 6px;
}

.refresh-variables-btn,
.apply-btn,
.clear-btn-small {
  padding: 6px 10px;
  border: 1px solid #3274F6;
  background: transparent;
  border-radius: 4px;
  color: #3274F6;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-variables-btn:hover:not(:disabled),
.apply-btn:hover:not(:disabled) {
  background: rgba(50, 116, 246, 0.2);
}

.refresh-variables-btn:disabled,
.apply-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.apply-btn {
  min-width: 100px;
  background: #3274F6;
  color: white;
}

.apply-btn:hover:not(:disabled) {
  background: #2563eb;
}

.clear-btn-small {
  padding: 6px 10px;
}

.clear-btn-small:hover {
  background: #dc3545;
  color: white;
  border-color: #dc3545;
}

/* 搜索框 */
.search-box {
  position: relative;
  margin-bottom: 10px;
  padding: 0 15px;
  padding-top: 10px;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  padding: 8px 30px 8px 10px;
  background: #252525;
  border: 1px solid #444;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 12px;
  outline: none;
  transition: border-color 0.2s ease;
}

.search-input:focus {
  border-color: #3274F6;
}

.search-icon {
  position: absolute;
  right: 25px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  opacity: 0.5;
}

/* 变量分类容器 */
.categories-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.categories-container::-webkit-scrollbar {
  width: 6px;
}

.categories-container::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 3px;
}

.category-group {
  margin-bottom: 8px;
  border: 1px solid #333;
  border-radius: 4px;
  background: #1f1f1f;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: #252525;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
}

.category-header:hover {
  background: #2a2a2a;
}

.category-icon {
  font-size: 10px;
  color: #888;
  transition: transform 0.2s ease;
}

.category-name {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  color: #e0e0e0;
}

.category-count {
  font-size: 11px;
  color: #888;
  padding: 2px 6px;
  background: #333;
  border-radius: 10px;
}

.category-content {
  padding: 10px;
  border-top: 1px solid #333;
}

.variable-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  transition: background 0.15s ease;
}

.variable-checkbox:hover {
  background: rgba(50, 116, 246, 0.1);
}

.variable-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: #3274F6;
}

.variable-text {
  font-size: 11px;
  color: #bbb;
  word-break: break-all;
}

/* 下方图表区 */
.charts-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  background: #141414;
  overflow: hidden;
}

.charts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #1a1a1a;
  border-bottom: 1px solid #333;
  gap: 15px;
  flex-shrink: 0;
}

.charts-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #3274F6;
}

.charts-container {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  padding-bottom: 30px;
  background: #141414;
}

.charts-container::-webkit-scrollbar {
  width: 6px;
}

.charts-container::-webkit-scrollbar-thumb {
  background: #444;
  border-radius: 3px;
}

.charts-container::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 图表卡片 */
.chart-item {
  margin-bottom: 12px;
  background: #1f1f1f;
  border-radius: 6px;
  padding: 12px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #333;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #3274F6;
}

.chart-value {
  font-size: 14px;
  font-weight: bold;
  color: #ff6b6b;
}

.chart {
  width: 100%;
  min-height: 150px;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #666;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 14px;
  opacity: 0.7;
}

/* 通用样式 */
.time-info {
  font-size: 12px;
  color: #888;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>