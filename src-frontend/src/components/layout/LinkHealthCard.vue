<template>
  <section class="link-health-drawer">
    <div class="drawer-header">
      <div>
        <div class="drawer-kicker">Data Link Monitor</div>
        <div class="drawer-title">链路健康总览</div>
        <div class="drawer-subtitle">RX / 解析 / TX / 吞吐 / 队列 同屏趋势</div>
      </div>
      <div class="drawer-actions">
        <div class="health-badge" :class="healthLevelClass">{{ healthLabel }}</div>
        <button v-if="closable" class="close-btn" type="button" @click="$emit('close')">关闭</button>
      </div>
    </div>

    <div class="hero-shell">
      <div class="hero-copy">
        <div class="hero-title">链路趋势主视图</div>
        <div class="hero-text">左轴看上下行与解析速率，右轴看吞吐与积压。正常情况下，RX 与解析应贴近，队列应贴地。</div>
      </div>
      <div class="hero-summary">{{ healthSummary }}</div>
    </div>

    <div class="trend-panel">
      <EChartWrapper
        title="链路总览曲线"
        unit="pps / kbps / queue"
        :series="trafficTrendSeries"
        :showLegend="true"
        :height="260"
        :optionOverrides="trafficTrendOverrides"
      />
    </div>

    <div class="headline-grid">
      <div class="headline-item">
        <span class="headline-label">接收</span>
        <strong class="headline-value">{{ stats.rxPacketsTotal }}</strong>
        <span class="headline-meta">{{ stats.recentRxPps.toFixed(1) }} pps</span>
      </div>
      <div class="headline-item">
        <span class="headline-label">解析</span>
        <strong class="headline-value">{{ stats.parsedMessagesTotal }}</strong>
        <span class="headline-meta">{{ stats.recentParsedPps.toFixed(1) }} pps</span>
      </div>
      <div class="headline-item">
        <span class="headline-label">发送</span>
        <strong class="headline-value">{{ stats.txPacketsTotal }}</strong>
        <span class="headline-meta">{{ stats.recentTxPps.toFixed(1) }} pps</span>
      </div>
      <div class="headline-item emphasis-item">
        <span class="headline-label">吞吐</span>
        <strong class="headline-value">{{ stats.recentPayloadKbps.toFixed(1) }}</strong>
        <span class="headline-meta">kbps</span>
      </div>
    </div>

    <div class="queue-grid">
      <div class="queue-item" :class="queueClass(stats.packetQueueSize)">
        <span class="queue-name">分发队列</span>
        <span class="queue-value">{{ stats.packetQueueSize }}</span>
      </div>
      <div class="queue-item" :class="queueClass(stats.recordingQueueSize)">
        <span class="queue-name">录制队列</span>
        <span class="queue-value">{{ stats.recordingQueueSize }}</span>
      </div>
      <div class="queue-item" :class="queueClass(stats.onlineAnalysisQueueSize)">
        <span class="queue-name">评测队列</span>
        <span class="queue-value">{{ stats.onlineAnalysisQueueSize }}</span>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-item">
        <span class="detail-label">解析拒绝</span>
        <span class="detail-value" :class="stats.parserRejectionsTotal ? 'warn' : 'ok'">{{ stats.parserRejectionsTotal }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">解析问题</span>
        <span class="detail-value" :class="stats.parserIssuesTotal ? 'warn' : 'ok'">{{ stats.parserIssuesTotal }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">监听端口</span>
        <span class="detail-value">{{ portText }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">运行时长</span>
        <span class="detail-value">{{ uptimeText }}</span>
      </div>
      <div class="detail-item detail-item-wide">
        <span class="detail-label">最近刷新</span>
        <span class="detail-value">{{ lastUpdatedText }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import EChartWrapper from '@/components/monitor/EChartWrapper.vue'
import { useDroneStore } from '@/store/drone'

defineEmits(['close'])

const props = defineProps({
  closable: {
    type: Boolean,
    default: false
  }
})

const droneStore = useDroneStore()

const stats = computed(() => droneStore.trafficStats)
const healthSummary = computed(() => droneStore.trafficHealthSummary)
const healthLevel = computed(() => droneStore.trafficHealthLevel)
const trafficTrend = computed(() => droneStore.trafficTrend)

const healthLabel = computed(() => {
  switch (healthLevel.value) {
    case 'healthy':
      return '通畅'
    case 'warning':
      return '预警'
    case 'blocked':
      return '积压'
    case 'stale':
      return '停滞'
    case 'offline':
      return '未启动'
    case 'watch':
      return '观察'
    default:
      return '未采集'
  }
})

const healthLevelClass = computed(() => ({
  healthy: healthLevel.value === 'healthy',
  warning: healthLevel.value === 'warning' || healthLevel.value === 'watch',
  blocked: healthLevel.value === 'blocked' || healthLevel.value === 'stale',
  offline: healthLevel.value === 'offline' || healthLevel.value === 'idle'
}))

const portText = computed(() => {
  const ports = stats.value.listeningPorts || []
  return ports.length ? ports.join(' / ') : '--'
})

const lastUpdatedText = computed(() => {
  if (!stats.value.lastUpdated) return '--'
  return new Date(stats.value.lastUpdated).toLocaleTimeString('zh-CN', { hour12: false })
})

const uptimeText = computed(() => {
  const totalSeconds = Math.max(0, Math.floor(Number(stats.value.uptimeSec || 0)))
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0')
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0')
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
})

const trimTimedSeries = (entries = [], limit = 180) => (entries || []).slice(-limit).map((item) => [item.timestamp, item.value])

const padTime = (value) => String(value).padStart(2, '0')
const formatTimeTick = (value) => {
  const date = new Date(Number(value))
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  return `${padTime(date.getMinutes())}:${padTime(date.getSeconds())}`
}

const trafficTrendSeries = computed(() => [
  {
    name: 'RX pps',
    data: trimTimedSeries(trafficTrend.value.rxPps),
    yAxisIndex: 0,
    smooth: true,
    areaStyle: { color: 'rgba(56, 189, 248, 0.08)' },
    lineStyle: { color: '#38bdf8', width: 2.4 },
    itemStyle: { color: '#38bdf8' }
  },
  {
    name: '解析 pps',
    data: trimTimedSeries(trafficTrend.value.parsedPps),
    yAxisIndex: 0,
    smooth: true,
    areaStyle: { color: 'rgba(74, 222, 128, 0.08)' },
    lineStyle: { color: '#22c55e', width: 2.4 },
    itemStyle: { color: '#22c55e' }
  },
  {
    name: 'TX pps',
    data: trimTimedSeries(trafficTrend.value.txPps),
    yAxisIndex: 0,
    smooth: true,
    lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
    itemStyle: { color: '#f59e0b' }
  },
  {
    name: '吞吐 kbps',
    data: trimTimedSeries(trafficTrend.value.payloadKbps),
    yAxisIndex: 1,
    smooth: true,
    lineStyle: { color: '#a78bfa', width: 2 },
    itemStyle: { color: '#a78bfa' }
  },
  {
    name: '分发队列',
    data: trimTimedSeries(trafficTrend.value.packetQueueSize),
    yAxisIndex: 1,
    smooth: true,
    lineStyle: { color: '#ef4444', width: 1.8 },
    itemStyle: { color: '#ef4444' }
  },
  {
    name: '录制队列',
    data: trimTimedSeries(trafficTrend.value.recordingQueueSize),
    yAxisIndex: 1,
    smooth: true,
    lineStyle: { color: '#f59e0b', width: 1.8 },
    itemStyle: { color: '#f59e0b' }
  },
  {
    name: '评测队列',
    data: trimTimedSeries(trafficTrend.value.onlineAnalysisQueueSize),
    yAxisIndex: 1,
    smooth: true,
    lineStyle: { color: '#ec4899', width: 1.8 },
    itemStyle: { color: '#ec4899' }
  }
])

const trafficTrendOverrides = {
  backgroundColor: 'transparent',
  grid: {
    left: 44,
    right: 50,
    top: 42,
    bottom: 34
  },
  legend: {
    top: 6,
    textStyle: {
      color: '#cbd5e1',
      fontSize: 11
    }
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(15, 23, 42, 0.92)',
    borderColor: 'rgba(148, 163, 184, 0.35)',
    textStyle: {
      color: '#e2e8f0'
    }
  },
  xAxis: {
    type: 'time',
    axisLine: {
      lineStyle: {
        color: 'rgba(148, 163, 184, 0.55)'
      }
    },
    axisLabel: {
      color: '#94a3b8',
      formatter: formatTimeTick
    },
    splitLine: {
      lineStyle: {
        color: 'rgba(51, 65, 85, 0.55)',
        type: 'dashed'
      }
    }
  },
  yAxis: [
    {
      type: 'value',
      name: 'pps',
      nameTextStyle: { color: '#93c5fd', padding: [0, 0, 0, 10] },
      axisLine: { lineStyle: { color: 'rgba(96, 165, 250, 0.65)' } },
      axisLabel: { color: '#93c5fd' },
      splitLine: { lineStyle: { color: 'rgba(51, 65, 85, 0.45)', type: 'dashed' } }
    },
    {
      type: 'value',
      name: 'kbps / queue',
      nameTextStyle: { color: '#f9a8d4', padding: [0, 10, 0, 0] },
      axisLine: { lineStyle: { color: 'rgba(244, 114, 182, 0.6)' } },
      axisLabel: { color: '#f9a8d4' },
      splitLine: { show: false }
    }
  ]
}

function queueClass(size) {
  if (size >= 50) return 'danger'
  if (size >= 10) return 'warn'
  return 'good'
}
</script>

<style scoped>
.link-health-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.12), transparent 34%),
    radial-gradient(circle at top right, rgba(56, 189, 248, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(5, 10, 24, 0.99) 0%, rgba(14, 23, 43, 0.98) 100%);
  border: 1px solid rgba(71, 126, 176, 0.34);
  box-shadow: 0 28px 60px rgba(2, 6, 23, 0.42);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.drawer-kicker {
  font-size: 11px;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: #67e8f9;
}

.drawer-title {
  margin-top: 3px;
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
}

.drawer-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #8ea3bf;
}

.drawer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.health-badge {
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.health-badge.healthy {
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
}

.health-badge.warning {
  background: rgba(245, 158, 11, 0.14);
  color: #fcd34d;
}

.health-badge.blocked {
  background: rgba(239, 68, 68, 0.14);
  color: #fda4af;
}

.health-badge.offline {
  background: rgba(100, 116, 139, 0.2);
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

.hero-shell {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-end;
  padding: 14px 16px;
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(11, 21, 40, 0.84) 0%, rgba(16, 31, 54, 0.68) 100%);
  border: 1px solid rgba(80, 129, 176, 0.22);
}

.hero-title {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
}

.hero-text {
  margin-top: 4px;
  max-width: 620px;
  font-size: 12px;
  line-height: 1.5;
  color: #95a9c3;
}

.hero-summary {
  font-size: 14px;
  font-weight: 700;
  color: #d9f99d;
}

.trend-panel {
  padding: 10px;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(9, 17, 33, 0.94) 0%, rgba(6, 12, 24, 0.98) 100%);
  border: 1px solid rgba(76, 115, 156, 0.22);
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.04);
}

.trend-panel :deep(.e-chart-wrapper) {
  margin-bottom: 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(12, 22, 40, 0.96) 0%, rgba(8, 15, 28, 0.98) 100%);
  border: 1px solid rgba(78, 112, 148, 0.2);
}

