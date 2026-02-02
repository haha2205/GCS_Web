<template>
  <div class="command-panel">
    <h3 class="panel-title">飞控指令</h3>
    
    <!-- 指令类型切换 -->
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

    <!-- 飞控指令（CmdIdx） -->
    <div v-show="activeTab === 'remote'" class="tab-content command-sections">
      <!-- 滚动容器 -->
      <div class="content-scroll">
        <!-- 飞行控制 -->
        <div class="command-group">
          <h4 class="group-title">飞行控制</h4>
          <div class="command-grid" :class="{ 'btn-disabled': !connected }">
            <button v-for="cmd in flightCommands" :key="cmd.id" 
                    class="command-btn flight" 
                    :class="{ danger: cmd.danger }"
                    :title="cmd.name"
                    @click="sendRemoteCommand(cmd.id, cmd.name)">
              <span class="cmd-icon">{{ cmd.icon }}</span>
              <span class="cmd-label">{{ cmd.shortName }}</span>
            </button>
          </div>
        </div>

        <!-- 起降控制 -->
        <div class="command-group">
          <h4 class="group-title">起降控制</h4>
          <div class="command-grid" :class="{ 'btn-disabled': !connected }">
            <button v-for="cmd in takeoffCommands" :key="cmd.id"
                    class="command-btn takeoff"
                    :class="{ danger: cmd.danger }"
                    :title="cmd.name"
                    @click="sendRemoteCommand(cmd.id, cmd.name)">
              <span class="cmd-icon">{{ cmd.icon }}</span>
              <span class="cmd-label">{{ cmd.shortName }}</span>
            </button>
          </div>
        </div>

        <!-- 避障控制 -->
        <div class="command-group">
          <h4 class="group-title">避障控制</h4>
          <div class="command-grid" :class="{ 'btn-disabled': !connected }">
            <button class="command-btn avoidance" @click="sendRemoteCommand(24, '避障开')">
              <span class="cmd-icon">🔓</span>
              <span class="cmd-label">避障开</span>
            </button>
            <button class="command-btn avoidance" @click="sendRemoteCommand(25, '避障关')">
              <span class="cmd-icon">🔒</span>
              <span class="cmd-label">避障关</span>
            </button>
          </div>
        </div>

        <!-- 速度控制 -->
        <div class="command-group">
          <h4 class="group-title">速度控制</h4>
          <div class="command-grid" :class="{ 'btn-disabled': !connected }">
            <button class="command-btn speed" @click="sendRemoteCommand(19, '地速飞行')">
              <span class="cmd-label">地速</span>
            </button>
            <button class="command-btn speed" @click="sendRemoteCommand(20, '空速飞行')">
              <span class="cmd-label">空速</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 遥调指令（CmdMission） -->
    <div v-show="activeTab === 'telemetry'" class="tab-content telemetry-sections">
      <!-- 滚动容器 -->
      <div class="content-scroll">
        <!-- 姿态遥调 -->
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
                    type="number" 
                    :min="item.min" 
                    :max="item.max" 
                    :step="item.step"
                    v-model.number="item.value"
                    class="telemetry-input number-box"
                  >
                <span class="telemetry-unit">{{ item.unit }}</span>
                <button class="send-btn" @click="sendTelemetryCommand(item.id, item.value, item.name)">发送</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 速度遥调 -->
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
                    type="number" 
                    :min="item.min" 
                    :max="item.max" 
                    :step="item.step"
                    v-model.number="item.value"
                    class="telemetry-input number-box"
                  >
                <span class="telemetry-unit">{{ item.unit }}</span>
                <button class="send-btn" @click="sendTelemetryCommand(item.id, item.value, item.name)">发送</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 位置遥调 -->
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
                    type="number" 
                    :min="item.min" 
                    :max="item.max" 
                    :step="item.step"
                    v-model.number="item.value"
                    class="telemetry-input number-box"
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
import { ref, computed } from 'vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()
const connected = computed(() => droneStore.connected)
const activeTab = ref('remote')

// 指令类型标签
const tabs = [
  { id: 'remote', label: '遥控指令' },
  { id: 'telemetry', label: '遥调指令' }
]

