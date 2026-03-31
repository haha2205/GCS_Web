<template>
  <div class="bottom-bar">
    <div class="bottom-grid">
      <div class="left-panels">
        <div class="planning-console-section section-column">
          <div class="console-header">
            <span class="console-title">PLANNING COMMAND</span>
            <div class="planning-header-actions">
              <span class="planning-summary">{{ currentCmdIdxInfo }}</span>
              <button class="planning-btn primary compact-header-btn" @click="sendPlanningCommand" :disabled="!droneStore.canSendCommands">发送</button>
              <button class="planning-btn compact-header-btn" @click="resetPlanning">重置</button>
            </div>
          </div>

          <div class="planning-grid">
            <label class="planning-field">
              <span>X</span>
              <input v-model.number="targetPos.x" type="number" class="planning-input" step="1" />
            </label>
            <label class="planning-field">
              <span>Y</span>
              <input v-model.number="targetPos.y" type="number" class="planning-input" step="1" />
            </label>
            <label class="planning-field">
              <span>Z</span>
              <input v-model.number="targetPos.z" type="number" class="planning-input" step="1" min="0" />
            </label>
            <label class="planning-field speed-field">
              <span>速度</span>
              <input v-model.number="cruiseSpeed" type="number" class="planning-input" step="0.5" min="0" max="30" />
            </label>
            <label class="mission-toggle">
              <input type="checkbox" v-model="enableMission" />
              <span>使能任务</span>
            </label>
          </div>
        </div>

        <div class="command-column">
          <div class="critical-console-section">
            <div class="console-header">
              <span class="console-title">CRITICAL CMDIDX</span>
            </div>
            <div class="critical-actions compact-actions" :class="{ disabled: !droneStore.canSendCommands }">
              <button
                v-for="cmd in criticalBottomCommands"
                :key="cmd.id"
                class="quick-command-btn compact-btn"
                :class="[`tone-${cmd.tone}`, { disabled: !droneStore.canSendCommands }]"
                :title="cmd.name"
                @click="triggerCriticalCommand(cmd)"
              >
                <span class="quick-command-label">{{ cmd.name }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="sys-console-section section-column">
        <div class="console-header">
          <span class="console-title">SYSTEM LOG</span>
          <button class="clear-btn" @click="clearSysLog" title="清空日志">清空</button>
        </div>
        <div class="console-content" ref="sysLogRef">
          <div
            v-for="(log, i) in sysLogs"
            :key="i"
            class="log-line"
            :class="'log-' + log.level"
          >
            <span class="log-icon">{{ log.icon }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useDroneStore } from '@/store/drone'
import { criticalBottomCommands } from '@/constants/commandConfig'

const droneStore = useDroneStore()

const sysLogRef = ref(null)
const targetPos = ref({ x: 100, y: 100, z: 10 })
const cruiseSpeed = ref(5)
const enableMission = ref(false)
const seqIdCounter = ref(0)

const currentCmdIdx = computed(() => droneStore.activeCommandIdx)
const sysLogs = computed(() => droneStore.displaySystemLogs)

watch(() => sysLogs.value.length, () => {
  setTimeout(() => {
    if (sysLogRef.value) {
      sysLogRef.value.scrollTop = sysLogRef.value.scrollHeight
    }
  }, 80)
})

const currentCmdIdxInfo = computed(() => {
  if (currentCmdIdx.value === 0) return 'CmdIdx: 无'
  const cmdMap = {
    1: '外控', 2: '混控', 3: '程控', 4: '爬升', 5: '巡航', 6: '下降', 7: '解除定高', 8: '航向保持',
    9: '左盘旋', 10: '右盘旋', 11: '航向锁定', 12: '发动机启动', 13: '发动机停止', 14: '自动起飞',
    15: '自动着陆', 16: '悬停', 17: '复原', 18: '预控', 19: '地速飞行', 20: '空速飞行', 21: '起飞准备',
    22: '人工起飞', 23: '人工着陆', 24: '避障开', 25: '避障关'
  }
  return `CmdIdx ${currentCmdIdx.value} ${cmdMap[currentCmdIdx.value] || ''}`
})

const addSysLog = (message, level = 'info') => droneStore.addLog(message, level)

const triggerCriticalCommand = async (cmd) => {
  if (!droneStore.canSendCommands) {
    addSysLog('WS或UDP未就绪，无法发送关键指令', 'warning')
    return
  }

  if (cmd.confirm && !window.confirm(cmd.confirm)) {
    return
  }

  try {
    const result = await droneStore.sendRemoteCommand(cmd.id, cmd.name)
    if (result?.status === 'success') {
      const level = cmd.tone === 'danger' ? 'warning' : cmd.tone === 'success' ? 'success' : 'info'
      addSysLog(`${cmd.name}指令已发送`, level)
    }
  } catch (error) {
    addSysLog(`${cmd.name}失败: ${error.message}`, 'error')
  }
}

const sendPlanningCommand = async () => {
  if (!droneStore.canSendCommands) {
    addSysLog('WS或UDP未就绪，无法发送规划指令', 'warning')
    return
  }

  try {
    seqIdCounter.value = (seqIdCounter.value + 1) % 1000000
    const result = await droneStore.sendCommandREST('gcs_command', {
      seqId: seqIdCounter.value,
      targetX: targetPos.value.x,
      targetY: targetPos.value.y,
      targetZ: targetPos.value.z,
      cruiseSpeed: cruiseSpeed.value,
      enable: enableMission.value ? 1 : 0,
      cmdId: currentCmdIdx.value
    })

    if (result?.status === 'success') {
      addSysLog(`规划指令已发送: (${targetPos.value.x}, ${targetPos.value.y}, ${targetPos.value.z}) ${cruiseSpeed.value}m/s`, 'success')
    } else {
      throw new Error(result?.message || '发送失败')
    }
  } catch (error) {
    addSysLog(`规划发送失败: ${error.message}`, 'error')
  }
}

const resetPlanning = () => {
  targetPos.value = { x: 100, y: 100, z: 10 }
  cruiseSpeed.value = 5
  enableMission.value = false
  addSysLog('规划指令已重置', 'info')
}

const clearSysLog = () => {
  droneStore.clearLogs()
}
</script>

<style scoped>
.bottom-bar {
  box-sizing: border-box;
  height: 100%;
  padding: 6px 12px;
  background: var(--surface-secondary);
  border-top: 1px solid var(--border-color);
  overflow: hidden;
}

.bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(300px, 0.9fr);
  gap: 10px;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.left-panels {
  display: grid;
  grid-template-columns: minmax(320px, 1.1fr) minmax(420px, 1.2fr);
  gap: 10px;
  min-width: 0;
  min-height: 0;
}

.section-column,
.command-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  min-height: 0;
}

