<template>
  <section class="online-card">
    <div class="online-header">
      <div>
        <div class="online-title">在线评测</div>
        <div class="online-subtitle">地面端实时综合性能评测</div>
      </div>
      <div class="online-badge" :class="badgeClass">{{ badgeText }}</div>
    </div>

    <div class="online-body">
      <div class="score-block">
        <div class="score-label">综合分</div>
        <div class="score-value">{{ compositeText }}</div>
      </div>

      <div class="domain-grid">
        <div class="domain-item" v-for="item in domainItems" :key="item.key">
          <span class="domain-name">{{ item.label }}</span>
          <span class="domain-value">{{ item.value }}</span>
        </div>
      </div>
    </div>

    <div class="online-footer">
      <span>通道: {{ channelText }}</span>
      <span v-if="missingText">缺失: {{ missingText }}</span>
    </div>

    <div class="architecture-panel" v-if="architectureGroups.length">
      <div class="architecture-header">
        <div>
          <div class="architecture-title">{{ architectureTitle }}</div>
          <div class="architecture-meta">{{ architectureMeta }}</div>
        </div>
      </div>

      <div class="architecture-grid">
        <div class="architecture-column" v-for="group in architectureGroups" :key="group.hardware">
          <div class="architecture-node">{{ group.hardware_label }}</div>
          <div class="architecture-module" v-for="module in group.modules" :key="module.function">
            {{ module.function_label }}
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

const badgeText = computed(() => {
  if (!droneStore.onlineAnalysis.enabled) return '未启用'
  if (droneStore.onlineAnalysis.ready) return '已就绪'
  return '等待数据'
})

const badgeClass = computed(() => ({
  ready: droneStore.onlineAnalysis.ready,
  waiting: droneStore.onlineAnalysis.enabled && !droneStore.onlineAnalysis.ready,
  disabled: !droneStore.onlineAnalysis.enabled
}))

const compositeText = computed(() => {
  const value = droneStore.onlineAnalysis.compositeScore
  return Number.isFinite(value) ? value.toFixed(1) : '--'
})

const domainItems = computed(() => {
  const scores = droneStore.onlineAnalysis.domainScores || {}
  return [
    { key: 'perception', label: '感知', value: formatScore(scores.perception) },
    { key: 'decision', label: '决策', value: formatScore(scores.decision) },
    { key: 'control', label: '控制', value: formatScore(scores.control) },
    { key: 'communication', label: '通信', value: formatScore(scores.communication) },
    { key: 'safety', label: '安全', value: formatScore(scores.safety) }
  ]
})

const channelText = computed(() => {
  const channels = droneStore.onlineAnalysis.availableChannels || []
  return channels.length ? channels.join(' / ') : '暂无'
})

const missingText = computed(() => {
  const missing = droneStore.onlineAnalysis.missingRequiredChannels || []
  return missing.length ? missing.join(' / ') : ''
})

const architectureInfo = computed(() => droneStore.onlineAnalysis.recommendedArchitecture || {})
const architectureTitle = computed(() => architectureInfo.value.title || '最优架构方案')
const architectureMeta = computed(() => {
  const preset = architectureInfo.value.preset || '--'
  const paradigm = architectureInfo.value.paradigm || '--'
  return `${preset} / ${paradigm}`
})
const architectureGroups = computed(() => architectureInfo.value.groupedAllocation || [])

function formatScore(value) {
  return Number.isFinite(value) ? value.toFixed(1) : '--'
}
</script>

<style scoped>
.online-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92) 0%, rgba(240, 247, 255, 0.96) 100%);
  border: 1px solid #d6e3f1;
}

.online-header,
.online-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.online-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.online-subtitle,
.online-footer {
  font-size: 11px;
  color: #64748b;
}

.online-badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.online-badge.ready {
  background: rgba(22, 163, 74, 0.12);
  color: #166534;
}

.online-badge.waiting {
  background: rgba(217, 119, 6, 0.12);
  color: #92400e;
}

.online-badge.disabled {
  background: rgba(148, 163, 184, 0.18);
  color: #475569;
}

.online-body {
  display: flex;
  align-items: center;
  gap: 16px;
}

.score-block {
  min-width: 96px;
}

.score-label {
  font-size: 11px;
  color: #64748b;
}

.score-value {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.1;
}

.domain-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.domain-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
}

.domain-name {
  font-size: 11px;
  color: #64748b;
}

.domain-value {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.architecture-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 2px;
}

.architecture-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.architecture-meta {
  font-size: 11px;
  color: #64748b;
}

.architecture-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.architecture-column {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #dbe7f4;
}

.architecture-node {
  font-size: 11px;
  font-weight: 700;
  color: #0f172a;
}

.architecture-module {
  font-size: 12px;
  color: #334155;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(226, 232, 240, 0.52);
}

@media (max-width: 920px) {
  .architecture-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .online-body {
    flex-direction: column;
    align-items: flex-start;
  }

  .domain-grid,
  .architecture-grid {
    grid-template-columns: 1fr;
  }
}
</style>