<template>
  <div class="monitor-tabs-panel">
    <div class="monitor-content" :class="monitorContentClass">
      <section v-if="showControlPanel" class="monitor-column">
        <div class="column-header">
          <div class="column-title">控制状态</div>
        </div>

        <div class="column-scroll">
          <div class="monitor-section state-section">
            <div class="state-columns">
              <div class="state-column" v-for="(column, columnIndex) in stateColumns" :key="columnIndex">
                <div class="metric-card" v-for="item in column" :key="item.label">
                  <div class="metric-label">{{ item.label }}</div>
                  <div class="metric-value">{{ item.value }}</div>
                  <div class="metric-unit">{{ item.unit }}</div>
                </div>
              </div>
            </div>
          </div>

          <div class="monitor-section gcs-section">
            <div class="section-subtitle">GCS回传</div>
            <div class="gcs-grid">
              <div class="metric-card compact-card" v-for="item in gcsCards" :key="item.label">
                <div class="metric-label">{{ item.label }}</div>
                <div class="metric-value compact-value">{{ item.value }}</div>
                <div class="metric-unit">{{ item.unit }}</div>
              </div>
            </div>
          </div>

          <div class="chart-shell pwm-shell">
            <EChartWrapper
              key="pwm-chart"
              title="PWM输出"
              unit="ratio"
              :series="pwmSeries"
              :showLegend="true"
              :yMin="0"
              :yMax="1"
              :optionOverrides="defaultTimeChartOverrides"
            />
          </div>
        </div>
      </section>

      <section v-if="showSystemPanel" class="monitor-column system-column">
        <div class="column-header">
          <div class="column-title">系统性能</div>
        </div>

        <div class="column-scroll">
          <div class="monitor-section chart-grid-section">
            <div class="section-subtitle">机载关键曲线</div>
            <div class="chart-grid">
              <div class="chart-cell">
                <EChartWrapper title="地速分量" unit="m/s" :series="groundVelocitySeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell">
                <EChartWrapper title="角速度 p/q/r" unit="rad/s" :series="angularRateSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell">
                <EChartWrapper title="控制令牌状态" :series="controlTokenSeries" :showLegend="true" :height="140" :yMin="0" :yMax="4" :optionOverrides="tokenTimeChartOverrides" />
              </div>
              <div class="chart-cell">
                <EChartWrapper title="高度趋势" unit="m" :series="heightSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell chart-span-2">
                <EChartWrapper title="遥控输入" :series="futabaSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <section class="trend-band">
      <div class="trend-card">
        <EChartWrapper key="attitude-trend-chart" title="姿态角趋势" unit="deg" :series="attitudeTrendSeries" :showLegend="true" :height="180" :optionOverrides="defaultTimeChartOverrides" />
      </div>
      <div class="trend-card">
        <EChartWrapper key="path-deviation-trend-chart" title="轨迹偏差趋势" unit="m" :series="pathDeviationSeries" :showLegend="true" :height="180" :optionOverrides="defaultTimeChartOverrides" />
      </div>
      <div class="trend-card">
        <EChartWrapper
          key="trajectory-track-chart"
          title="航迹跟踪"
          unit="m"
          :series="trajectorySeries"
          :showLegend="true"
          :height="180"
          :optionOverrides="trajectoryChartOverrides"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'
import EChartWrapper from '@/components/monitor/EChartWrapper.vue'

const props = defineProps({
  showControlPanel: {
    type: Boolean,
    default: true
  },
  showSystemPanel: {
    type: Boolean,
    default: false
  }
})

const droneStore = useDroneStore()
const showControlPanel = computed(() => props.showControlPanel)
const showSystemPanel = computed(() => props.showSystemPanel)
const monitorContentClass = computed(() => ({
  'single-column': showControlPanel.value !== showSystemPanel.value,
  'empty-panel': !showControlPanel.value && !showSystemPanel.value
}))

const trimSeries = (entries = [], limit = 120) => (entries || []).slice(-limit).map((item) => item.value)
const trimTimedSeries = (entries = [], limit = 120) => (entries || []).slice(-limit).map((item) => [item.timestamp, item.value])
const trimTrack = (entries = [], limit = 180) => (entries || []).slice(-limit)

const padTime = (value) => String(value).padStart(2, '0')
const formatTimeTick = (value) => {
  const date = new Date(Number(value))
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return `${padTime(date.getMinutes())}:${padTime(date.getSeconds())}`
}

