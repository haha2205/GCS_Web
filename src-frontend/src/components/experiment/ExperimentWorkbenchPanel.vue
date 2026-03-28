<template>
  <div class="workbench-panel">
    <section class="section-alert" :class="alertToneClass">
      <div class="alert-summary">
        <span class="section-kicker">Analysis Package</span>
        <strong>{{ analysisBannerTitle }}</strong>
        <span class="alert-meta">{{ packageStatusText }}</span>
      </div>
      <div class="summary-pills">
        <div class="summary-pill">
          <span>标准文件</span>
          <strong>{{ readyFileCount }}/5</strong>
        </div>
        <div class="summary-pill">
          <span>评估分数</span>
          <strong>{{ finalCompositeScoreText }}</strong>
        </div>
        <div class="summary-pill summary-pill-wide">
          <span>推荐架构</span>
          <strong>{{ recommendedArchitectureLabel }}</strong>
        </div>
      </div>
    </section>

    <section class="workbench-grid">
      <article class="workbench-card analysis-card">
        <div class="card-head">
          <div>
            <span class="section-kicker">DSM + Evaluation</span>
            <h3>结构与评分视图</h3>
          </div>
          <span class="card-meta">thesis-aligned summaries</span>
        </div>

        <div class="overview-strip">
          <div v-for="item in analysisOverviewTiles" :key="item.label" class="overview-tile">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div class="chart-grid analysis-chart-grid">
          <section class="chart-panel">
            <div class="subpanel-head">
              <strong>DSM 结构信号</strong>
              <span>{{ dsmStateText }}</span>
            </div>
            <div v-if="hasDsmChart" class="chart-shell">
              <EChartWrapper
                title="结构强度曲线"
                unit="%"
                :categories="dsmChartCategories"
                :series="dsmChartSeries"
                :yMin="0"
                :yMax="100"
                :height="190"
              />
            </div>
            <div v-else class="empty-state">
              当前没有形成 DSM 汇总结果。空录制场景下这属于预期，因为标准文件只有表头，没有可分析数据行。
            </div>
          </section>

          <section class="chart-panel">
            <div class="subpanel-head">
              <strong>五域压力轮廓</strong>
              <span>{{ evaluationStateText }}</span>
            </div>
            <div v-if="hasEvaluationDomainChart" class="chart-shell">
              <EChartWrapper
                title="Domain Pressure"
                unit="%"
                chartType="radar"
                :radarIndicator="evaluationRadarIndicators"
                :series="evaluationChartSeries"
                :height="190"
              />
            </div>
            <div v-else class="empty-state">
              评估结果尚未产出。只有当 DSM 报告生成后，才会出现五域评分与基线对比。
            </div>
          </section>

          <section class="chart-panel chart-panel-wide">
            <div class="subpanel-head">
              <strong>基线差值曲线</strong>
              <span>{{ baselineDeltaHint }}</span>
            </div>
            <div v-if="hasBaselineDeltaChart" class="chart-shell">
              <EChartWrapper
                title="Baseline Delta"
                unit="delta"
                chartType="bar"
                :categories="baselineDeltaCategories"
                :series="baselineDeltaSeries"
                :yMin="baselineDeltaMin"
                :yMax="baselineDeltaMax"
                :height="170"
              />
            </div>
            <div v-else class="empty-state compact-empty">
              基线差值还不可用；当前阶段只能确认评估流程是否完成，不能得出相对基线的提升或退化趋势。
            </div>
          </section>
        </div>
      </article>

      <article class="workbench-card optimization-card">
        <div class="card-head">
          <div>
            <span class="section-kicker">Optimization</span>
            <h3>优化结果与候选曲线</h3>
          </div>
          <span class="card-meta">candidate frontier</span>
        </div>

        <div class="overview-strip optimization-overview-strip">
          <div class="overview-tile overview-tile-wide">
            <span>当前基线</span>
            <strong>{{ currentArchitectureLabel }}</strong>
          </div>
          <div class="overview-tile overview-tile-wide emphasis-tile">
            <span>推荐输出</span>
            <strong>{{ recommendedArchitectureLabel }}</strong>
          </div>
          <div class="overview-tile">
            <span>Score Delta</span>
            <strong>{{ scoreDeltaText }}</strong>
          </div>
          <div class="overview-tile">
            <span>Cross Delta</span>
            <strong>{{ crossDeltaText }}</strong>
          </div>
          <div class="overview-tile">
            <span>Power Delta</span>
            <strong>{{ powerDeltaText }}</strong>
          </div>
          <div class="overview-tile" :class="recommendation.constraintPass === false ? 'risk-tile' : ''">
            <span>Constraint</span>
            <strong>{{ constraintPassText }}</strong>
          </div>
        </div>

        <div class="chart-grid optimization-chart-grid">
          <section class="chart-panel">
            <div class="subpanel-head">
              <strong>候选综合评分曲线</strong>
              <span>{{ optimizationStateText }}</span>
            </div>
            <div v-if="hasOptimizationScoreChart" class="chart-shell">
              <EChartWrapper
                title="Candidate Scores"
                unit="score"
                chartType="bar"
                :categories="optimizationChartCategories"
                :series="optimizationChartSeries"
                :height="190"
              />
            </div>
            <div v-else class="empty-state">
              当前还没有可绘制的候选评分曲线。空录制只会停留在候选占位态，这也是预期行为。
            </div>
          </section>

          <section class="chart-panel">
            <div class="subpanel-head">
              <strong>候选资源代价轮廓</strong>
              <span>cross count vs power</span>
            </div>
            <div v-if="hasOptimizationResourceChart" class="chart-shell">
              <EChartWrapper
                title="Resource Pressure"
                unit="%"
                chartType="bar"
                :categories="optimizationChartCategories"
                :series="optimizationResourceSeries"
                :yMin="0"
                :yMax="100"
                :height="190"
                :showLegend="true"
              />
            </div>
            <div v-else class="empty-state">
              候选资源画像尚未形成，说明优化器只回传了候选名册，还没有可比较的 cross 或 power 结果。
            </div>
          </section>

          <section class="chart-panel chart-panel-wide">
            <div class="subpanel-head">
              <strong>优化证据与风险</strong>
              <span>{{ evidenceCountText }}</span>
            </div>
            <div class="evidence-chips">
              <span v-for="item in evidenceChips" :key="item" class="evidence-chip">{{ item }}</span>
            </div>
            <p class="risk-text">{{ riskText }}</p>

            <div class="candidate-grid">
              <div v-for="candidate in normalizedCandidates" :key="candidate.id" class="candidate-item">
                <div class="candidate-copy">
                  <strong>{{ candidate.name }}</strong>
                  <small>{{ candidate.group }}</small>
                </div>
                <div class="candidate-metrics">
                  <span>{{ candidate.scoreText }}</span>
                  <span>{{ candidate.crossText }}</span>
                  <span>{{ candidate.powerText }}</span>
                </div>
                <span class="candidate-status" :class="candidate.constraintPass === false ? 'candidate-score-risk' : ''">
                  {{ candidate.statusText }}
                </span>
              </div>
            </div>
          </section>
        </div>
      </article>
    </section>

    <section class="status-strip">
      <article class="strip-card">
        <div class="strip-head">
          <span class="section-kicker">Pipeline</span>
          <span class="strip-meta">{{ pipelineMeta }}</span>
        </div>
        <div class="mini-steps">
          <div v-for="step in pipelineSteps" :key="step.key" class="mini-step">
            <span class="mini-label">{{ step.label }}</span>
            <div class="mini-track">
              <span class="mini-fill" :class="statusClass(step.status)"></span>
            </div>
            <span class="mini-status">{{ statusText(step.status) }}</span>
          </div>
        </div>
      </article>

      <article class="strip-card">
        <div class="strip-head">
          <span class="section-kicker">Standard Files</span>
          <span class="strip-meta">{{ readyFileCount }}/5 ready</span>
        </div>
        <div class="file-chips">
          <div v-for="item in standardFiles" :key="item.key" class="file-chip" :class="statusClass(item.status)">
            <strong>{{ item.shortLabel }}</strong>
            <span>{{ statusText(item.status) }}</span>
          </div>
        </div>
      </article>

      <article class="strip-card">
        <div class="strip-head">
          <span class="section-kicker">Figure Ledger</span>
          <span class="strip-meta">{{ figureLedgerMeta }}</span>
        </div>
        <div class="figure-grid">
          <div v-for="item in figureLedgerTiles" :key="item.label" class="figure-chip" :class="statusClass(item.status)">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'
