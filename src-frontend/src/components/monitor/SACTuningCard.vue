<template>
  <div class="sac-card">
    <div class="card-header">
      <div>
        <div class="card-title">SAC 调参过程</div>
        <div class="card-subtitle">3 参数最小集：fKeVx / fIeVx / fKeAx</div>
      </div>
      <div class="status-pill" :class="statusClass">{{ displayState || 'idle' }}</div>
    </div>

    <div class="meta-grid">
      <div class="meta-item"><span>Session</span><strong>{{ rlTuning.sessionId || '--' }}</strong></div>
      <div class="meta-item"><span>Episode</span><strong>{{ rlTuning.episodeId || '--' }}</strong></div>
      <div class="meta-item"><span>Replay</span><strong>{{ rlTuning.replaySize }}</strong></div>
      <div class="meta-item"><span>History</span><strong>{{ rlTuning.historySize }}</strong></div>
      <div class="meta-item"><span>Last Reward</span><strong>{{ formatNumber(rlTuning.lastReward) }}</strong></div>
      <div class="meta-item"><span>Best Reward</span><strong>{{ formatNumber(rlTuning.bestReward) }}</strong></div>
    </div>

    <div class="flag-row">
      <span class="flag" :class="{ ok: rlTuning.paramEchoConfirmed }">回读确认: {{ rlTuning.paramEchoConfirmed ? '是' : '否' }}</span>
      <span class="flag" :class="{ ok: rlTuning.taskStartAllowed }">可启动任务: {{ rlTuning.taskStartAllowed ? '是' : '否' }}</span>
      <span class="flag" :class="{ warn: rlTuning.rollbackTriggered }">触发回退: {{ rlTuning.rollbackTriggered ? '是' : '否' }}</span>
    </div>

    <div class="section">
      <div class="section-title">当前参数</div>
      <div class="param-grid">
        <div v-for="key in trackedKeys" :key="`curr-${key}`" class="param-item">
          <span>{{ key }}</span>
          <strong>{{ formatNumber(rlTuning.currentParams?.[key]) }}</strong>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">候选参数</div>
      <div class="param-grid">
        <div v-for="key in trackedKeys" :key="`cand-${key}`" class="param-item candidate">
          <span>{{ key }}</span>
          <strong>{{ formatNumber(rlTuning.candidateParams?.[key]) }}</strong>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">训练指标</div>
      <div class="metric-grid">
        <div class="metric-item"><span>actor_loss</span><strong>{{ formatNumber(agent.actor_loss) }}</strong></div>
        <div class="metric-item"><span>critic1_loss</span><strong>{{ formatNumber(agent.critic1_loss) }}</strong></div>
        <div class="metric-item"><span>critic2_loss</span><strong>{{ formatNumber(agent.critic2_loss) }}</strong></div>
        <div class="metric-item"><span>alpha</span><strong>{{ formatNumber(agent.alpha) }}</strong></div>
        <div class="metric-item"><span>avg_q</span><strong>{{ formatNumber(agent.avg_q) }}</strong></div>
        <div class="metric-item"><span>avg_log_prob</span><strong>{{ formatNumber(agent.avg_log_prob) }}</strong></div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">SAC 输出动作</div>
      <div class="vector-row">
        <span v-for="(value, index) in rlTuning.latestActionVector || []" :key="`action-${index}`">a{{ index + 1 }}={{ formatNumber(value) }}</span>
      </div>
      <div class="vector-row small">
        <span v-for="(value, index) in agent.policy_mean || []" :key="`mean-${index}`">mu{{ index + 1 }}={{ formatNumber(value) }}</span>
      </div>
      <div class="vector-row small">
        <span v-for="(value, index) in agent.policy_std || []" :key="`std-${index}`">sigma{{ index + 1 }}={{ formatNumber(value) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()
const rlTuning = computed(() => droneStore.rlTuning || {})
const agent = computed(() => rlTuning.value.agentMetrics || {})
const trackedKeys = computed(() => (rlTuning.value.parameterKeys?.length ? rlTuning.value.parameterKeys : ['fKeVx', 'fIeVx', 'fKeAx']))

const displayState = computed(() => {
  const state = rlTuning.value.state || 'idle'
  const hasCandidate = Object.keys(rlTuning.value.candidateParams || {}).length > 0
  const hasActiveEpisode = !!rlTuning.value.episodeId
  const hasValidSession = !!rlTuning.value.sessionId

  if (state === 'error' && hasValidSession && (hasCandidate || hasActiveEpisode || rlTuning.value.paramEchoConfirmed)) {
    return hasActiveEpisode ? 'episode_running' : 'session_ready'
  }

  return state
})

const statusClass = computed(() => {
  const state = displayState.value
  if (state === 'episode_running') return 'healthy'
  if (state === 'waiting_param_echo' || state === 'episode_preparing' || state === 'applying_params' || state === 'session_ready') return 'warning'
  if (state === 'error') return 'danger'
  return 'idle'
})

function formatNumber(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) {
    return '--'
  }
  return num.toFixed(6).replace(/\.0+$/, '').replace(/(\.\d*?[1-9])0+$/, '$1')
}
</script>

<style scoped>
.sac-card {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.card-subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.status-pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  background: #e2e8f0;
  color: #334155;
}

.status-pill.healthy { background: #dcfce7; color: #166534; }
.status-pill.warning { background: #fef3c7; color: #92400e; }
.status-pill.danger { background: #fee2e2; color: #991b1b; }

.meta-grid,
.metric-grid,
.param-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.meta-item,
.metric-item,
.param-item {
  padding: 8px;
  border-radius: 10px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-item.candidate {
  background: #eff6ff;
}

.meta-item span,
.metric-item span,
.param-item span {
  font-size: 11px;
  color: #64748b;
}

.meta-item strong,
.metric-item strong,
.param-item strong {
  font-size: 13px;
  color: #0f172a;
  font-family: 'Courier New', monospace;
}

.flag-row,
.vector-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.flag {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #334155;
}

.flag.ok { background: #dcfce7; color: #166534; }
.flag.warn { background: #fee2e2; color: #991b1b; }

.section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-color);
  margin-bottom: 6px;
}

.vector-row span {
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #1e293b;
  background: #f8fafc;
  padding: 4px 8px;
  border-radius: 8px;
}

.vector-row.small span {
  font-size: 11px;
}

@media (max-width: 1200px) {
  .meta-grid,
  .metric-grid,
  .param-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>