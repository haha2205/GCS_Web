<template>
  <div class="bottom-bar">
    <!-- 实时模式：显示链路状态和系统日志 -->
    <div v-if="systemMode === 'REALTIME'" class="realtime-content">
      <!-- 中间：后端链路状态 -->
      <div class="link-console-section">
        <div class="console-header">
          <span class="console-title">LINK STATUS</span>
          <div class="status-indicators">
            <span class="indicator" :class="{ error: !droneStore.isConnected }">
              <span class="indicator-dot"></span>
              UDP: {{ udpConnected ? '已连接' : '未连接' }}
            </span>
            <span class="indicator" :class="{ error: !wsConnected }">
              <span class="indicator-dot"></span>
              WS: {{ wsConnected ? '已连接' : '未连接' }}
            </span>
            <span class="indicator">
              <span class="indicator-dot success"></span>
              延迟: {{ latency }}ms
            </span>
          </div>
        </div>
        <div class="console-content" ref="linkLogRef">
          <div
            v-for="(log, i) in linkLogs"
            :key="i"
            class="log-line"
            :class="'log-' + log.level"
          >
            <span class="log-time">[{{ log.time }}]</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>

      <!-- 右侧：系统日志 -->
      <div class="sys-console-section">
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

    <!-- 回放模式：显示播放控制器 -->
    <div v-else class="replay-content">
      <ReplayController />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useDroneStore } from '@/store/drone'
import ReplayController from './ReplayController.vue'

const droneStore = useDroneStore()

// 获取系统模式
const systemMode = computed(() => droneStore.systemMode)
const linkLogRef = ref(null)
const sysLogRef = ref(null)

// 模拟链路状态（实际应用中从store获取）
const udpConnected = ref(true)
const wsConnected = ref(true)
const latency = ref(45)

// 链路日志
const linkLogs = ref([
])

// 系统日志
const sysLogs = ref([
])

// 监听store的日志
watch(() => droneStore.logs, (logs) => {
  if (logs.length > 0) {
    const lastLog = logs[logs.length - 1]
    sysLogs.value.push({
      time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      level: lastLog.level === 'error' ? 'error' : lastLog.level === 'warning' ? 'warn' : 'info',
      icon: lastLog.level === 'error' ? '❌' : lastLog.level === 'warning' ? '⚠' : '✓',
      message: lastLog.message
    })
    // 自动滚动到底部
    setTimeout(() => {
      if (sysLogRef.value) {
        sysLogRef.value.scrollTop = sysLogRef.value.scrollHeight
      }
    }, 100)
  }
}, { deep: true })

// 飞行指令
const handleExternalControl = async () => {
  if (!droneStore.connected) return
  try {
    // 发送外控命令 (CmdIdx: 1)
    await droneStore.sendCommand('cmd_idx', { cmdId: 1, name: '外控' })
    addSysLog('外控指令已发送', 'info')
  } catch (error) {
    addSysLog('外控失败: ' + error.message, 'error')
  }
}

const handleTakeoffPreparation = async () => {
  if (!droneStore.connected) return
  try {
    // 发送起飞准备命令 (CmdIdx: 21)
    await droneStore.sendCommand('cmd_idx', { cmdId: 21, name: '起飞准备' })
    addSysLog('起飞准备指令已发送', 'info')
  } catch (error) {
    addSysLog('起飞准备失败: ' + error.message, 'error')
  }
}

const handleManualTakeoff = async () => {
  if (!droneStore.connected) return
  try {
    // 发送人工起飞命令 (CmdIdx: 22)
    await droneStore.sendCommand('cmd_idx', { cmdId: 22, name: '人工起飞' })
    addSysLog('人工起飞指令已发送', 'success')
  } catch (error) {
    addSysLog('人工起飞失败: ' + error.message, 'error')
  }
}

const handleAutoTakeoff = async () => {
  if (!droneStore.connected) return
  try {
    // 发送自动起飞命令 (CmdIdx: 14)
    await droneStore.sendCommand('cmd_idx', { cmdId: 14, name: '自动起飞' })
    addSysLog('自动起飞指令已发送', 'success')
  } catch (error) {
    addSysLog('自动起飞失败: ' + error.message, 'error')
  }
}

const handleManualLanding = async () => {
  if (!droneStore.connected) return
  try {
    // 发送人工着陆命令 (CmdIdx: 23)
    await droneStore.sendCommand('cmd_idx', { cmdId: 23, name: '人工着陆' })
    addSysLog('人工着陆指令已发送', 'info')
  } catch (error) {
    addSysLog('人工着陆失败: ' + error.message, 'error')
  }
}