import EChartWrapper from '@/components/monitor/EChartWrapper.vue'

const droneStore = useDroneStore()

const pipeline = computed(() => droneStore.pipelineStatus || {})
const dsm = computed(() => droneStore.dsmSummary || {})
const evaluation = computed(() => droneStore.evaluationSummary || {})
const recommendation = computed(() => droneStore.architectureRecommendation || {})
const experimentContext = computed(() => droneStore.experimentContext || {})
const figureAssetStatus = computed(() => droneStore.figureAssetStatus || {})

const analysisBannerTitle = computed(() => {
  if (pipeline.value.standardFilesStatus === 'ready') {
    return '标准分析包已就绪'
  }
  if (pipeline.value.standardFilesStatus === 'empty') {
    return '标准文件已生成但无有效数据'
  }
  if (pipeline.value.dsmStatus === 'blocked') {
    return '标准分析包不完整，DSM 已阻断'
  }
  return '标准分析包尚未形成'
})

const alertToneClass = computed(() => statusClass(pipeline.value.standardFilesStatus))
const packageStatusText = computed(() => {
  if (pipeline.value.standardFilesStatus === 'ready') {
    return 'ready for dsm'
  }
  if (pipeline.value.standardFilesStatus === 'empty') {
    return 'header-only dataset'
  }
  if (pipeline.value.dsmStatus === 'blocked') {
    return 'blocked by standardization'
  }
  return 'raw/views only'
})

