<template>
  <div class="command-panel">
    <h3 class="panel-title">飞控指令</h3>

    <div class="command-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-show="activeTab === 'remote'" class="tab-content">
      <div class="content-scroll">
        <div class="command-grid" :class="{ 'btn-disabled': !connected }">
          <button
            v-for="cmd in remoteCommandButtons"
            :key="cmd.id"
            class="command-btn"
            :class="{ danger: cmd.tone === 'danger' }"
            :title="cmd.name"
            @click="sendRemoteCommand(cmd.id, cmd.name, cmd.confirm)"
          >
            <span class="cmd-label">{{ cmd.name }}</span>
          </button>
        </div>
      </div>
    </div>

    <div v-show="activeTab === 'telemetry'" class="tab-content">
      <div class="content-scroll">
        <div class="telemetry-group">
          <h4 class="group-title">姿态遥调</h4>
          <div class="telemetry-grid" :class="{ 'btn-disabled': !connected }">
            <div class="telemetry-item" v-for="item in attitudeAdjustments" :key="item.id">
              <div class="item-header">
                <label class="telemetry-label">{{ item.name }}</label>
                <span class="range-hint">[{{ item.min }}, {{ item.max }}]</span>
              </div>
              <div class="telemetry-control-row">
                <input
                  v-model.number="item.value"
                  type="number"
                  :min="item.min"
                  :max="item.max"
                  :step="item.step"
                  class="telemetry-input"
                >
                <span class="telemetry-unit">{{ item.unit }}</span>
                <button class="send-btn" @click="sendTelemetryCommand(item.id, item.value, item.name)">发送</button>
              </div>
            </div>
          </div>
        </div>

        <div class="telemetry-group">
          <h4 class="group-title">速度遥调</h4>
          <div class="telemetry-grid" :class="{ 'btn-disabled': !connected }">
            <div class="telemetry-item" v-for="item in velocityAdjustments" :key="item.id">
              <div class="item-header">
                <label class="telemetry-label">{{ item.name }}</label>
                <span class="range-hint">[{{ item.min }}, {{ item.max }}]</span>
              </div>
              <div class="telemetry-control-row">
                <input
                  v-model.number="item.value"
                  type="number"
                  :min="item.min"
                  :max="item.max"
                  :step="item.step"
                  class="telemetry-input"
                >
                <span class="telemetry-unit">{{ item.unit }}</span>
                <button class="send-btn" @click="sendTelemetryCommand(item.id, item.value, item.name)">发送</button>
              </div>
            </div>
          </div>
        </div>

        <div class="telemetry-group">
          <h4 class="group-title">位置遥调</h4>
          <div class="telemetry-grid" :class="{ 'btn-disabled': !connected }">
            <div class="telemetry-item" v-for="item in positionAdjustments" :key="item.id">
              <div class="item-header">
                <label class="telemetry-label">{{ item.name }}</label>
                <span class="range-hint">[{{ item.min }}, {{ item.max }}]</span>
              </div>
              <div class="telemetry-control-row">
                <input
                  v-model.number="item.value"
                  type="number"
                  :min="item.min"
                  :max="item.max"
                  :step="item.step"
                  class="telemetry-input"
                >
                <span class="telemetry-unit">{{ item.unit }}</span>
                <button class="send-btn" @click="sendTelemetryCommand(item.id, item.value, item.name)">发送</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useDroneStore } from '@/store/drone'
import { remoteCommandButtons } from '@/constants/commandConfig'

const droneStore = useDroneStore()
const connected = computed(() => droneStore.canSendCommands)
const activeTab = ref('remote')

const tabs = [
  { id: 'remote', label: '遥控指令' },
  { id: 'telemetry', label: '遥调指令' }
]

const attitudeAdjustments = [
  { id: 10111, name: '俯仰角', min: -12, max: 12, step: 0.1, value: 0, unit: '°' },
  { id: 10112, name: '滚转角', min: -12, max: 12, step: 0.1, value: 0, unit: '°' },
  { id: 10113, name: '航向角', min: 0, max: 360, step: 1, value: 0, unit: '°' }
]

