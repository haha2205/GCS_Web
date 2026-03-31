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
            <div class="section-subtitle">电机数值</div>
            <div class="chart-grid">
              <div class="chart-cell">
                <EChartWrapper title="电调电压" unit="V" :series="escVoltageSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell">
                <EChartWrapper title="电调电流" unit="A" :series="escCurrentSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell">
                <EChartWrapper title="电调温度" unit="°C" :series="escTempSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell">
                <EChartWrapper title="电机转速" unit="rpm" :series="escRpmSeries" :showLegend="true" :height="140" :optionOverrides="defaultTimeChartOverrides" />
              </div>
              <div class="chart-cell chart-span-2">
                <EChartWrapper title="功率百分比" unit="%" :series="escPowerSeries" :showLegend="true" :height="140" :yMin="0" :yMax="100" :optionOverrides="defaultTimeChartOverrides" />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <section class="trend-band">
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

const formatValue = (value, digits = 2) => {
  const num = Number(value)
  return Number.isFinite(num) ? num.toFixed(digits) : (0).toFixed(digits)
}

const formatTelemetryValue = (hasTelemetry, value, digits = 2) => {
  if (!hasTelemetry) {
    return '--'
  }
  return formatValue(value, digits)
}

const formatTelemetryInteger = (hasTelemetry, value) => {
  if (!hasTelemetry) {
    return '--'
  }
  const num = Number(value)
  return Number.isFinite(num) ? String(Math.trunc(num)) : '--'
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
const hasFlightTelemetry = computed(() => !!droneStore.telemetryTimestamps?.flightState)
const hasGcsTelemetry = computed(() => !!droneStore.telemetryTimestamps?.gcsData)
const alignedTargetPath = computed(() => {
  const source = droneStore.localTraj.length ? droneStore.localTraj : droneStore.globalPath
  return (source || []).map((point) => droneStore._alignPlanningPoint(point))
})

const gcsCards = computed(() => {
  const gcs = droneStore.gcsData || {}
  return [
    { label: 'CmdIdx', value: formatTelemetryInteger(hasGcsTelemetry.value, gcs.Tele_GCS_CmdIdx), unit: 'idx' },
    { label: 'Mission', value: formatTelemetryInteger(hasGcsTelemetry.value, gcs.Tele_GCS_Mission), unit: 'mission' },
    { label: 'Val', value: hasGcsTelemetry.value ? formatValue(gcs.Tele_GCS_Val, 3) : '--', unit: 'value' },
    { label: 'GCS Fail', value: hasGcsTelemetry.value ? (Number(gcs.Tele_GCS_com_GCS_fail) ? 'FAIL' : 'OK') : '未接入', unit: 'link' }
  ]
})

const stateColumns = computed(() => [
  [
    { label: '纬度', value: formatTelemetryValue(hasFlightTelemetry.value, statesLat.value, 6), unit: 'deg' },
    { label: '经度', value: formatTelemetryValue(hasFlightTelemetry.value, statesLon.value, 6), unit: 'deg' },
    { label: '高度', value: formatTelemetryValue(hasFlightTelemetry.value, statesHeight.value), unit: 'm' }
  ],
  [
    { label: 'Vx', value: formatTelemetryValue(hasFlightTelemetry.value, statesVx.value), unit: 'm/s' },
    { label: 'Vy', value: formatTelemetryValue(hasFlightTelemetry.value, statesVy.value), unit: 'm/s' },
    { label: 'Vz', value: formatTelemetryValue(hasFlightTelemetry.value, statesVz.value), unit: 'm/s' }
  ],
  [
    { label: 'p', value: formatTelemetryValue(hasFlightTelemetry.value, statesP.value, 3), unit: 'rad/s' },
    { label: 'q', value: formatTelemetryValue(hasFlightTelemetry.value, statesQ.value, 3), unit: 'rad/s' },
    { label: 'r', value: formatTelemetryValue(hasFlightTelemetry.value, statesR.value, 3), unit: 'rad/s' }
  ],
  [
    { label: 'φ', value: formatTelemetryValue(hasFlightTelemetry.value, statesPhi.value), unit: 'deg' },
    { label: 'θ', value: formatTelemetryValue(hasFlightTelemetry.value, statesTheta.value), unit: 'deg' },
    { label: 'ψ', value: formatTelemetryValue(hasFlightTelemetry.value, statesPsi.value), unit: 'deg' }
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

const motorColors = ['#ef4444', '#14b8a6', '#0ea5e9', '#22c55e', '#f59e0b', '#f97316']
const motorNames = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6']

const escVoltageSeries = computed(() =>
  motorNames.map((name, i) => ({
    name,
    data: trimTimedSeries(droneStore.history[`escVoltage${i + 1}`], 100),
    lineStyle: { color: motorColors[i] },
    itemStyle: { color: motorColors[i] }
  }))
)

const escCurrentSeries = computed(() =>
  motorNames.map((name, i) => ({
    name,
    data: trimTimedSeries(droneStore.history[`escCurrent${i + 1}`], 100),
    lineStyle: { color: motorColors[i] },
    itemStyle: { color: motorColors[i] }
  }))
)

const escTempSeries = computed(() =>
  motorNames.map((name, i) => ({
    name,
    data: trimTimedSeries(droneStore.history[`escTemp${i + 1}`], 100),
    lineStyle: { color: motorColors[i] },
    itemStyle: { color: motorColors[i] }
  }))
)

const escRpmSeries = computed(() =>
  motorNames.map((name, i) => ({
    name,
    data: trimTimedSeries(droneStore.history[`escRpm${i + 1}`], 100),
    lineStyle: { color: motorColors[i] },
    itemStyle: { color: motorColors[i] }
  }))
)

const escPowerSeries = computed(() =>
  motorNames.map((name, i) => ({
    name,
    data: trimTimedSeries(droneStore.history[`escPower${i + 1}`], 100),
    lineStyle: { color: motorColors[i] },
    itemStyle: { color: motorColors[i] }
  }))
)

const pathDeviationSeries = computed(() => [
  { name: 'Error X', data: trimTimedSeries(droneStore.metricTrends.pathErrorX, 160), lineStyle: { color: '#2563eb' }, itemStyle: { color: '#2563eb' } },
  { name: 'Error Y', data: trimTimedSeries(droneStore.metricTrends.pathErrorY, 160), lineStyle: { color: '#22c55e' }, itemStyle: { color: '#22c55e' } },
  { name: 'Error Z', data: trimTimedSeries(droneStore.metricTrends.pathErrorZ, 160), lineStyle: { color: '#ef4444' }, itemStyle: { color: '#ef4444' } },
  { name: 'Total', data: trimTimedSeries(droneStore.metricTrends.pathDeviationM, 160), lineStyle: { color: '#111827' }, itemStyle: { color: '#111827' } }
])

const trajectorySeries = computed(() => {
  const actualPath = trimTrack(droneStore.trajectory, 220).map((point) => [point.x, point.y])
  const targetPath = trimTrack(alignedTargetPath.value, 220).map((point) => [point.x, point.y])

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
  overflow-y: auto;
  overflow-x: hidden;
  background: linear-gradient(180deg, #f8fbff 0%, #edf4fb 100%);
  color: var(--text-primary);
  scrollbar-width: thin;
  scrollbar-color: rgba(37, 99, 235, 0.38) rgba(219, 228, 239, 0.7);
}

.monitor-tabs-panel::-webkit-scrollbar {
  width: 8px;
}

.monitor-tabs-panel::-webkit-scrollbar-track {
  background: rgba(219, 228, 239, 0.7);
}

.monitor-tabs-panel::-webkit-scrollbar-thumb {
  background: rgba(37, 99, 235, 0.38);
  border-radius: 999px;
}

.monitor-content {
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
  padding: 12px;
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
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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