.trend-panel :deep(.chart-header) {
  border-bottom-color: rgba(71, 85, 105, 0.35);
}

.trend-panel :deep(.chart-title) {
  color: #f8fafc;
}

.trend-panel :deep(.chart-unit) {
  color: #7f95b3;
}

.trend-panel :deep(.chart-container) {
  height: 260px !important;
  min-height: 260px !important;
  border-radius: 10px;
}

.headline-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.headline-item,
.detail-item,
.queue-item {
  background: linear-gradient(180deg, rgba(14, 23, 40, 0.78) 0%, rgba(10, 18, 33, 0.88) 100%);
  border: 1px solid rgba(78, 112, 148, 0.2);
  border-radius: 12px;
}

.headline-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
}

.emphasis-item {
  background: linear-gradient(180deg, rgba(30, 64, 175, 0.28) 0%, rgba(13, 24, 46, 0.9) 100%);
}

.headline-label,
.detail-label,
.queue-name {
  font-size: 11px;
  color: #87a0bd;
}

.headline-value,
.queue-value,
.detail-value {
  color: #f8fafc;
  font-family: 'Consolas', 'Monaco', monospace;
}

.headline-value {
  font-size: 20px;
  line-height: 1.1;
}

.headline-meta {
  font-size: 11px;
  color: #b7c7d9;
}

.queue-grid,
.detail-grid {
  display: grid;
  gap: 10px;
}

.queue-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.queue-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
}

.queue-item.good {
  border-color: rgba(34, 197, 94, 0.28);
}

.queue-item.warn {
  border-color: rgba(245, 158, 11, 0.32);
}

.queue-item.danger {
  border-color: rgba(185, 28, 28, 0.38);
  background: linear-gradient(180deg, rgba(69, 10, 10, 0.46) 0%, rgba(30, 12, 18, 0.72) 100%);
}

.queue-value {
  font-size: 18px;
  font-weight: 700;
}

.detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 10px 12px;
}

.detail-item-wide {
  grid-column: span 2;
}

.detail-value {
  font-size: 13px;
  font-weight: 700;
}

.detail-value.ok {
  color: #4ade80;
}

.detail-value.warn {
  color: #fcd34d;
}

.summary-value {
  font-family: inherit;
}

@media (max-width: 920px) {
  .drawer-header,
  .hero-shell {
    flex-direction: column;
    align-items: flex-start;
  }

  .headline-grid,
  .queue-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .detail-item-wide {
    grid-column: span 1;
  }
}
</style>