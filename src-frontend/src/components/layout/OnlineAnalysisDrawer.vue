<template>
  <section class="online-drawer">
    <div class="drawer-header">
      <div>
        <div class="drawer-kicker">Live Evaluation Matrix</div>
        <div class="drawer-title">在线评测总览</div>
        <div class="drawer-subtitle">五域得分趋势 + 域内关键指标</div>
      </div>
      <div class="drawer-actions">
        <div class="status-badge" :class="badgeClass">{{ badgeText }}</div>
        <button v-if="closable" class="close-btn" type="button" @click="$emit('close')">关闭</button>
      </div>
    </div>

    <div class="hero-shell">
      <div>
        <div class="hero-title">评测主曲线</div>
        <div class="hero-text">先看综合分与五域得分是否同向，再看下方域内指标是哪一项在拖分。</div>
      </div>
      <div class="hero-meta">
        <span>{{ compositeText }}</span>
        <span>{{ evidenceText }}</span>
      </div>
    </div>

    <div class="trend-panel">
      <EChartWrapper
        title="综合分与五域曲线"
        unit="score"
        :series="scoreTrendSeries"
        :showLegend="true"
        :height="250"
        :optionOverrides="scoreTrendOverrides"
      />
    </div>

    <div class="score-grid">
      <div class="score-card highlight-card">
        <span class="score-name">综合分</span>
        <strong class="score-value">{{ compositeText }}</strong>
      </div>
      <div v-for="item in domainItems" :key="item.key" class="score-card">
        <span class="score-name">{{ item.label }}</span>
        <strong class="score-value">{{ item.value }}</strong>
      </div>
    </div>

    <div class="domain-grid">
      <section v-for="panel in domainPanels" :key="panel.key" class="domain-panel">
        <div class="domain-header">
          <div>
            <div class="domain-title">{{ panel.title }}</div>
            <div class="domain-subtitle">{{ panel.subtitle }}</div>
          </div>
          <div class="domain-score">{{ panel.scoreText }}</div>
        </div>

        <div class="domain-chart-shell">
          <EChartWrapper
            title=" "
            :unit="panel.unit"
            :series="panel.series"
            :showLegend="true"
            :height="160"
            :optionOverrides="panel.optionOverrides"
          />
        </div>

        <div class="metric-chip-grid">
          <div v-for="metric in panel.metrics" :key="metric.label" class="metric-chip">
            <span class="metric-chip-label">{{ metric.label }}</span>
            <strong class="metric-chip-value">{{ metric.value }}</strong>
          </div>
        </div>
      </section>
    </div>

    <div class="footer-row">
      <span>通道: {{ channelText }}</span>
      <span v-if="missingText">缺失: {{ missingText }}</span>
      <span>最近刷新: {{ lastUpdatedText }}</span>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EChartWrapper from '@/components/monitor/EChartWrapper.vue'
import { useDroneStore } from '@/store/drone'

defineEmits(['close'])

defineProps({
  closable: {
    type: Boolean,
    default: false
  }
})

const droneStore = useDroneStore()

const online = computed(() => droneStore.onlineAnalysis)

const badgeText = computed(() => {
  if (!online.value.enabled) return '未启用'
  if (online.value.ready) return '已就绪'
  return '等待数据'
})

const badgeClass = computed(() => ({
  ready: online.value.ready,
  waiting: online.value.enabled && !online.value.ready,
  disabled: !online.value.enabled
}))

const compositeText = computed(() => formatScore(online.value.compositeScore))
const evidenceText = computed(() => (online.value.strictMeasuredReady ? '实测链路' : '代理链路'))

const domainItems = computed(() => [
  { key: 'perception', label: '感知', value: formatScore(online.value.domainScores.perception) },
  { key: 'decision', label: '决策', value: formatScore(online.value.domainScores.decision) },
  { key: 'control', label: '控制', value: formatScore(online.value.domainScores.control) },
  { key: 'communication', label: '通信', value: formatScore(online.value.domainScores.communication) },
  { key: 'safety', label: '安全', value: formatScore(online.value.domainScores.safety) }
])

const channelText = computed(() => {
  const channels = online.value.availableChannels || []
  return channels.length ? channels.join(' / ') : '暂无'
})

const missingText = computed(() => {
  const missing = online.value.missingRequiredChannels || []
  return missing.length ? missing.join(' / ') : ''
})

const lastUpdatedText = computed(() => {
  if (!online.value.lastUpdated) return '--'
  return new Date(online.value.lastUpdated).toLocaleTimeString('zh-CN', { hour12: false })
})