const pipelineSteps = computed(() => [
  { key: 'raw', label: '原始录制', status: pipeline.value.rawRecordingStatus || 'waiting' },
  { key: 'standard', label: '标准导出', status: pipeline.value.standardFilesStatus || 'missing' },
  { key: 'dsm', label: 'DSM', status: pipeline.value.dsmStatus && pipeline.value.dsmStatus !== 'waiting' ? pipeline.value.dsmStatus : 'planned' },
  { key: 'evaluation', label: '评估', status: pipeline.value.evaluationStatus && pipeline.value.evaluationStatus !== 'waiting' ? pipeline.value.evaluationStatus : 'planned' },
  { key: 'optimization', label: '优化', status: pipeline.value.optimizationStatus && pipeline.value.optimizationStatus !== 'waiting' ? pipeline.value.optimizationStatus : 'planned' },
  { key: 'archive', label: '归档', status: pipeline.value.archiveStatus && pipeline.value.archiveStatus !== 'waiting' ? pipeline.value.archiveStatus : 'planned' }
])

const standardFiles = computed(() => [
  { key: 'fcsTelemetry', shortLabel: 'FCS', status: pipeline.value.standardFiles?.fcsTelemetry || 'missing' },
  { key: 'planningTelemetry', shortLabel: 'Planning', status: pipeline.value.standardFiles?.planningTelemetry || 'missing' },
  { key: 'radarData', shortLabel: 'Radar', status: pipeline.value.standardFiles?.radarData || 'missing' },
  { key: 'busTraffic', shortLabel: 'Bus', status: pipeline.value.standardFiles?.busTraffic || 'missing' },
  { key: 'cameraData', shortLabel: 'Camera', status: pipeline.value.standardFiles?.cameraData || 'missing' }
])

