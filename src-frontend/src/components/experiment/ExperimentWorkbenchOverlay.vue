<template>
  <transition name="overlay-fade">
    <div v-if="visible" class="workbench-overlay">
      <div class="overlay-shell">
        <section class="summary-card">
          <div class="summary-head">
            <div class="summary-title">
              <span class="card-kicker">Case Summary</span>
              <strong>{{ caseTitle }}</strong>
            </div>
            <button class="close-btn" @click="$emit('close')">关闭</button>
          </div>
          <div class="summary-grid">
            <div class="summary-item">
              <span>任务</span>
              <strong>{{ taskName }}</strong>
            </div>
            <div class="summary-item">
              <span>场景</span>
              <strong>{{ scenarioName }}</strong>
            </div>
            <div class="summary-item">
              <span>架构</span>
              <strong>{{ architectureName }}</strong>
            </div>
            <div class="summary-item">
              <span>重复轮次</span>
              <strong>{{ repeatIndexText }}</strong>
            </div>
            <div class="summary-item">
              <span>触发策略</span>
              <strong>{{ triggerPolicy }}</strong>
            </div>
            <div class="summary-item">
              <span>评估窗口</span>
              <strong>{{ evaluationWindowText }}</strong>
            </div>
          </div>
          <div class="tag-row">
            <span class="case-tag">模板 {{ taskProfileText }}</span>
            <span class="case-tag">扰动 {{ disturbanceText }}</span>
            <span class="case-tag">重点 {{ expectedFocusText }}</span>
            <span class="case-tag">策略 {{ adaptationModeText }}</span>
            <span class="case-tag">环境 {{ environmentClassText }}</span>
            <span class="case-tag">障碍 {{ obstacleDensityText }}</span>
            <span class="case-tag">风场 {{ windLevelText }}</span>
            <span class="case-tag">链路 {{ linkQualityText }}</span>
            <span class="case-tag">传感 {{ sensorQualityText }}</span>
          </div>
        </section>

        <div class="panel-shell">
          <ExperimentWorkbenchPanel />
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { useDroneStore } from '@/store/drone'
import ExperimentWorkbenchPanel from './ExperimentWorkbenchPanel.vue'

defineProps({
  visible: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close'])

const droneStore = useDroneStore()

const taskName = computed(() => droneStore.experimentContext.task?.taskName || 'Idle')
const scenarioName = computed(() => droneStore.experimentContext.scenarioName || 'Scenario Default')
const architectureName = computed(() => droneStore.experimentContext.architecture?.displayName || 'Baseline Balanced')
const repeatIndexText = computed(() => {
  const value = droneStore.experimentContext.caseMeta?.repeatIndex
  return value === null || value === undefined ? '未指定' : `第 ${value} 轮`
})
const triggerPolicy = computed(() => droneStore.experimentContext.triggerPolicy || 'default trigger')
const evaluationWindowText = computed(() => {
  const value = droneStore.experimentContext.caseMeta?.evaluationWindowSec
  return value ? `${value}s` : '未指定'
})
const caseTitle = computed(() => {
  const planCaseId = droneStore.experimentContext.planCaseId || droneStore.experimentContext.caseId || 'CASE_PENDING'
  return `${planCaseId} · ${taskName.value} · ${scenarioName.value}`
})
const selectedCase = computed(() => {
  const caseId = droneStore.experimentContext.selectedPlanCaseId || droneStore.experimentContext.planCaseId
  return (droneStore.experimentContext.availableCases || []).find(item => item.case_id === caseId) || null
})
const taskProfileText = computed(() => selectedCase.value?.task_profile_id || taskName.value)
const disturbanceText = computed(() => selectedCase.value?.disturbance_profile || selectedCase.value?.scenario_name || scenarioName.value)
const expectedFocusText = computed(() => selectedCase.value?.expected_focus || 'reference')
const adaptationModeText = computed(() => selectedCase.value?.adaptation_mode || 'observe_only')
const environmentClassText = computed(() => selectedCase.value?.environment_class || droneStore.experimentContext.environmentClass || 'unknown')
const obstacleDensityText = computed(() => selectedCase.value?.obstacle_density || droneStore.experimentContext.obstacleDensity || 'unknown')
const windLevelText = computed(() => selectedCase.value?.wind_level || droneStore.experimentContext.windLevel || 'unknown')
const linkQualityText = computed(() => selectedCase.value?.link_quality || droneStore.experimentContext.linkQualityLevel || 'unknown')
const sensorQualityText = computed(() => selectedCase.value?.sensor_quality || droneStore.experimentContext.sensorQualityLevel || 'unknown')
</script>

<style scoped>
.workbench-overlay {
  position: absolute;
  inset: 0;
  z-index: 25;
  background: rgba(236, 242, 248, 0.94);
  backdrop-filter: blur(8px);
  padding: 10px;
  overflow: hidden;
}

.overlay-shell {
  height: 100%;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 6px;
}

.summary-card,
.panel-shell {
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  box-shadow: var(--shadow-md);
}

.card-kicker {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent-color);
}

.close-btn {
  border: 1px solid rgba(37, 99, 235, 0.24);
  background: rgba(37, 99, 235, 0.08);
  color: var(--accent-color);
  border-radius: 10px;
  height: 34px;
  padding: 0 14px;
  font-weight: 600;
  cursor: pointer;
}

.summary-card {
  padding: 8px 10px 10px;
}

.summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.summary-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.summary-head strong {
  color: var(--text-primary);
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
}

.summary-item {
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--panel-muted);
  border: 1px solid var(--border-light);
  min-width: 0;
}

.summary-item span {
  display: block;
  margin-bottom: 2px;
  font-size: 10px;
  color: var(--text-tertiary);
}

.summary-item strong {
  display: block;
  color: var(--text-primary);
  font-size: 11px;
  line-height: 1.2;
  word-break: break-word;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}

.case-tag {
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.14);
  color: var(--accent-color);
  font-size: 10px;
}

.panel-shell {
  min-height: 0;
  overflow: hidden;
}

.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.2s ease;
}

.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

@media (max-width: 1280px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>