const trimTimedSeries = (entries = [], limit = 180, factor = 1) => (entries || []).slice(-limit).map((item) => [item.timestamp, Number(item.value) * factor])

const padTime = (value) => String(value).padStart(2, '0')
const formatTimeTick = (value) => {
  const date = new Date(Number(value))
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return `${padTime(date.getMinutes())}:${padTime(date.getSeconds())}`
}

const scoreTrendSeries = computed(() => [
  makeSeries('综合分', online.value.history.composite, '#f8fafc', 2.8),
  makeSeries('感知', online.value.history.perception, '#38bdf8', 2),
  makeSeries('决策', online.value.history.decision, '#f59e0b', 2),
  makeSeries('控制', online.value.history.control, '#22c55e', 2),
  makeSeries('通信', online.value.history.communication, '#a78bfa', 2),
  makeSeries('安全', online.value.history.safety, '#f472b6', 2)
])

const domainPanels = computed(() => {
  const metrics = online.value.metrics || {}
  const history = online.value.metricHistory || {}
  return [
    {
      key: 'perception',
      title: '感知域',
      subtitle: '时延、负载、资源余量',
      unit: 'mixed metrics',
      scoreText: formatScore(online.value.domainScores.perception),
      series: [
        makeMetricSeries('时延', history.perceptionLatencyMs, '#38bdf8', 0),
        makeMetricSeries('CPU负载', history.perceptionCpuLoad, '#f97316', 1, 100),
        makeMetricSeries('资源余量', history.resourceMargin, '#22c55e', 2, 100)
      ],
      optionOverrides: buildMetricChartOverrides([
        buildMetricAxis('时延', history.perceptionLatencyMs, '#38bdf8', 'ms'),
        buildMetricAxis('CPU负载', history.perceptionCpuLoad, '#f97316', '%', 100),
        buildMetricAxis('资源余量', history.resourceMargin, '#22c55e', '%', 100)
      ]),
      metrics: [
        { label: '时延', value: formatMetric(metrics.perceptionLatencyMs, 'ms') },
        { label: 'CPU负载', value: formatPercent(metrics.perceptionCpuLoad) },
        { label: '资源余量', value: formatPercent(metrics.resourceMargin) }
      ]
    },
    {
      key: 'decision',
      title: '决策域',
      subtitle: '规划耗时、跟踪误差、任务可靠度',
      unit: 'mixed metrics',
      scoreText: formatScore(online.value.domainScores.decision),
      series: [
        makeMetricSeries('规划耗时', history.planningTimeMs, '#f59e0b', 0),
        makeMetricSeries('跟踪RMSE', history.trackingRmseM, '#38bdf8', 1),
        makeMetricSeries('任务可靠度', history.missionReliability, '#22c55e', 2, 100)
      ],
      optionOverrides: buildMetricChartOverrides([
        buildMetricAxis('规划耗时', history.planningTimeMs, '#f59e0b', 'ms'),
        buildMetricAxis('跟踪RMSE', history.trackingRmseM, '#38bdf8', 'm'),
        buildMetricAxis('任务可靠度', history.missionReliability, '#22c55e', '%', 100)
      ]),
      metrics: [
        { label: '规划耗时', value: formatMetric(metrics.planningTimeMs, 'ms') },
        { label: '跟踪RMSE', value: formatMetric(metrics.trackingRmseM, 'm') },
        { label: '任务可靠度', value: formatPercent(metrics.missionReliability) }
      ]
    },
    {
      key: 'control',
      title: '控制域',
      subtitle: '抖动、姿态超调、电机响应',
      unit: 'mixed metrics',
      scoreText: formatScore(online.value.domainScores.control),
      series: [
        makeMetricSeries('控制抖动', history.controlJitterMs, '#22c55e', 0),
        makeMetricSeries('姿态超调', history.attitudeOvershootPct, '#f97316', 1),
        makeMetricSeries('电机响应', history.motorResponseMs, '#38bdf8', 2)
      ],
      optionOverrides: buildMetricChartOverrides([
        buildMetricAxis('控制抖动', history.controlJitterMs, '#22c55e', 'ms'),
        buildMetricAxis('姿态超调', history.attitudeOvershootPct, '#f97316', '%'),
        buildMetricAxis('电机响应', history.motorResponseMs, '#38bdf8', 'ms')
      ]),
      metrics: [
        { label: '控制抖动', value: formatMetric(metrics.controlJitterMs, 'ms') },
        { label: '姿态超调', value: formatMetric(metrics.attitudeOvershootPct, '%') },
        { label: '电机响应', value: formatMetric(metrics.motorResponseMs, 'ms') }
      ]
    },
    {
      key: 'communication',
      title: '通信域',
      subtitle: '下行丢包、总线带宽、跨链路时延',
      unit: 'mixed metrics',
      scoreText: formatScore(online.value.domainScores.communication),
      series: [
        makeMetricSeries('下行丢包', history.downlinkLossRate, '#f43f5e', 0, 100),
        makeMetricSeries('总线带宽', history.busBandwidthUtil, '#a78bfa', 1, 100),
        makeMetricSeries('跨链路时延', history.crossLatencyMs, '#38bdf8', 2)
      ],
      optionOverrides: buildMetricChartOverrides([
        buildMetricAxis('下行丢包', history.downlinkLossRate, '#f43f5e', '%', 100),
        buildMetricAxis('总线带宽', history.busBandwidthUtil, '#a78bfa', '%', 100),
        buildMetricAxis('跨链路时延', history.crossLatencyMs, '#38bdf8', 'ms')
      ]),
      metrics: [
        { label: '下行丢包', value: formatPercent(metrics.downlinkLossRate) },
        { label: '总线带宽', value: formatPercent(metrics.busBandwidthUtil) },
        { label: '跨链路时延', value: formatMetric(metrics.crossLatencyMs, 'ms') }
      ]
    },
    {
      key: 'safety',
      title: '安全域',
      subtitle: '障碍数量、避障触发、系统功耗',
      unit: 'mixed metrics',
      scoreText: formatScore(online.value.domainScores.safety),
      series: [
        makeMetricSeries('障碍数量', history.obstacleCount, '#f472b6', 0),
        makeMetricSeries('避障触发', history.avoidTriggerCount, '#f59e0b', 1),
        makeMetricSeries('系统功耗', history.systemPowerW, '#22c55e', 2)
      ],
      optionOverrides: buildMetricChartOverrides([
        buildMetricAxis('障碍数量', history.obstacleCount, '#f472b6', ''),
        buildMetricAxis('避障触发', history.avoidTriggerCount, '#f59e0b', ''),
        buildMetricAxis('系统功耗', history.systemPowerW, '#22c55e', 'W')
      ]),
      metrics: [
        { label: '障碍数量', value: formatMetric(metrics.obstacleCount, '') },
        { label: '避障触发', value: formatMetric(metrics.avoidTriggerCount, '') },
        { label: '系统功耗', value: formatMetric(metrics.systemPowerW, 'W') }
      ]
    }
  ]
})