const readyFileCount = computed(() => standardFiles.value.filter((item) => item.status === 'ready').length)
const currentArchitectureLabel = computed(() => recommendation.value.currentArchitecture || droneStore.experimentContext.architecture.displayName || 'Baseline Balanced')
const recommendedArchitectureLabel = computed(() => recommendation.value.recommendedArchitecture || '待评估')
const scoreDeltaText = computed(() => formatSignedNumber(recommendation.value.scoreDelta, 3, '--'))
const crossDeltaText = computed(() => formatSignedNumber(recommendation.value.crossCountDelta, 0, '--'))
const powerDeltaText = computed(() => formatSignedNumber(recommendation.value.powerDelta, 3, '-- W'))
const constraintPassText = computed(() => {
  if (recommendation.value.constraintPass === true) {
    return 'pass'
  }
  if (recommendation.value.constraintPass === false) {
    return 'risk'
  }
  return '--'
})

const evidenceChips = computed(() => {
  const evidence = recommendation.value.triggerEvidence || []
  return evidence.length ? evidence : ['awaiting standard files', 'awaiting DSM', 'awaiting evaluation']
})
const evidenceCountText = computed(() => `${evidenceChips.value.length} evidence tags`)
const riskText = computed(() => recommendation.value.riskText || '当前缺少可用于分析的标准文件，推荐结果不可用。')
const pipelineMeta = computed(() => pipeline.value.updatedAt ? new Date(pipeline.value.updatedAt).toLocaleTimeString() : 'awaiting backend')
const optimizationStateText = computed(() => recommendation.value.recommendedArchitecture ? 'recommendation ready' : 'awaiting optimizer')
const figureBatchIdText = computed(() => resolveFigureValue('figureBatchId'))
const figureBatchGroupText = computed(() => resolveFigureValue('figureBatchGroup'))
const figureLedgerRangeText = computed(() => resolveFigureValue('figureLedgerRange'))
const experimentTypeText = computed(() => resolveFigureValue('experimentType'))
const chapterTargetText = computed(() => resolveFigureValue('chapterTarget'))
const lawValidationScopeText = computed(() => resolveFigureValue('lawValidationScope'))
const analysisRunIdText = computed(() => resolveFigureValue('analysisRunId'))
const figureAssetReady = computed(() => {
  const value = figureAssetStatus.value.figureAssetReady ?? evaluation.value.figureAssetReady ?? recommendation.value.figureAssetReady ?? dsm.value.figureAssetReady ?? pipeline.value.figureAssetReady
  return value === true
})
const figureLedgerMeta = computed(() => {
  if (analysisRunIdText.value !== '--') {
    return analysisRunIdText.value
  }
  if (figureBatchIdText.value !== '--') {
    return 'batch bound'
  }
  return 'awaiting batch binding'
})
const figureLedgerTiles = computed(() => [
  {
    label: 'Batch',
    value: figureBatchIdText.value,
    status: figureBatchIdText.value === '--' ? 'missing' : 'ready'
  },
  {
    label: 'Group',
    value: figureBatchGroupText.value,
    status: figureBatchGroupText.value === '--' ? 'waiting' : 'ready'
  },
  {
    label: 'Ledger',
    value: figureLedgerRangeText.value,
    status: figureLedgerRangeText.value === '--' ? 'waiting' : 'ready'
  },
  {
    label: 'Type',
    value: experimentTypeText.value,
    status: experimentTypeText.value === '--' ? 'waiting' : 'ready'
  },
  {
    label: 'Chapter',
    value: chapterTargetText.value,
    status: chapterTargetText.value === '--' ? 'waiting' : 'ready'
  },
  {
    label: 'Law',
    value: lawValidationScopeText.value,
    status: lawValidationScopeText.value === '--' ? 'waiting' : 'ready'
  },
  {
    label: 'Assets',
    value: figureAssetReady.value ? 'ready' : 'pending',
    status: figureAssetReady.value ? 'ready' : figureBatchIdText.value === '--' ? 'missing' : 'pending'
  }
])