.critical-console-section,
.planning-console-section,
.sys-console-section {
  background: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.critical-console-section,
.planning-console-section,
.sys-console-section {
  flex: 1;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 8px;
  background: var(--surface-elevated);
  border-bottom: 1px solid var(--border-soft);
}

.console-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent-color);
  font-family: 'Roboto Mono', monospace;
}

.planning-summary {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'Roboto Mono', monospace;
}

.planning-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.planning-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(70px, 1fr));
  gap: 6px 8px;
  padding: 8px 10px;
  align-items: start;
  background: rgba(255, 255, 255, 0.82);
  flex: 1;
}

.planning-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.planning-input {
  height: 30px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-elevated);
  padding: 0 8px;
  color: var(--text-primary);
}

.planning-input:focus {
  outline: none;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
}

.speed-field {
  min-width: 0;
}

.mission-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  grid-column: 1 / -1;
  justify-content: flex-start;
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 600;
}

.mission-toggle input {
  accent-color: var(--accent-color);
}

.planning-btn {
  min-width: 96px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: #f8fbff;
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.planning-btn.primary {
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
  border-color: rgba(59, 130, 246, 0.28);
  color: var(--accent-color);
}

.planning-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.compact-header-btn {
  min-width: 60px;
  height: 28px;
  padding: 0 10px;
  font-size: 11px;
  border-radius: 8px;
}

.critical-actions {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  padding: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.55) 0%, rgba(248, 250, 252, 0.95) 100%);
  flex: 1;
}

.critical-actions.disabled {
  opacity: 0.58;
}

.quick-command-btn {
  min-height: 34px;
  padding: 4px 6px;
  border-radius: 10px;
  border: 1px solid transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  color: var(--text-primary);
}

.quick-command-btn:hover:not(.disabled) {
  transform: translateY(-1px);
}

.quick-command-btn.disabled {
  cursor: not-allowed;
}

.quick-command-label {
  font-size: 11px;
  font-weight: 700;
  text-align: center;
}

.tone-primary {
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
  border-color: rgba(59, 130, 246, 0.28);
}

.tone-success {
  background: linear-gradient(180deg, #ecfdf5 0%, #d1fae5 100%);
  border-color: rgba(16, 185, 129, 0.28);
}

.tone-warning {
  background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
  border-color: rgba(245, 158, 11, 0.28);
}

.tone-danger {
  background: linear-gradient(180deg, #fef2f2 0%, #fee2e2 100%);
  border-color: rgba(239, 68, 68, 0.28);
}

.console-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px 8px;
  font-family: 'Roboto Mono', monospace;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.68);
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-soft);
  line-height: 1.5;
}

.log-line:last-child {
  border-bottom: none;
}

.log-message {
  color: var(--text-secondary);
  flex: 1;
  word-break: break-all;
}

.log-info .log-message {
  color: var(--text-primary);
}

.log-success .log-message {
  color: #166534;
}

.log-warn .log-message {
  color: #c2410c;
}

.log-error .log-message {
  color: #b91c1c;
}

.clear-btn {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: var(--accent-color);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: rgba(59, 130, 246, 0.18);
}

.console-content::-webkit-scrollbar {
  width: 6px;
}

.console-content::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.8);
  border-radius: 3px;
}

.console-content::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5);
  border-radius: 3px;
}

.console-content::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.72);
}

@media (max-width: 1280px) {
  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .left-panels {
    grid-template-columns: 1fr;
  }

  .planning-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .planning-header-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}

@media (max-width: 760px) {
  .planning-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>