const defaultTimeChartOverrides = {
  xAxis: {
    type: 'time',
    axisLine: {
      lineStyle: {
        color: '#94a3b8'
      }
    },
    axisLabel: {
      color: '#475569',
      formatter: formatTimeTick
    },
    splitLine: {
      lineStyle: {
        color: '#dbe4ef',
        type: 'dashed'
      }
    }
  },
  tooltip: {
    trigger: 'axis'
  }
}

const tokenTimeChartOverrides = {
  ...defaultTimeChartOverrides,
  yAxis: {
    type: 'value',
    min: 0,
    max: 4,
    interval: 1,
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
  }
}

const formatValue = (value, digits = 2) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(digits) : (0).toFixed(digits)
}

const statesLat = computed(() => droneStore.fcsStates?.states_lat ?? 0)
const statesLon = computed(() => droneStore.fcsStates?.states_lon ?? 0)
const statesHeight = computed(() => droneStore.fcsStates?.states_height ?? 0)
const statesVx = computed(() => droneStore.fcsStates?.states_Vx_GS ?? 0)
const statesVy = computed(() => droneStore.fcsStates?.states_Vy_GS ?? 0)
const statesVz = computed(() => droneStore.fcsStates?.states_Vz_GS ?? 0)
const statesP = computed(() => droneStore.fcsStates?.states_p ?? 0)
const statesQ = computed(() => droneStore.fcsStates?.states_q ?? 0)
const statesR = computed(() => droneStore.fcsStates?.states_r ?? 0)
const statesPhi = computed(() => droneStore.realtimeViews?.flightState?.phi ?? droneStore.attitude?.roll ?? 0)
const statesTheta = computed(() => droneStore.realtimeViews?.flightState?.theta ?? droneStore.attitude?.pitch ?? 0)
const statesPsi = computed(() => droneStore.realtimeViews?.flightState?.psi ?? droneStore.attitude?.yaw ?? 0)

const gcsCards = computed(() => {
  const gcs = droneStore.gcsData || {}
  return [
    { label: 'CmdIdx', value: Number.isFinite(Number(gcs.Tele_GCS_CmdIdx)) ? String(gcs.Tele_GCS_CmdIdx) : '0', unit: 'idx' },
    { label: 'Mission', value: Number.isFinite(Number(gcs.Tele_GCS_Mission)) ? String(gcs.Tele_GCS_Mission) : '0', unit: 'mission' },
    { label: 'Val', value: formatValue(gcs.Tele_GCS_Val, 3), unit: 'value' },
    { label: 'GCS Fail', value: Number(gcs.Tele_GCS_com_GCS_fail) ? 'FAIL' : 'OK', unit: 'link' }
  ]
})

const stateColumns = computed(() => [
  [
    { label: '纬度', value: formatValue(statesLat.value, 6), unit: 'deg' },
    { label: '经度', value: formatValue(statesLon.value, 6), unit: 'deg' },
    { label: '高度', value: formatValue(statesHeight.value), unit: 'm' }
  ],
  [
    { label: 'Vx', value: formatValue(statesVx.value), unit: 'm/s' },
    { label: 'Vy', value: formatValue(statesVy.value), unit: 'm/s' },
    { label: 'Vz', value: formatValue(statesVz.value), unit: 'm/s' }
  ],
  [
    { label: 'p', value: formatValue(statesP.value, 3), unit: 'rad/s' },
    { label: 'q', value: formatValue(statesQ.value, 3), unit: 'rad/s' },
    { label: 'r', value: formatValue(statesR.value, 3), unit: 'rad/s' }
  ],
  [
    { label: 'φ', value: formatValue(statesPhi.value), unit: 'deg' },
    { label: 'θ', value: formatValue(statesTheta.value), unit: 'deg' },
    { label: 'ψ', value: formatValue(statesPsi.value), unit: 'deg' }
  ]
])