const hasDsmChart = computed(() => {
  return [dsm.value.nodeCount, dsm.value.edgeCount, dsm.value.crossModuleInteractions, dsm.value.totalBusBytes, dsm.value.avgCrossLatency]
    .some((value) => Number.isFinite(Number(value)) && Number(value) > 0)
})

const analysisOverviewTiles = computed(() => [
  { label: 'Nodes', value: formatCompactNumber(dsm.value.nodeCount) },
  { label: 'Edges', value: formatCompactNumber(dsm.value.edgeCount) },
  { label: 'Cross', value: formatCompactNumber(dsm.value.crossModuleInteractions) },
  { label: 'Latency', value: formatCompactNumber(dsm.value.avgCrossLatency, ' ms') },
  { label: 'Score', value: formatCompactNumber(evaluation.value.finalCompositeScore) },
  { label: 'Violations', value: formatCompactNumber(evaluation.value.constraintViolationCount) }
])

const dsmChartCategories = ['Nodes', 'Edges', 'Cross', 'Latency', 'Traffic']
const dsmChartSeries = computed(() => [{
  name: 'DSM signal',
  data: [
    normalizePercent(dsm.value.nodeCount, 12),
    normalizePercent(dsm.value.edgeCount, 24),
    normalizePercent(dsm.value.crossModuleInteractions, 16),
    normalizePercent(dsm.value.avgCrossLatency, 120),
    normalizePercent(dsm.value.totalBusBytes, 1000000)
  ],
  smooth: true,
  areaStyle: { color: 'rgba(37, 99, 235, 0.14)' },
  lineStyle: { color: '#2563eb', width: 2 },
  itemStyle: { color: '#2563eb' }
}])
const dsmStateText = computed(() => hasDsmChart.value ? 'summary ready' : statusText(pipeline.value.dsmStatus || 'blocked'))

const evaluationDomainSignals = computed(() => {
  const domainScores = evaluation.value.domainScores || {}
  return [
    {
      label: '感知',
      raw: safeMetric(domainScores.perception?.perception_latency_ms),
      chartValue: normalizePercent(domainScores.perception?.perception_latency_ms, 200)
    },
    {
      label: '决策',
      raw: safeMetric(domainScores.decision?.planning_time_ms),
      chartValue: normalizePercent(domainScores.decision?.planning_time_ms, 200)
    },
    {
      label: '控制',
      raw: safeMetric(domainScores.control?.control_jitter_ms),
      chartValue: normalizePercent(domainScores.control?.control_jitter_ms, 50)
    },
    {
      label: '通信',
      raw: safeMetric(domainScores.communication?.cross_latency_ms),
      chartValue: normalizePercent(domainScores.communication?.cross_latency_ms, 120)
    },
    {
      label: '安全',
      raw: safeMetric(domainScores.safety?.system_power_w),
      chartValue: normalizePercent(domainScores.safety?.system_power_w, 100)
    }
  ]
})

const hasEvaluationDomainChart = computed(() => evaluationDomainSignals.value.some((item) => item.raw !== null))
const evaluationRadarIndicators = computed(() => evaluationDomainSignals.value.map((item) => ({
  name: item.label,
  max: 100
})))
const evaluationChartSeries = computed(() => [{
  name: 'domain pressure',
  data: evaluationDomainSignals.value.map((item) => item.chartValue),
  smooth: true,
  areaStyle: { color: 'rgba(245, 158, 11, 0.16)' },
  lineStyle: { color: '#f59e0b', width: 2 },
  itemStyle: { color: '#f59e0b' }
}])
const evaluationStateText = computed(() => {
  if (evaluation.value.evaluationReady) {
    return 'evaluation ready'
  }
  return statusText(pipeline.value.evaluationStatus || 'blocked')
})
const finalCompositeScoreText = computed(() => formatCompactNumber(evaluation.value.finalCompositeScore))

