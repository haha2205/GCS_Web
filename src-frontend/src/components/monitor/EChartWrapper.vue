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
import { GridComponent, TooltipComponent } from 'echarts/components'
import { LineChart } from 'echarts/charts'

// 注册必要组件
echarts.use([CanvasRenderer, GridComponent, TooltipComponent, LineChart])

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
  yMin: Number,
  yMax: Number
})

const chartRef = ref(null)
let chartInstance = null

const initChart = () => {
  if (!chartRef.value) {
    console.warn('[EChartWrapper] 容器引用不存在')
    return
  }
  
  // 先销毁旧实例
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  
  // 强制设置容器尺寸（确保ECharts有渲染空间）
  chartRef.value.style.width = '100%'
  chartRef.value.style.height = '150px'
  chartRef.value.style.minWidth = '100px'
  chartRef.value.style.minHeight = '150px'
  chartRef.value.style.display = 'block'
  chartRef.value.style.position = 'relative'
  chartRef.value.style.visibility = 'visible'
  
  // 检查容器尺寸
  const rect = chartRef.value.getBoundingClientRect()
  console.log('[EChartWrapper] 容器尺寸（强制设置后）:', rect, '数据长度:', props.series.length)
  
  // 强制初始化ECharts，不管容器尺寸如何
  try {
    chartInstance = echarts.init(chartRef.value, {
      renderer: 'canvas'
    })
    console.log('[EChartWrapper] ECharts实例创建成功')
    // 延迟更新图表，等待DOM完成
    setTimeout(() => {
      updateChart()
      // 设置图表尺寸
      if (chartInstance && rect.width > 0 && rect.height > 0) {
        chartInstance.resize()
      }
    }, 50)
  } catch (error) {
    console.error('[EChartWrapper] 初始化失败', error)
  }
}

const updateChart = () => {
  if (!chartInstance) {
    console.warn('[EChartWrapper] chartInstance不存在，无法更新')
    return
  }
  
  if (!props.series || !Array.isArray(props.series) || props.series.length === 0) {
    console.warn('[EChartWrapper] series为空，跳过更新')
    return
  }
  
  console.log('[EChartWrapper] 更新图表，series:', props.series.map(s => ({ name: s.name, dataLen: s.data?.length || 0 })))
  
  // 生成x轴数据：根据第一个series的数据长度生成索引
  const firstSeriesData = props.series[0]?.data || []
  const xAxisData = firstSeriesData.length > 0
    ? firstSeriesData.map((_, i) => i)
    : [0] // 确保至少有一个x轴点
  
  const option = {
    grid: {
      left: 40,
      right: 20,
      top: 30,
      bottom: 30
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(20, 20, 20, 0.9)',
      borderColor: '#333',
      borderWidth: 1,
      textStyle: {
        color: '#fff'
      }
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      boundaryGap: false,
      axisLine: {
        lineStyle: {
          color: '#444'
        }
      },
      axisLabel: {
        color: '#888'
      }
    },
    yAxis: {
      type: 'value',
      min: props.yMin,
      max: props.yMax,
      axisLine: {
        lineStyle: {
          color: '#444'
        }
      },
      axisLabel: {
        color: '#888'
      },
      splitLine: {
        lineStyle: {
          color: '#333',
          type: 'dashed'
        }
      }
    },
    series: props.series.map(s => ({
      ...s,
      type: 'line',
      symbol: 'none',
      lineStyle: {
        width: 2
      }
    }))
  }
  
  try {
    chartInstance.setOption(option, true)
    console.log('[EChartWrapper] 图表更新成功')
  } catch (error) {
    console.error('[EChartWrapper] 图表更新失败', error)
  }
}

// 监听 series 变化
watch(() => props.series, (newSeries) => {
  if (newSeries && Array.isArray(newSeries) && newSeries.length > 0) {
    console.log('[EChartWrapper] series变化，准备更新图表，系列数量:', newSeries.length)
    nextTick(() => {
      if (!chartInstance) {
        console.log('[EChartWrapper] chartInstance不存在，尝试初始化')
        initChart()
      } else {
        updateChart()
      }
    })
  }
}, { deep: true })

let resizeObserver = null

onMounted(() => {
  console.log('[EChartWrapper] onMounted, props.series:', props.series?.map(s => ({ name: s.name, dataLen: s.data?.length || 0 })))
  
  // 使用 ResizeObserver 监听容器尺寸变化
  resizeObserver = new ResizeObserver((entries) => {
    for (let entry of entries) {
      const { width, height } = entry.contentRect
      console.log('[EChartWrapper] 容器尺寸变化:', { width, height })
      if (width > 0 && height > 0 && !chartInstance) {
        console.log('[EChartWrapper] 容器尺寸有效，初始化图表')
        initChart()
      } else if (chartInstance) {
        chartInstance.resize()
      } else {
        // 如果图表未初始化且尺寸有效，尝试初始化
        if (width > 0 && height > 0) {
          console.log('[EChartWrapper] ResizeObserver检测到有效尺寸，初始化图表')
          initChart()
        }
      }
    }
  })
  
  // 初始化时检查容器
  nextTick(() => {
    if (chartRef.value) {
      resizeObserver.observe(chartRef.value)
      
      // 强制设置容器高度（防止v-show导致尺寸为0）
      chartRef.value.style.height = '150px'
      chartRef.value.style.minHeight = '150px'
      
      // 激进的策略：不管容器尺寸如何，都尝试初始化
      // ECharts可以处理尺寸为0的情况，会在尺寸有效时自动渲染
      setTimeout(() => {
        if (!chartInstance && chartRef.value) {
          const rect = chartRef.value.getBoundingClientRect()
          console.log('[EChartWrapper] 延迟后容器尺寸:', rect)
          
          if (rect.width > 0 && rect.height > 0) {
            console.log('[EChartWrapper] 容器尺寸有效，初始化图表')
            initChart()
          } else {
            console.warn('[EChartWrapper] 容器尺寸仍为0，但强制初始化（ECharts会自己处理）')
            // 强制初始化，ECharts会等待容器尺寸有效
            initChart()
          }
        }
      }, 100)
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

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}
</script>

<style scoped>
.e-chart-wrapper {
  width: 100%;
  padding: 10px;
  background: rgba(30, 30, 30, 0.5);
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
  border-bottom: 1px solid #444;
  flex-shrink: 0;
}
 
.chart-title {
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
}
 
.chart-unit {
  color: #888;
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