const sharedGrid = {
  left: 40,
  right: 22,
  top: 36,
  bottom: 28
}

const scoreTrendOverrides = {
  backgroundColor: 'transparent',
  grid: sharedGrid,
  legend: {
    top: 4,
    textStyle: {
      color: '#cbd5e1',
      fontSize: 11
    }
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.94)',
    borderColor: 'rgba(148, 163, 184, 0.28)',
    textStyle: {
      color: '#e2e8f0'
    }
  },
  xAxis: {
    type: 'time',
    axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.5)' } },
    axisLabel: { color: '#94a3b8', formatter: formatTimeTick },
    splitLine: { lineStyle: { color: 'rgba(51, 65, 85, 0.5)', type: 'dashed' } }
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 100,
    axisLine: { lineStyle: { color: 'rgba(96, 165, 250, 0.58)' } },
    axisLabel: { color: '#93c5fd' },
    splitLine: { lineStyle: { color: 'rgba(51, 65, 85, 0.45)', type: 'dashed' } }
  }
}

function makeSeries(name, source, color, width = 2, factor = 1) {
  return {
    name,
    data: trimTimedSeries(source, 180, factor),
    smooth: true,
    symbol: 'none',
    lineStyle: { color, width },
    itemStyle: { color },
    areaStyle: name === '综合分' ? { color: 'rgba(248, 250, 252, 0.06)' } : undefined
  }
}

function makeMetricSeries(name, source, color, yAxisIndex = 0, factor = 1) {
  return {
    name,
    yAxisIndex,
    data: trimTimedSeries(source, 180, factor),
    smooth: true,
    symbol: 'none',
    lineStyle: { color, width: 2.1 },
    itemStyle: { color },
    emphasis: { focus: 'series' }
  }
}

function buildMetricAxis(name, source, color, unit = '', factor = 1) {
  return {
    name,
    source,
    color,
    unit,
    factor,
    bounds: computeMetricBounds(source, factor)
  }
}