const baselineDeltaCategories = ['Score', 'Violations', 'Cross', 'Power']
const baselineDeltaValues = computed(() => [
  safeMetric(evaluation.value.baselineDelta?.final_composite_score),
  safeMetric(evaluation.value.baselineDelta?.constraint_violation_count),
  safeMetric(evaluation.value.baselineDelta?.cross_count),
  safeMetric(evaluation.value.baselineDelta?.system_power_w)
])
const hasBaselineDeltaChart = computed(() => baselineDeltaValues.value.some((value) => value !== null && value !== 0))
const baselineDeltaSeries = computed(() => [{
  name: 'baseline delta',
  data: baselineDeltaValues.value.map((value) => value ?? 0),
  itemStyle: { color: '#0ea5e9' }
}])
const baselineDeltaExtent = computed(() => {
  const numeric = baselineDeltaValues.value.filter((value) => value !== null)
  if (!numeric.length) {
    return { min: -1, max: 1 }
  }
  const min = Math.min(...numeric)
  const max = Math.max(...numeric)
  if (min === max) {
    const padding = Math.abs(min) > 0 ? Math.abs(min) * 0.25 : 1
    return { min: min - padding, max: max + padding }
  }
  const padding = Math.max((max - min) * 0.15, 0.5)
  return { min: min - padding, max: max + padding }
})
const baselineDeltaMin = computed(() => baselineDeltaExtent.value.min)
const baselineDeltaMax = computed(() => baselineDeltaExtent.value.max)
const baselineDeltaHint = computed(() => hasBaselineDeltaChart.value ? 'candidate vs baseline' : 'awaiting delta output')

const normalizedCandidates = computed(() => {
  const rawCandidates = recommendation.value.candidates || []
  return rawCandidates.slice(0, 6).map((candidate, index) => {
    const score = safeMetric(candidate.score ?? candidate.predicted_score)
    const crossCount = safeMetric(candidate.cross_count)
    const powerW = safeMetric(candidate.power_w)
    return {
      id: candidate.profile_id || candidate.id || `candidate_${index}`,
      name: candidate.profile_name || candidate.name || candidate.display_name || candidate.id || 'Candidate',
      group: candidate.profile_group || candidate.group || candidate.solution_type || candidate.mapping_profile || 'profile pending',
      score,
      crossCount,
      powerW,
      scoreText: score !== null ? `score ${score.toFixed(3)}` : (candidate.status === 'awaiting_evaluation' ? 'score 待评估' : 'score 待回传'),
      crossText: crossCount !== null ? `cross ${Math.round(crossCount)}` : 'cross --',
      powerText: powerW !== null ? `power ${powerW.toFixed(1)} W` : 'power --',
      statusText: candidate.constraint_pass === false
        ? '约束风险'
        : score !== null
          ? '已评分'
          : '待评估',
      constraintPass: candidate.constraint_pass
    }
  })
})

const optimizationChartCategories = computed(() => normalizedCandidates.value.map((item) => item.name))
const hasOptimizationScoreChart = computed(() => normalizedCandidates.value.some((item) => item.score !== null))
const optimizationChartSeries = computed(() => [{
  name: 'candidate score',
  data: normalizedCandidates.value.map((item) => item.score ?? 0),
  itemStyle: { color: '#10b981' }
}])