const pwmSeries = computed(() => [
  { name: 'M1', data: trimTimedSeries(droneStore.history.pwm1, 100), lineStyle: { color: '#ef4444' }, itemStyle: { color: '#ef4444' } },
  { name: 'M2', data: trimTimedSeries(droneStore.history.pwm2, 100), lineStyle: { color: '#14b8a6' }, itemStyle: { color: '#14b8a6' } },
  { name: 'M3', data: trimTimedSeries(droneStore.history.pwm3, 100), lineStyle: { color: '#0ea5e9' }, itemStyle: { color: '#0ea5e9' } },
  { name: 'M4', data: trimTimedSeries(droneStore.history.pwm4, 100), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } },
  { name: 'M5', data: trimTimedSeries(droneStore.history.pwm5, 100), lineStyle: { color: '#f59e0b' }, itemStyle: { color: '#f59e0b' } },
  { name: 'M6', data: trimTimedSeries(droneStore.history.pwm6, 100), lineStyle: { color: '#f97316' }, itemStyle: { color: '#f97316' } }
])

const groundVelocitySeries = computed(() => [
  { name: 'Vx', data: trimTimedSeries(droneStore.history.velocityX), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'Vy', data: trimTimedSeries(droneStore.history.velocityY), lineStyle: { color: '#f97316' }, itemStyle: { color: '#f97316' } },
  { name: 'Vz', data: trimTimedSeries(droneStore.history.velocityZ), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } }
])

const angularRateSeries = computed(() => [
  { name: 'p', data: trimTimedSeries(droneStore.history.angularRateP), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'q', data: trimTimedSeries(droneStore.history.angularRateQ), lineStyle: { color: '#f97316' }, itemStyle: { color: '#f97316' } },
  { name: 'r', data: trimTimedSeries(droneStore.history.angularRateR), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } }
])

const controlTokenSeries = computed(() => [
  { name: 'rud', data: trimTimedSeries(droneStore.history.tokenRud), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'ail', data: trimTimedSeries(droneStore.history.tokenAil), lineStyle: { color: '#f59e0b' }, itemStyle: { color: '#f59e0b' } },
  { name: 'ele', data: trimTimedSeries(droneStore.history.tokenEle), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } },
  { name: 'col', data: trimTimedSeries(droneStore.history.tokenCol), lineStyle: { color: '#ef4444' }, itemStyle: { color: '#ef4444' } }
])

const heightSeries = computed(() => [
  { name: 'Actual', data: trimTimedSeries(droneStore.history.altitudeActual), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'Target', data: trimTimedSeries(droneStore.history.altitudeTarget), lineStyle: { color: '#94a3b8', type: 'dashed' }, itemStyle: { color: '#94a3b8' } }
])

const futabaSeries = computed(() => [
  { name: 'Roll', data: trimTimedSeries(droneStore.history.futabaRoll), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'Pitch', data: trimTimedSeries(droneStore.history.futabaPitch), lineStyle: { color: '#f97316' }, itemStyle: { color: '#f97316' } },
  { name: 'Yaw', data: trimTimedSeries(droneStore.history.futabaYaw), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } }
])

const attitudeTrendSeries = computed(() => [
  { name: 'Roll', data: trimTimedSeries(droneStore.history.rollActual, 160), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'Pitch', data: trimTimedSeries(droneStore.history.pitchActual, 160), lineStyle: { color: '#0ea5e9' }, itemStyle: { color: '#0ea5e9' } },
  { name: 'Yaw', data: trimTimedSeries(droneStore.history.yawActual, 160), lineStyle: { color: '#f97316' }, itemStyle: { color: '#f97316' } }
])

const pathDeviationSeries = computed(() => [
  { name: 'Error X', data: trimTimedSeries(droneStore.metricTrends.pathErrorX, 160), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'Error Y', data: trimTimedSeries(droneStore.metricTrends.pathErrorY, 160), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } },
  { name: 'Error Z', data: trimTimedSeries(droneStore.metricTrends.pathErrorZ, 160), lineStyle: { color: '#ef4444' }, itemStyle: { color: '#ef4444' } },
  { name: 'Total', data: trimTimedSeries(droneStore.metricTrends.pathDeviationM, 160), lineStyle: { color: '#111827' }, itemStyle: { color: '#111827' } }
])

const trajectorySeries = computed(() => {
  const actualPath = trimTrack(droneStore.trajectory, 220).map((point) => [point.x, point.y])
  const targetPathSource = droneStore.localTraj.length ? droneStore.localTraj : droneStore.globalPath
  const targetPath = trimTrack(targetPathSource, 220).map((point) => [point.x, point.y])

  return [
    {
      name: '实际航迹',
      data: actualPath,
      lineStyle: { color: '#2563eb', width: 2.5 },
      itemStyle: { color: '#2563eb' },
      symbol: 'none'
    },
    {
      name: '目标航迹',
      data: targetPath,
      lineStyle: { color: '#94a3b8', type: 'dashed', width: 2 },
      itemStyle: { color: '#94a3b8' },
      symbol: 'none'
    }
  ]
})