function buildMetricChartOverrides(axes) {
  return {
    backgroundColor: 'transparent',
    grid: sharedGrid,
    legend: {
      top: 4,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        color: '#94a3b8',
        fontSize: 10
      }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: 'rgba(148, 163, 184, 0.28)',
      textStyle: {
        color: '#e2e8f0'
      },
      formatter: (params = []) => formatMetricTooltip(params, axes)
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.38)' } },
      axisLabel: { color: '#64748b', formatter: formatTimeTick },
      splitLine: { lineStyle: { color: 'rgba(30, 41, 59, 0.55)', type: 'dashed' } }
    },
    yAxis: axes.map((axis, index) => ({
      type: 'value',
      min: axis.bounds.min,
      max: axis.bounds.max,
      scale: true,
      position: index === 0 ? 'left' : 'right',
      offset: index > 1 ? 32 : 0,
      show: false,
      axisLine: { lineStyle: { color: hexToRgba(axis.color, 0.55) } },
      axisLabel: { color: '#93c5fd' },
      splitLine: index === 0 ? { lineStyle: { color: 'rgba(30, 41, 59, 0.48)', type: 'dashed' } } : { show: false }
    }))
  }
}

function computeMetricBounds(source = [], factor = 1) {
  const values = (source || [])
    .slice(-60)
    .map((item) => Number(item?.value) * factor)
    .filter((value) => Number.isFinite(value))

  if (!values.length) {
    return { min: 0, max: 10 }
  }

  let minValue = Math.min(...values)
  let maxValue = Math.max(...values)

  if (minValue === maxValue) {
    const padding = Math.max(Math.abs(minValue) * 0.15, 1)
    minValue -= padding
    maxValue += padding
  }

  const spread = maxValue - minValue
  const padding = Math.max(spread * 0.25, 0.5)
  let focusedMin = minValue - padding
  let focusedMax = maxValue + padding

  if (focusedMax - focusedMin < 2) {
    const center = (focusedMin + focusedMax) / 2
    focusedMin = center - 1
    focusedMax = center + 1
  }

  if (focusedMin === focusedMax) {
    focusedMax = focusedMin + 1
  }

  return {
    min: Number(focusedMin.toFixed(3)),
    max: Number(focusedMax.toFixed(3))
  }
}

function formatMetricTooltip(params = [], axes = []) {
  if (!Array.isArray(params) || !params.length) {
    return ''
  }

  const timestamp = params[0]?.value?.[0]
  const header = timestamp ? `<div style="margin-bottom:4px;">${formatTooltipTime(timestamp)}</div>` : ''
  const lines = params.map((item) => {
    const axisMeta = axes[item.seriesIndex] || {}
    const rawValue = Array.isArray(item.value) ? item.value[1] : item.value
    const unit = axisMeta.unit || ''
    const valueText = formatTooltipMetric(rawValue, unit)
    return `<div><span style="display:inline-block;margin-right:6px;border-radius:50%;width:8px;height:8px;background:${item.color};"></span>${item.seriesName}: ${valueText}</div>`
  })
  return `${header}${lines.join('')}`
}

function formatTooltipTime(value) {
  const date = new Date(Number(value))
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return `${padTime(date.getHours())}:${padTime(date.getMinutes())}:${padTime(date.getSeconds())}`
}

function formatTooltipMetric(value, unit = '') {
  if (!Number.isFinite(Number(value))) {
    return '--'
  }
  const numeric = Number(value)
  const text = Math.abs(numeric) >= 100 ? numeric.toFixed(0) : numeric.toFixed(2)
  return unit ? `${text}${unit}` : text
}

function hexToRgba(hex, alpha) {
  const normalized = String(hex || '').replace('#', '')
  if (normalized.length !== 6) {
    return `rgba(148, 163, 184, ${alpha})`
  }

  const red = Number.parseInt(normalized.slice(0, 2), 16)
  const green = Number.parseInt(normalized.slice(2, 4), 16)
  const blue = Number.parseInt(normalized.slice(4, 6), 16)

  if (![red, green, blue].every(Number.isFinite)) {
    return `rgba(148, 163, 184, ${alpha})`
  }

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
}

function formatScore(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : '--'
}

function formatMetric(value, unit = '') {
  if (!Number.isFinite(Number(value))) return '--'
  const numeric = Number(value)
  const text = Math.abs(numeric) >= 100 ? numeric.toFixed(0) : numeric.toFixed(2)
  return unit ? `${text}${unit}` : text
}

function formatPercent(value) {
  if (!Number.isFinite(Number(value))) return '--'
  return `${(Number(value) * 100).toFixed(1)}%`
}
</script>