const velocityAdjustments = [
  { id: 9531, name: '纵向速度', min: -12, max: 50, step: 0.1, value: 0, unit: 'm/s' },
  { id: 9532, name: '横向速度', min: -12, max: 12, step: 0.1, value: 0, unit: 'm/s' },
  { id: 9533, name: '升降速度', min: -3000, max: 3000, step: 1, value: 0, unit: 'm/s' }
]

const positionAdjustments = [
  { id: 9501, name: '纵向位置', min: -1000, max: 1000, step: 1, value: 0, unit: 'm' },
  { id: 9502, name: '横向位置', min: 20, max: 500, step: 1, value: 0, unit: 'm' },
  { id: 1021, name: '高度', min: 0, max: 200, step: 1, value: 0, unit: 'm' }
]

const sendRemoteCommand = async (cmdId, cmdName, confirmText) => {
  if (confirmText && !window.confirm(confirmText)) {
    return
  }

  try {
    const result = await droneStore.sendRemoteCommand(cmdId, cmdName)
    if (result?.status === 'success') {
      console.log(`指令发送成功: ${cmdName}`)
    } else if (result?.message) {
      droneStore.addLog(`${cmdName}未发送: ${result.message}`, result?.status === 'rate_limited' ? 'warning' : 'error')
    }
  } catch (error) {
    console.error('发送失败:', error.message)
    droneStore.addLog(`发送指令失败: ${error.message}`, 'error')
  }
}

const sendTelemetryCommand = async (cmdId, value, name) => {
  if (!connected.value) {
    droneStore.addLog('未连接到后端，无法发送指令', 'warning')
    return
  }

  try {
    const result = await droneStore.sendCommandREST('cmd_mission', {
      cmd_mission: cmdId,
      value: parseFloat(value),
      name
    })
    if (result?.status === 'success') {
      console.log(`遥调指令发送成功: ${name}`)
    } else if (result?.message) {
      droneStore.addLog(`${name}未发送: ${result.message}`, result?.status === 'rate_limited' ? 'warning' : 'error')
    }
  } catch (error) {
    console.error('发送失败:', error.message)
    droneStore.addLog(`发送指令失败: ${error.message}`, 'error')
  }
}
</script>

<style scoped>
.command-panel {
  padding: 15px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  color: var(--text-primary);
}

.panel-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--accent-warm);
  flex-shrink: 0;
}

.command-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 15px;
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  padding: 10px 16px;
  background: var(--panel-muted);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(37, 99, 235, 0.08);
}

.tab-btn.active {
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
  border-color: rgba(59, 130, 246, 0.28);
  color: var(--accent-color);
}

.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  padding-right: 4px;
}

.content-scroll::-webkit-scrollbar {
  width: 6px;
}

.content-scroll::-webkit-scrollbar-track {
  background: var(--panel-muted);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb {
  background: rgba(59, 130, 246, 0.5);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(59, 130, 246, 0.75);
}

.command-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.command-btn {
  min-height: 54px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: linear-gradient(180deg, #f8fbff 0%, #edf4ff 100%);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  transition: all 0.2s ease;
}

.command-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
}

.command-btn.danger {
  border-color: rgba(239, 68, 68, 0.32);
  background: linear-gradient(180deg, #fff1f2 0%, #ffe4e6 100%);
}

.cmd-label {
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  text-align: center;
}

.btn-disabled {
  opacity: 0.58;
  pointer-events: none;
}

.telemetry-group {
  margin-bottom: 16px;
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-color);
  margin: 0 0 10px 0;
}

.telemetry-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.telemetry-item {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.9);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.telemetry-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
}

.range-hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

.telemetry-control-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
}

.telemetry-input {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--surface-elevated);
  color: var(--text-primary);
}

.telemetry-unit {
  font-size: 12px;
  color: var(--text-secondary);
}

.send-btn {
  height: 34px;
  border-radius: 8px;
  border: 1px solid rgba(37, 99, 235, 0.2);
  background: rgba(37, 99, 235, 0.08);
  color: var(--accent-color);
  padding: 0 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
</style>