const trajectoryChartOverrides = computed(() => ({
  xAxis: {
    type: 'value',
    name: 'X (m)',
    nameLocation: 'middle',
    nameGap: 24,
    axisLine: { lineStyle: { color: '#94a3b8' } },
    axisLabel: { color: '#475569' },
    splitLine: { lineStyle: { color: '#dbe4ef', type: 'dashed' } }
  },
  yAxis: {
    type: 'value',
    name: 'Y (m)',
    nameLocation: 'middle',
    nameGap: 32,
    axisLine: { lineStyle: { color: '#94a3b8' } },
    axisLabel: { color: '#475569' },
    splitLine: { lineStyle: { color: '#dbe4ef', type: 'dashed' } }
  },
  tooltip: { trigger: 'item' }
}))

</script>

<style scoped>
.monitor-tabs-panel {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(180deg, #f8fbff 0%, #edf4fb 100%);
  color: var(--text-primary);
}

.monitor-content {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 12px;
  padding: 12px 12px 8px;
}

.monitor-content.single-column {
  grid-template-columns: 1fr;
}

.monitor-content.empty-panel {
  display: none;
}

.monitor-column {
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.column-header {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-light);
  background: linear-gradient(180deg, rgba(255, 255, 255, 1) 0%, rgba(241, 245, 249, 0.96) 100%);
}

.column-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.column-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(37, 99, 235, 0.38) rgba(219, 228, 239, 0.7);
}

.column-scroll::-webkit-scrollbar {
  width: 8px;
}

.column-scroll::-webkit-scrollbar-track {
  background: rgba(219, 228, 239, 0.7);
  border-radius: 999px;
}

.column-scroll::-webkit-scrollbar-thumb {
  background: rgba(37, 99, 235, 0.38);
  border-radius: 999px;
}

.chart-shell,
.monitor-section {
  margin-bottom: 10px;
}

.monitor-section {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 10px;
}

.section-subtitle {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-color);
  margin-bottom: 8px;
}

.state-section {
  padding: 8px;
}

.state-columns {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.state-column {
  display: grid;
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.state-column .metric-card {
  min-height: 74px;
}

.gcs-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 10px;
  border-radius: 10px;
  background: var(--panel-muted);
  border: 1px solid var(--border-light);
}

.compact-card {
  min-height: 64px;
}

.metric-label,
.metric-unit {
  font-size: 11px;
  color: var(--text-tertiary);
}

.metric-value {
  margin-top: 4px;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.15;
  font-family: 'Consolas', 'Monaco', monospace;
  color: var(--text-primary);
}

.compact-value {
  font-size: 15px;
}

.metric-unit {
  margin-top: 2px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.chart-cell {
  min-height: 0;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.72);
  overflow: hidden;
}

.chart-span-2 {
  grid-column: span 2;
}

.trend-band {
  flex: 0 0 232px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 0 12px 12px;
}

.trend-card {
  min-height: 0;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.pwm-shell :deep(.chart-header),
.chart-cell :deep(.chart-header),
.trend-card :deep(.chart-header) {
  padding: 10px 12px 6px;
}

.pwm-shell :deep(.chart-title),
.pwm-shell :deep(.chart-unit),
.chart-cell :deep(.chart-title),
.chart-cell :deep(.chart-unit),
.trend-card :deep(.chart-title),
.trend-card :deep(.chart-unit) {
  font-size: 11px;
}

.pwm-shell :deep(.chart-container) {
  height: 118px !important;
  min-height: 118px !important;
}

.status-ok {
  color: var(--success-color);
}

.status-warn {
  color: var(--warning-color);
}

.status-danger {
  color: var(--error-color);
}

.system-column {
  min-width: 320px;
}

@media (max-width: 1400px) {
  .monitor-content {
    grid-template-columns: 1fr;
  }

  .trend-band {
    grid-template-columns: 1fr;
    flex-basis: 620px;
  }
}

@media (max-width: 760px) {
  .state-columns,
  .gcs-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }

  .chart-span-2 {
    grid-column: span 1;
  }

  .state-column {
    grid-template-rows: none;
  }
}
</style>