const handleAutoLanding = async () => {
  if (!droneStore.connected) return
  try {
    // 发送自动着陆命令 (CmdIdx: 15)
    await droneStore.sendCommand('cmd_idx', { cmdId: 15, name: '自动着陆' })
    addSysLog('自动着陆指令已发送', 'info')
  } catch (error) {
    addSysLog('自动着陆失败: ' + error.message, 'error')
  }
}

const handleRTL = async () => {
  if (!droneStore.connected) return
  if (!confirm('确认要返航吗？')) return
  try {
    // 发送一键返航命令 (CmdIdx: 17)
    await droneStore.sendCommand('cmd_idx', { cmdId: 17, name: '一键返航' })
    addSysLog('返航指令已发送', 'warning')
  } catch (error) {
    addSysLog('返航失败: ' + error.message, 'error')
  }
}

const handleAvoidanceControl = async () => {
  if (!droneStore.connected) return
  try {
    // 切换避障开关 (CmdIdx: 24/25)
    const avoidanceEnabled = !droneStore.avoidanceEnabled || false
    const cmdId = avoidanceEnabled ? 25 : 24
    const name = avoidanceEnabled ? '避障关' : '避障开'
    await droneStore.sendCommand('cmd_idx', { cmdId, name })
    addSysLog(`${name}指令已发送`, 'info')
  } catch (error) {
    addSysLog('避障控制失败: ' + error.message, 'error')
  }
}

// 添加系统日志
const addSysLog = (message, level = 'info') => {
  sysLogs.value.unshift({
    time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
    level,
    icon: level === 'error' ? '❌' : level === 'warning' ? '⚠' : level === 'success' ? '✓' : 'ℹ',
    message
  })
  
  // 限制日志数量
  if (sysLogs.value.length > 100) {
    sysLogs.value = sysLogs.value.slice(0, 100)
  }
  
  // 自动滚动
  setTimeout(() => {
    if (sysLogRef.value) {
      sysLogRef.value.scrollTop = sysLogRef.value.scrollHeight
    }
  }, 50)
}

const clearSysLog = () => {
  sysLogs.value = []
  addSysLog('日志已清空', 'info')
}
</script>

<style scoped>
.bottom-bar {
  display: flex;
  flex-direction: row;
  gap: 10px;
  padding: 8px 16px;
  background: #141414;
  border-top: 1px solid #2e2e2;
  height: 140px;
}

/* 实时模式内容 - 左右排列 */
.realtime-content {
  display: flex;
  flex-direction: row;
  gap: 10px;
  width: 100%;
  height: 100%;
}

/* 回放模式内容 */
.replay-content {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 100%;
  padding: 0 20px;
  width: 100%;
  background: #141414;
  border-top: 2px solid #3274F6;
  user-select: none;
}

/* 控制台区域 - 实时模式下左右排列 */
.realtime-content .link-console-section,
.realtime-content .sys-console-section {
  background: #1e1e1e;
  border: 1px solid #333;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  background: #252526;
  border-bottom: 1px solid #333;
}

.console-title {
  font-size: 12px;
  font-weight: 600;
  color: #00bcd4;
  font-family: 'Roboto Mono', monospace;
}

.status-indicators {
  display: flex;
  gap: 12px;
}

.indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #888;
  font-family: 'Roboto Mono', monospace;
}

.indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #666;
}

.indicator-dot.success {
  background: #4caf50;
}

.indicator.error {
  background: #ff4d4f;
}

.console-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  font-family: 'Roboto Mono', monospace;
  font-size: 11px;
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid #333;
  line-height: 1.5;
}

.log-line:last-child {
  border-bottom: none;
}

.log-time {
  color: #666;
  min-width: 80px;
}

.log-message {
  color: #ccc;
  flex: 1;
  word-break: break-all;
}

.log-info .log-message {
  color: #e0e0e0;
}

.log-success .log-message {
  color: #69f0ae;
}

.log-warn .log-message {
  color: #ffab40;
}

.log-error .log-message {
  color: #ff5252;
}

.clear-btn {
  background: #1e3a8a;
  border: 1px solid #333;
  color: #fff;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: #264078;
}

/* 滚动条样式 */
.console-content::-webkit-scrollbar {
  width: 6px;
}

.console-content::-webkit-scrollbar-track {
  background: #1a1a1a;
}

.console-content::-webkit-scrollbar-thumb {
  background: #3288fa;
  border-radius: 3px;
}

.console-content::-webkit-scrollbar-thumb:hover {
  background: #2676ea;
}
</style>