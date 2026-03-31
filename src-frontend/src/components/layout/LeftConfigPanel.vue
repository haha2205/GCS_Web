<template>
  <div class="config-panel">
    <h3 class="panel-title">配置中心</h3>
    
    <div class="content-scroll">
      <div class="config-content" :class="{ 'btn-disabled': loading }">
        <div class="config-section">
          <h4 class="section-title">连接配置</h4>
          <div class="config-grid">
            <div class="config-subsection">
              <div class="subsection-title">本地端（GCS）</div>
              <div class="config-row">
                <label>Protocol</label>
                <div class="config-value">{{ protocol.toUpperCase() }}</div>
              </div>
              <div class="config-row">
                <label>监听地址</label>
                <div class="config-value">{{ listenAddress }}</div>
              </div>
              <div class="config-row">
                <label>主聚合接收口</label>
                <div class="config-value">{{ hostPort }}</div>
              </div>
              <div class="config-row">
                <label>飞控遥测降级监听口</label>
                <div class="config-value">{{ sendOnlyPort }}</div>
              </div>
              <div class="config-row">
                <label>规划遥测专用口</label>
                <div class="config-value">{{ planningRecvPort }}</div>
              </div>
            </div>
            
            <div class="config-subsection">
              <div class="subsection-title">远程端（飞控）</div>
              <div class="config-row">
                <label>Remote IP</label>
                <div class="config-value">{{ remoteIp }}</div>
              </div>
              <div class="config-row">
                <label>指令上行</label>
                <div class="config-value">{{ commandRecvPort }}</div>
              </div>
              <div class="config-row">
                <label>飞控遥测发送口</label>
                <div class="config-value">{{ sendOnlyPort }}</div>
              </div>
              <div class="config-row">
                <label>LiDAR下行</label>
                <div class="config-value">{{ lidarSendPort }}</div>
              </div>
              <div class="config-row">
                <label>规划上行</label>
                <div class="config-value">{{ planningSendPort }}</div>
              </div>
              <div class="config-row">
                <label>规划遥测发送口</label>
                <div class="config-value">{{ planningRecvPort }}</div>
              </div>
            </div>
          </div>
          <div class="fixed-config-note">
            <div>HTTP / WebSocket 后端绑定 {{ backendHttpBindUrl }}</div>
            <div>前端访问后端地址：{{ backendHttpUrl }}</div>
            <div>前端页面访问入口：{{ frontendDisplayUrls.join(' / ') }}</div>
            <div>UDP 口径固定为 GCS {{ listenAddress }} 以 30509 作为飞控遥测主入口，18506 仅作兼容降级监听，18511 接收规划遥测；UAV {{ remoteIp }} 使用 18504 / 18506 / 18510 / 18511。</div>
          </div>
          <div class="config-actions">
            <button
              :class="['connect-btn', { connected: isConnected, loading: loading }]"
              @click="toggleConnection"
              :disabled="loading"
            >
              <span class="status-indicator" v-if="!loading"></span>
              <span v-if="loading">处理中...</span>
              <span v-else>{{ isConnected ? '断开 UDP' : '连接 UDP' }}</span>
            </button>
          </div>
        </div>
      </div>
      
      <div v-if="saveMessage" class="action-message" :class="{ success: saveSuccess }">
        {{ saveMessage }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import backend, { isBackendUnavailableError } from '@/api/backend'

const droneStore = useDroneStore()
const connectionApi = backend.connection
const udpApi = backend.udp

// UDP连接状态
const isConnected = ref(false)

// 协议和本地配置
const protocol = ref('udp')
const listenAddress = ref('192.168.16.13')
const hostPort = ref(30509)

// 远程端配置
const remoteIp = ref('192.168.16.116')
const commandRecvPort = ref(18504)
const sendOnlyPort = ref(18506)
const lidarSendPort = ref(18507)
const planningSendPort = ref(18510)
const planningRecvPort = ref(18511)
const backendHttpBindUrl = ref('http://0.0.0.0:8000')
const backendHttpUrl = ref('http://localhost:8000')
const frontendDisplayUrls = ref(['http://localhost:5173', 'http://127.0.0.1:5173'])

// 加载状态
const loading = ref(false)
const saveMessage = ref('')
const saveSuccess = ref(false)

/**
 * 加载配置
 */
const loadConfig = async () => {
  loading.value = true
  try {
    // 加载连接配置
    const connConfig = await connectionApi.getConfig()
    if (connConfig.data) {
      protocol.value = connConfig.data.protocol
      listenAddress.value = connConfig.data.listenAddress || '192.168.16.13'
      hostPort.value = connConfig.data.hostPort
      remoteIp.value = connConfig.data.remoteIp
      commandRecvPort.value = connConfig.data.commandRecvPort || 18504
      sendOnlyPort.value = connConfig.data.sendOnlyPort
      lidarSendPort.value = connConfig.data.lidarSendPort || 18507
      planningSendPort.value = connConfig.data.planningSendPort
      planningRecvPort.value = connConfig.data.planningRecvPort
      backendHttpBindUrl.value = connConfig.data.semantics?.backend_http_bind_url || 'http://0.0.0.0:8000'
      backendHttpUrl.value = connConfig.data.semantics?.backend_http_url || 'http://localhost:8000'
      frontendDisplayUrls.value = connConfig.data.semantics?.frontend_access_urls || ['http://localhost:5173', 'http://127.0.0.1:5173']
      droneStore.updateConfig(connConfig.data)
    }
  } catch (error) {
    if (!isBackendUnavailableError(error)) {
      console.error('加载配置失败:', error)
      droneStore.addLog('加载配置失败: ' + error.message, 'error')
    }
  } finally {
    loading.value = false
  }
}

/**
 * 手动断开UDP连接
 */
const disconnectUDP = async () => {
  loading.value = true
  saveMessage.value = ''
  
  try {
    droneStore.addLog('手动断开UDP连接...', 'info')
    const result = await udpApi.stopServer()
    
    if (result.status === 'success') {
      droneStore.addLog('UDP连接已断开', 'success')
      saveMessage.value = 'UDP连接已断开'
      saveSuccess.value = true
    }
  } catch (error) {
    console.error('断开UDP连接失败:', error)
    saveMessage.value = '断开失败: ' + error.message
    saveSuccess.value = false
    droneStore.addLog('断开UDP连接失败: ' + error.message, 'error')
  } finally {
    loading.value = false
    setTimeout(() => saveMessage.value = '', 3000)
  }
}

/**
 * 切换连接状态（点击连接/断开按钮）
 */
const toggleConnection = async () => {
  if (isConnected.value) {
    await disconnectUDP()
  } else {
    loading.value = true
    try {
      droneStore.addLog('使用固定链路参数启动 UDP...', 'info')
      const result = await udpApi.startServer()
      isConnected.value = result?.status === 'success'
      saveMessage.value = result?.message || 'UDP服务器已启动'
      saveSuccess.value = result?.status === 'success'
      droneStore.addLog(saveMessage.value, saveSuccess.value ? 'success' : 'warning')
    } catch (error) {
      console.error('启动UDP服务器失败:', error)
      saveMessage.value = '启动UDP失败: ' + error.message
      saveSuccess.value = false
      droneStore.addLog(saveMessage.value, 'error')
    } finally {
      loading.value = false
    }
  }

  if (saveMessage.value) {
    setTimeout(() => saveMessage.value = '', 5000)
  }
}

/**
 * 监听WebSocket消息，处理UDP状态变化
 */
watch(() => droneStore.lastBackendMessage, (newMessage) => {
  if (!newMessage) return
  
  try {
    const data = typeof newMessage === 'string' ? JSON.parse(newMessage) : newMessage
    
    if (data?.type === 'udp_status_change') {
      const previousState = isConnected.value
      isConnected.value = (data.status === 'connected')
      
      // 状态变化时记录日志
      if (previousState !== isConnected.value) {
        if (isConnected.value) {
          const primaryPort = data.flight_telemetry_primary_port || data.flight_telemetry_port || data.primary_receive_port || data.config?.hostPort
          const fallbackPort = data.flight_telemetry_fallback_port || data.config?.sendOnlyPort
          const planningPort = data.planning_telemetry_port || data.config?.planningRecvPort
          droneStore.addLog('UDP连接已建立', 'success')
          droneStore.addLog(`GCS监听: ${primaryPort}(飞控主入口) / ${fallbackPort}(飞控降级监听) / ${planningPort}(规划遥测)`, 'info')
          droneStore.addLog(`后端地址: ${data.backend_http_url || backendHttpUrl.value}`, 'info')
        } else {
          droneStore.addLog('UDP连接已断开', 'warning')
        }
      }
    } else if (data?.type === 'config_update' && data.config_type === 'connection') {
      // 配置更新后刷新本地状态
      droneStore.addLog('收到配置更新通知', 'info')
    }
  } catch (error) {
    console.error('处理WebSocket消息失败:', error)
  }
})

// 组件挂载时
onMounted(async () => {
  await loadConfig()
  
  // 初始化时检查UDP连接状态
  try {
    const statusResult = await udpApi.getStatus()
    if (statusResult.data) {
      isConnected.value = statusResult.data.connected
    }
  } catch (error) {
    if (!isBackendUnavailableError(error)) {
      console.warn('获取UDP状态失败:', error)
    }
  }
})
</script>

<style scoped>
.config-panel {
  padding: 15px;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(180deg, #f8fbff 0%, #edf4fb 100%);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  box-shadow: var(--shadow-sm);
  color: var(--text-primary);
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0 8px 0 2px;
}

/* 自定义滚动条样式 */
.content-scroll::-webkit-scrollbar {
  width: 6px;
}

.content-scroll::-webkit-scrollbar-track {
  background: rgba(219, 228, 239, 0.9);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb {
  background: rgba(37, 99, 235, 0.35);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(37, 99, 235, 0.55);
}

.config-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding: 2px 4px 10px;
  border-bottom: 2px solid var(--accent-color);
}

.config-section {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.section-title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
}

.config-value {
  min-height: 38px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: rgba(243, 247, 252, 0.92);
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.fixed-config-note {
  margin: 8px 0 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.14);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.config-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subsection-title {
  font-size: 12px;
  color: var(--accent-color);
  font-weight: 600;
  margin-bottom: 8px;
  background: rgba(37, 99, 235, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

.config-subsection {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  background: var(--panel-muted);
  border-radius: 6px;
  border: 1px solid var(--border-light);
}

.config-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.config-row.switch-row {
  justify-content: flex-start;
  gap: 10px;
}

.config-row label {
  color: var(--text-secondary);
  font-size: 12px;
  min-width: 110px;
}

.config-input {
  background: var(--surface-elevated);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  color: var(--text-primary);
  padding: 6px 10px;
  font-size: 12px;
  width: 140px;
  transition: all 0.2s;
}

.config-input:focus {
  border-color: var(--accent-color);
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.file-input {
  display: flex;
  gap: 8px;
  flex: 1;
}

.file-input .config-input {
  flex: 1;
}

.browse-btn {
  background: var(--accent-color);
  border: none;
  border-radius: 4px;
  color: #ffffff;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  transition: all 0.2s;
}

.browse-btn:hover {
  background: var(--primary-hover);
}

/* Toggle Switch */
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #cbd5e1;
  transition: .3s;
  border-radius: 22px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
}

.toggle-switch input:checked + .slider {
  background-color: var(--accent-color);
}

.toggle-switch input:checked + .slider:before {
  transform: translateX(18px);
}

.config-actions {
  padding: 12px 0;
  border-top: 1px solid var(--border-light);
}

.action-message {
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  margin-top: 12px;
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
  color: #b91c1c;
}

.action-message.success {
  background: rgba(76, 175, 80, 0.1);
  border-color: rgba(76, 175, 80, 0.3);
  color: #4caf50;
}

.connect-btn {
  width: 100%;
  background: rgba(76, 175, 80, 0.2);
  border: 1px solid #4caf50;
  border-radius: 6px;
  color: #166534;
  padding: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.connect-btn:hover {
  background: rgba(76, 175, 80, 0.3);
}

.connect-btn.connected {
  background: #d32f2f;
  border-color: #d32f2f;
  color: #ffffff;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
  animation: blink 1s infinite;
}

.apply-btn {
  width: 100%;
  background: rgba(37, 99, 235, 0.12);
  border: 1px solid rgba(37, 99, 235, 0.24);
  border-radius: 6px;
  color: var(--accent-color);
  padding: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s;
}

.apply-btn:hover {
  background: rgba(37, 99, 235, 0.2);
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.clear-btn {
  background: rgba(255, 152, 0, 0.2);
  border: 1px solid rgba(255, 152, 0, 0.3);
  border-radius: 4px;
  color: #ff9800;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: rgba(255, 152, 0, 0.3);
}

.info-row {
  display: flex;
  flex-direction: column;
  padding: 8px 0;
  margin-bottom: 8px;
}

.info-text {
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.4;
  background: rgba(37, 99, 235, 0.08);
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 3px solid var(--accent-color);
}
</style>