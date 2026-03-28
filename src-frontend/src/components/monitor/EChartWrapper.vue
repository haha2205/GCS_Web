<template>
  <div class="e-chart-wrapper">
    <div class="chart-header">
      <span class="chart-title">{{ title }}</span>
      <span v-if="unit" class="chart-unit">单位: {{ unit }}</span>
    </div>
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, TooltipComponent, LegendComponent, RadarComponent } from 'echarts/components'
import { LineChart, BarChart, RadarChart } from 'echarts/charts'

echarts.use([
  CanvasRenderer,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  RadarComponent,
  LineChart,
  BarChart,
  RadarChart
])

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  series: {
    type: Array,
    required: true,
    default: () => []
  },
  unit: {
    type: String,
    default: ''
  },
  chartType: {
    type: String,
    default: 'line'
  },
  categories: {
    type: Array,
    default: () => []
  },
  radarIndicator: {
    type: Array,
    default: () => []
  },
  height: {
    type: Number,
    default: 150
  },
  yMin: Number,
  yMax: Number,
  boundaryGap: {
    type: Boolean,
    default: undefined
  },
  showLegend: {
    type: Boolean,
    default: false
  },
  optionOverrides: {
    type: Object,
    default: () => ({})
  }
})

const chartRef = ref(null)
let chartInstance = null
let resizeObserver = null

function applyContainerSize() {
  if (!chartRef.value) {
    return
  }

  const chartHeight = `${props.height}px`
  chartRef.value.style.width = '100%'
  chartRef.value.style.height = chartHeight
  chartRef.value.style.minWidth = '100px'
  chartRef.value.style.minHeight = chartHeight
}

function getXAxisData() {
  const firstSeriesData = props.series[0]?.data || []
  if (props.categories.length > 0) {
    return props.categories
  }
  if (firstSeriesData.length > 0) {
    return firstSeriesData.map((_, index) => index)
  }
  return [0]
}

function getRadarIndicator() {
  if (props.radarIndicator.length > 0) {
    return props.radarIndicator
  }
  return getXAxisData().map((name) => ({ name, max: 100 }))
}

function isTimedPoint(point) {
  return Array.isArray(point)
    && point.length >= 2
    && Number.isFinite(Number(point[0]))
    && Number.isFinite(Number(point[1]))
}

function hasTimedSeries() {
  return props.series.some((item) => Array.isArray(item?.data) && item.data.some(isTimedPoint))
}

function buildCartesianOption() {
  const isBar = props.chartType === 'bar'
  const useTimeAxis = props.chartType === 'line' && hasTimedSeries()
  return {
    grid: {
      left: 40,
      right: 20,
      top: 30,
      bottom: 30
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#cbd5e1',
      borderWidth: 1,
      textStyle: {
        color: '#0f172a'
      }
    },
    legend: {
      show: props.showLegend,
      top: 0,
      textStyle: {
        color: '#475569',
        fontSize: 11
      }
    },
    xAxis: {
      type: useTimeAxis ? 'time' : 'category',
      data: useTimeAxis ? undefined : getXAxisData(),
      boundaryGap: props.boundaryGap ?? isBar,
      axisLine: {
        lineStyle: {
          color: '#94a3b8'
        }
      },
      axisLabel: {
        color: '#475569'
      }
    },
    yAxis: {
      type: 'value',
      min: props.yMin,
      max: props.yMax,
      axisLine: {
        lineStyle: {
          color: '#94a3b8'
        }
      },
      axisLabel: {
        color: '#475569'
      },
      splitLine: {
        lineStyle: {
          color: '#dbe4ef',
          type: 'dashed'
        }
      }
    },
    series: props.series.map((item) => ({
      ...item,
      type: props.chartType,
      symbol: props.chartType === 'line' ? (item.symbol ?? 'none') : item.symbol,
      lineStyle: props.chartType === 'line'
        ? { width: 2, ...(item.lineStyle || {}) }
        : item.lineStyle,
      barMaxWidth: props.chartType === 'bar' ? (item.barMaxWidth || 28) : item.barMaxWidth
    }))
  }
}

function buildRadarOption() {
  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#cbd5e1',
      borderWidth: 1,
      textStyle: {
        color: '#0f172a'
      }
    },
    legend: {
      show: props.showLegend || props.series.length > 1,
      top: 0,
      textStyle: {
        color: '#475569',
        fontSize: 11
      }
    },
    radar: {
      radius: '64%',
      indicator: getRadarIndicator(),
      axisName: {
        color: '#475569',
        fontSize: 11
      },
      splitLine: {
        lineStyle: {
          color: '#dbe4ef'
        }
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(37, 99, 235, 0.03)', 'rgba(37, 99, 235, 0.06)']
        }
      },
      axisLine: {
        lineStyle: {
          color: '#cbd5e1'
        }
      }
    },
    series: props.series.map((item) => ({
      type: 'radar',
      ...item,
      data: [
        {
          value: item.data || [],
          name: item.name,
          areaStyle: item.areaStyle,
          lineStyle: item.lineStyle,
          itemStyle: item.itemStyle,
          symbol: item.symbol
        }
      ]
    }))
  }
}

function getOption() {
  const baseOption = props.chartType === 'radar'
    ? buildRadarOption()
    : buildCartesianOption()

  return {
    ...baseOption,
    ...props.optionOverrides
  }
}

function updateChart() {
  if (!chartInstance || !Array.isArray(props.series) || props.series.length === 0) {
    return
  }

  chartInstance.setOption(getOption(), true)
}

function initChart() {
  if (!chartRef.value) {
    return
  }

  if (chartInstance) {
    chartInstance.dispose()
  }

  applyContainerSize()
  chartInstance = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  updateChart()
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

watch(
  () => [props.series, props.categories, props.radarIndicator, props.chartType, props.height, props.yMin, props.yMax, props.showLegend, props.optionOverrides],
  () => {
    nextTick(() => {
      applyContainerSize()
      if (!chartInstance) {
        initChart()
        return
      }
      chartInstance.resize()
      updateChart()
    })
  },
  { deep: true }
)

onMounted(() => {
  nextTick(() => {
    applyContainerSize()
    initChart()

    if (chartRef.value) {
      resizeObserver = new ResizeObserver(() => {
        handleResize()
      })
      resizeObserver.observe(chartRef.value)
    }
  })

  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.e-chart-wrapper {
  width: 100%;
  padding: 10px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-soft);
  flex-shrink: 0;
}

.chart-title {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.chart-unit {
  color: var(--text-secondary);
  font-size: 11px;
}

.chart-container {
  width: 100%;
  height: 150px;
  min-height: 150px;
  min-width: 100px;
  position: relative;
}
</style>