// 飞控指令（CmdIdx）
const flightCommands = [
  { id: 1, name: '外控', shortName: '外控', icon: '🎮' },
  { id: 2, name: '混控', shortName: '混控', icon: '🎯' },
  { id: 3, name: '程控', shortName: '程控', icon: '⏯' },
  { id: 4, name: '爬升', shortName: '爬升', icon: '📈' },
  { id: 5, name: '定高/平飞', shortName: '定高', icon: '▶️' },
  { id: 6, name: '下滑', shortName: '下滑', icon: '⬇️' },
  { id: 8, name: '定向/直飞', shortName: '定向', icon: '➡️' },
  { id: 9, name: '左盘旋', shortName: '左盘旋', icon: '🔄' },
  { id: 10, name: '右盘旋', shortName: '右盘旋', icon: '🔄' },
  { id: 11, name: '航向保持', shortName: '航向保持', icon: '🧭' },
  { id: 12, name: '开车准备', shortName: '开车', icon: '🔧' },
  { id: 13, name: '停车', shortName: '停车', icon: '🛑' },
  { id: 18, name: '预控', shortName: '预控', icon: '👁️' }
]

const takeoffCommands = [
  { id: 21, name: '起飞准备', shortName: '起飞准备', icon: '✈️' },
  { id: 22, name: '人工起飞', shortName: '人工起飞', icon: '🚀' },
  { id: 14, name: '自动起飞', shortName: '自动起飞', icon: '🚀' },
  { id: 16, name: '悬停', shortName: '悬停', icon: '⏸' },
  { id: 23, name: '人工着陆', shortName: '人工着陆', icon: '🛬' },
  { id: 15, name: '自动着陆', shortName: '自动着陆', icon: '🛬' },
  { id: 7, name: '断开定高', shortName: '断开定高', icon: '⏸' },
  { id: 17, name: '一键返航', shortName: '返航', icon: '🏠', danger: true }
]

// 遥调指令（CmdMission）- 姿态
const attitudeAdjustments = [
  { id: 10111, name: '俯仰角', min: -12, max: 12, step: 0.1, value: 0, unit: '°' },
  { id: 10112, name: '滚转角', min: -12, max: 12, step: 0.1, value: 0, unit: '°' },
  { id: 10113, name: '航向角', min: 0, max: 360, step: 1, value: 0, unit: '°' }
]

// 遥调指令（CmdMission）- 速度
const velocityAdjustments = [
  { id: 9531, name: '纵向速度', min: -12, max: 50, step: 0.1, value: 0, unit: 'm/s' },
  { id: 9532, name: '横向速度', min: -12, max: 12, step: 0.1, value: 0, unit: 'm/s' },
  { id: 9533, name: '升降速度', min: -3000, max: 3000, step: 1, value: 0, unit: 'm/s' }
]

// 遥调指令（CmdMission）- 位置
const positionAdjustments = [
  { id: 9023, name: '纵向位置', min: -1000, max: 1000, step: 1, value: 0, unit: 'm' },
  { id: 9024, name: '横向位置', min: 20, max: 500, step: 1, value: 0, unit: 'm' },
  { id: 1021, name: '高度', min: 0, max: 200, step: 1, value: 0, unit: 'm' }
]

// 发送遥控指令（通过 REST API）
 const sendRemoteCommand = async (cmdId, cmdName) => {
  if (!connected.value) {
    droneStore.addLog('未连接到后端，无法发送指令', 'warning')
    return
  }
  
  try {
    // 更新store中的CmdIdx，让规划面板可以获取到当前指令
    droneStore.gcsData.Tele_GCS_CmdIdx = cmdId
    
    const result = await droneStore.sendCommandREST('cmd_idx', {
      cmdId,
      name: cmdName
    })
    if (result && result.status === 'success') {
      console.log(`指令发送成功: ${cmdName}`)
    }
  } catch (error) {
    console.error('发送失败:', error.message)
    droneStore.addLog(`发送指令失败: ${error.message}`, 'error')
  }
}

// 发送遥调指令（通过 REST API）
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
    if (result && result.status === 'success') {
      console.log(`遥调指令发送成功: ${name}`)
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
  height: 100%;  /* 关键修复：占满父容器高度 */
  min-height: 0;
}

.panel-title {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #ff9800;
  /* 标题不添加到flex计算中，固定高度 */
  flex-shrink: 0;
}