<style scoped>
.online-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.08), transparent 28%),
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.12), transparent 24%),
    linear-gradient(180deg, rgba(5, 10, 24, 0.99) 0%, rgba(14, 23, 43, 0.98) 100%);
  border: 1px solid rgba(76, 119, 164, 0.28);
  box-shadow: 0 28px 60px rgba(2, 6, 23, 0.42);
}

.drawer-header,
.hero-shell,
.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.drawer-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  color: #93c5fd;
}

.drawer-title {
  margin-top: 3px;
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
}

.drawer-subtitle,
.hero-text,
.footer-row {
  font-size: 12px;
  color: #8ea3bf;
}

.drawer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-badge {
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.status-badge.ready {
  background: rgba(22, 163, 74, 0.12);
  color: #4ade80;
}

.status-badge.waiting {
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
}

.status-badge.disabled {
  background: rgba(148, 163, 184, 0.18);
  color: #cbd5e1;
}

.close-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(122, 146, 173, 0.28);
  background: rgba(10, 18, 34, 0.76);
  color: #e2e8f0;
  cursor: pointer;
}

.close-btn:hover {
  background: rgba(18, 30, 52, 0.9);
}

.hero-shell,
.trend-panel,
.domain-panel,
.score-card {
  border: 1px solid rgba(76, 113, 152, 0.2);
  background: linear-gradient(180deg, rgba(14, 23, 40, 0.78) 0%, rgba(10, 18, 33, 0.9) 100%);
  border-radius: 14px;
}

.hero-shell {
  padding: 14px 16px;
}

.hero-title {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
}

.hero-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  font-weight: 700;
  color: #dbeafe;
}

.trend-panel {
  padding: 10px;
  background: linear-gradient(180deg, rgba(9, 17, 33, 0.94) 0%, rgba(6, 12, 24, 0.98) 100%);
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.04);
}

.trend-panel :deep(.e-chart-wrapper),
.domain-chart-shell :deep(.e-chart-wrapper) {
  margin-bottom: 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(12, 22, 40, 0.96) 0%, rgba(8, 15, 28, 0.98) 100%);
  border: 1px solid rgba(78, 112, 148, 0.2);
}

.trend-panel :deep(.chart-header),
.domain-chart-shell :deep(.chart-header) {
  padding: 10px 12px 8px;
  border-bottom-color: rgba(71, 85, 105, 0.35);
}

.domain-chart-shell :deep(.chart-header) {
  display: none;
}

.domain-chart-shell :deep(.e-chart-wrapper) {
  padding-top: 8px;
}

.trend-panel :deep(.chart-title),
.domain-chart-shell :deep(.chart-title) {
  color: #f8fafc;
}

.trend-panel :deep(.chart-unit),
.domain-chart-shell :deep(.chart-unit) {
  color: #7f95b3;
}

.trend-panel :deep(.chart-container),
.domain-chart-shell :deep(.chart-container) {
  border-radius: 10px;
}

.score-grid,
.domain-grid,
.metric-chip-grid {
  display: grid;
  gap: 10px;
}

.score-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.score-card {
  padding: 12px;
}

.highlight-card {
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.24) 0%, rgba(13, 24, 46, 0.92) 100%);
}

.score-name {
  display: block;
  font-size: 11px;
  color: #87a0bd;
}

.score-value {
  display: block;
  margin-top: 6px;
  font-size: 26px;
  font-weight: 700;
  color: #f8fafc;
}

.domain-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.domain-panel {
  padding: 12px;
}

.domain-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.domain-title {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
}

.domain-subtitle {
  margin-top: 3px;
  font-size: 11px;
  color: #90a6c2;
}

.domain-score {
  font-size: 22px;
  font-weight: 700;
  color: #dbeafe;
}

.domain-chart-shell {
  margin-top: 8px;
  border-radius: 12px;
  background: transparent;
}

.metric-chip-grid {
  margin-top: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-chip {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(78, 112, 148, 0.18);
  background: linear-gradient(180deg, rgba(8, 15, 28, 0.78) 0%, rgba(6, 12, 24, 0.92) 100%);
}

.metric-chip-label {
  display: block;
  font-size: 11px;
  color: #87a0bd;
}

.metric-chip-value {
  display: block;
  margin-top: 4px;
  color: #f8fafc;
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', monospace;
}

@media (max-width: 1100px) {
  .score-grid,
  .domain-grid,
  .metric-chip-grid {
    grid-template-columns: 1fr;
  }

  .drawer-header,
  .hero-shell,
  .footer-row,
  .domain-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-meta {
    align-items: flex-start;
  }
}
</style>