const optimizationCrossMax = computed(() => getPositiveMax(normalizedCandidates.value.map((item) => item.crossCount), 1))
const optimizationPowerMax = computed(() => getPositiveMax(normalizedCandidates.value.map((item) => item.powerW), 1))
const hasOptimizationResourceChart = computed(() => normalizedCandidates.value.some((item) => item.crossCount !== null || item.powerW !== null))
const optimizationResourceSeries = computed(() => [
  {
    name: 'cross pressure',
    data: normalizedCandidates.value.map((item) => item.crossCount !== null ? normalizeAgainstMax(item.crossCount, optimizationCrossMax.value) : 0),
    itemStyle: { color: '#f43f5e' }
  },
  {
    name: 'power pressure',
    data: normalizedCandidates.value.map((item) => item.powerW !== null ? normalizeAgainstMax(item.powerW, optimizationPowerMax.value) : 0),
    itemStyle: { color: '#6366f1' }
  }
])

function safeMetric(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function getPositiveMax(values, fallback = 1) {
  const numeric = values.filter((value) => Number.isFinite(Number(value)) && Number(value) > 0).map((value) => Number(value))
  return numeric.length ? Math.max(...numeric) : fallback
}

function normalizeAgainstMax(value, maxValue) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0 || maxValue <= 0) {
    return 0
  }
  return Math.min(100, (numeric / maxValue) * 100)
}

function normalizePercent(value, maxValue) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return 0
  }
  return Math.min(100, (numeric / maxValue) * 100)
}

function formatCompactNumber(value, suffix = '') {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '--'
  }
  if (Math.abs(numeric) >= 1000) {
    return `${numeric.toFixed(0)}${suffix}`
  }
  if (Math.abs(numeric) >= 100) {
    return `${numeric.toFixed(1)}${suffix}`
  }
  return `${numeric.toFixed(3).replace(/\.000$/, '')}${suffix}`
}

function formatSignedNumber(value, precision = 3, fallback = '--') {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return fallback
  }
  const absValue = precision === 0 ? Math.round(Math.abs(numeric)) : Math.abs(numeric).toFixed(precision)
  return `${numeric >= 0 ? '+' : '-'}${absValue}`
}

function resolveFigureValue(fieldName) {
  const candidates = [
    figureAssetStatus.value?.[fieldName],
    recommendation.value?.[fieldName],
    evaluation.value?.[fieldName],
    dsm.value?.[fieldName],
    experimentContext.value?.[fieldName]
  ]
  const resolved = candidates.find((value) => value !== undefined && value !== null && value !== '')
  return resolved ?? '--'
}

function statusText(status) {
  const map = {
    waiting: '等待',
    running: '运行中',
    ready: '已就绪',
    failed: '失败',
    missing: '未产出',
    empty: '空数据',
    raw_only: '仅原始层',
    planned: '后续阶段',
    pending: '待触发',
    blocked: '被阻断'
  }
  return map[status] || '等待'
}

function statusClass(status) {
  return {
    'status-ready': status === 'ready',
    'status-running': status === 'running',
    'status-warn': status === 'raw_only' || status === 'waiting' || status === 'planned' || status === 'pending' || status === 'blocked' || status === 'empty',
    'status-missing': status === 'missing' || status === 'failed'
  }
}
</script>

<style scoped>
.workbench-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px;
  background: linear-gradient(180deg, #f6f9fd 0%, #edf3fa 100%);
}

.section-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: #ffffff;
}

.alert-summary {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.section-kicker {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-color);
}

.section-alert strong,
.card-head h3,
.overview-tile strong,
.figure-chip strong,
.candidate-copy strong {
  color: var(--text-primary);
}

.alert-meta,
.card-meta,
.strip-meta,
.subpanel-head span {
  font-size: 10px;
  color: var(--text-tertiary);
}

.summary-pills,
.overview-strip {
  display: grid;
  gap: 6px;
}

.summary-pills {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  min-width: 420px;
}

.summary-pill,
.overview-tile,
.figure-chip,
.file-chip,
.candidate-item {
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: rgba(248, 250, 252, 0.96);
}

.summary-pill,
.overview-tile,
.figure-chip {
  padding: 8px 10px;
  display: grid;
  gap: 4px;
}