/* 内部滚动容器 - 关键修复 */
.content-scroll {
  flex: 1 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  min-height: 0 !important;
  max-height: 100% !important;
  padding-right: 4px;  /* 为滚动条预留空间 */
}

/* 自定义滚动条样式 - 强制生效 */
* .content-scroll::-webkit-scrollbar {
  width: 6px !important;
}

* .content-scroll::-webkit-scrollbar-track {
  background: rgba(30, 30, 30, 0.5) !important;
  border-radius: 3px !important;
}

* .content-scroll::-webkit-scrollbar-thumb {
  background: rgba(50, 136, 250, 0.5) !important;
  border-radius: 3px !important;
  transition: background 0.2s !important;
}

* .content-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(50, 136, 250, 0.8) !important;
}

/* 标签页内容容器 - 关键修复 */
.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* 指令类型切换 */
.command-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 15px;
  /* 标签栏不添加到flex计算中 */
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  padding: 10px 16px;
  background: rgba(40, 40, 40, 0.5);
  border: 1px solid #333;
  border-radius: 6px;
  color: #999;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(50, 136, 250, 0.15);
  color: #fff;
}

.tab-btn.active {
  background: rgba(50, 136, 250, 0.25);
  border-color: #3288fa;
  color: #fff;
  font-weight: 600;
}


.command-group {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.telemetry-group {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.group-title {
  color: #ff9800;
  font-size: 12px;
  font-weight: 600;
  margin: 0 0 10px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.command-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.telemetry-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.telemetry-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 0;
  border-bottom: 1px solid #333;
}

.telemetry-item:last-child {
  border-bottom: none;
}

.telemetry-label {
  color: #999;
  font-size: 12px;
  font-weight: 500;
}

.telemetry-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.telemetry-input {
  background: rgba(30, 30, 30, 0.8);
  border: 1px solid #444;
  border-radius: 4px;
  color: #fff;
  padding: 6px 10px;
  font-size: 13px;
}

.telemetry-input.range {
  flex: 1;
  max-width: 120px;
}

.telemetry-input.number {
  width: 70px;
  text-align: center;
}

.telemetry-unit {
  color: #666;
  font-size: 12px;
  min-width: 35px;
}

.command-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 8px;
  background: rgba(50, 136, 250, 0.15);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 6px;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.2s;
  height: 64px;
}

.command-btn:hover:not(.btn-disabled) {
  background: rgba(50, 136, 250, 0.25);
  transform: translateY(-2px);
}

.command-btn.btn-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.command-btn.danger {
  background: rgba(211, 47, 47, 0.15);
  border-color: rgba(211, 47, 47, 0.3);
}

.command-btn.danger:hover:not(.btn-disabled) {
  background: rgba(211, 47, 47, 0.25);
  background-color: #b71c1c;
}

.command-btn.takeoff {
  background: rgba(76, 175, 80, 0.15);
  border-color: rgba(76, 175, 80, 0.3);
}

.command-btn.takeoff:hover:not(.btn-disabled) {
  background: rgba(76, 175, 80, 0.25);
}

.command-btn.avoidance {
  background: rgba(255, 152, 0, 0.15);
  border-color: rgba(255, 152, 0, 0.3);
}

.command-btn.avoidance:hover:not(.btn-disabled) {
  background: rgba(255, 152, 0, 0.25);
}

.command-btn.speed {
  background: rgba(100, 181, 246, 0.15);
  border-color: rgba(100, 181, 246, 0.3);
}

.command-btn.speed:hover:not(.btn-disabled) {
  background: rgba(100, 181, 246, 0.25);
}

.cmd-icon {
  font-size: 20px;
  margin-bottom: 4px;
}

.cmd-label {
  color: #ffffff;
  font-size: 12px;
  font-weight: 500;
}

/* New telemetry styles */
.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.range-hint {
  color: #666;
  font-size: 11px;
}

.telemetry-control-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.telemetry-input.number-box {
  flex: 1;
  width: auto;
  min-width: 0;
  text-align: left;
}

.send-btn {
  background: rgba(50, 136, 250, 0.2);
  border: 1px solid rgba(50, 136, 250, 0.4);
  color: #409eff;
  border-radius: 4px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.send-btn:hover {
  background: rgba(50, 136, 250, 0.4);
  color: #fff;
}
</style>