.summary-pill span,
.overview-tile span,
.figure-chip span,
.mini-label,
.mini-status,
.risk-text,
.candidate-copy small,
.candidate-metrics span,
.file-chip span {
  color: var(--text-secondary);
  font-size: 10px;
}

.summary-pill-wide {
  min-width: 0;
}

.workbench-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(0, 1fr);
  gap: 6px;
}

.workbench-card,
.strip-card {
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 8px;
  box-shadow: var(--shadow-sm);
}

.card-head,
.strip-head,
.subpanel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-head {
  margin-bottom: 8px;
}

.card-head h3 {
  margin: 2px 0 0;
  font-size: 13px;
}

.overview-strip {
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin-bottom: 8px;
}

.optimization-overview-strip {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.overview-tile-wide {
  grid-column: span 2;
}

.emphasis-tile {
  background: rgba(237, 247, 255, 0.96);
}

.risk-tile {
  border-color: rgba(220, 38, 38, 0.18);
  background: rgba(220, 38, 38, 0.06);
}

.chart-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 8px;
}

.analysis-chart-grid,
.optimization-chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(0, 1fr);
}

.chart-panel {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: rgba(248, 250, 252, 0.82);
}

.chart-panel-wide {
  grid-column: 1 / -1;
}

.subpanel-head strong {
  font-size: 12px;
  color: var(--text-primary);
}

.chart-shell {
  min-height: 0;
}

.empty-state {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.1);
  background: rgba(37, 99, 235, 0.05);
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.45;
}

.compact-empty {
  margin-top: 0;
}

.evidence-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.evidence-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  color: var(--accent-color);
  font-size: 10px;
  font-weight: 600;
}

.risk-text {
  margin: 0;
  line-height: 1.45;
}

.candidate-grid {
  display: grid;
  gap: 6px;
  overflow-y: auto;
}

.candidate-item {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 10px;
}

.candidate-copy small {
  display: block;
  margin-top: 2px;
}

.candidate-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.candidate-status {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
}

.candidate-score-risk {
  color: #b91c1c;
}

.status-strip {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr) minmax(0, 1fr);
  gap: 6px;
}

.figure-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}

.mini-steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
}

.mini-step {
  display: grid;
  gap: 4px;
}

.mini-track {
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.16);
}

.mini-fill {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 999px;
}

.file-chips {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
}

.file-chip {
  display: grid;
  gap: 2px;
  padding: 6px 8px;
}

.file-chip strong {
  font-size: 10px;
  color: var(--text-primary);
}

.status-ready {
  border-color: rgba(22, 163, 74, 0.2);
  background: rgba(22, 163, 74, 0.08);
  color: #166534;
}

.status-running {
  border-color: rgba(37, 99, 235, 0.18);
  background: rgba(37, 99, 235, 0.08);
  color: #1d4ed8;
}

.status-warn {
  border-color: rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
}

.status-missing {
  border-color: rgba(220, 38, 38, 0.18);
  background: rgba(220, 38, 38, 0.08);
  color: #b91c1c;
}

@media (max-width: 1500px) {
  .workbench-grid,
  .status-strip,
  .analysis-chart-grid,
  .optimization-chart-grid {
    grid-template-columns: 1fr;
  }

  .chart-panel-wide,
  .overview-tile-wide {
    grid-column: auto;
  }
}

@media (max-width: 1200px) {
  .summary-pills,
  .overview-strip,
  .optimization-overview-strip,
  .figure-grid,
  .file-chips,
  .mini-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 800px) {
  .section-alert,
  .alert-summary,
  .card-head,
  .subpanel-head,
  .strip-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-pills,
  .overview-strip,
  .optimization-overview-strip,
  .figure-grid,
  .file-chips,
  .mini-steps {
    grid-template-columns: 1fr;
    min-width: 0;
  }

  .candidate-item {
    grid-template-columns: 1fr;
  }
}
</style>
