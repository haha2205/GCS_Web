<template>
  <div class="config-panel">
    <h3 class="panel-title">配置中心</h3>
    
    <div class="content-scroll">
      <!-- 连接配置 -->
      <div class="config-content" :class="{ 'btn-disabled': loading }">
        <div class="config-section">
          <h4 class="section-title">连接配置</h4>
          <div class="config-grid">
            <!-- 本地端配置 -->
            <div class="config-subsection">
              <div class="subsection-title">本地端（GCS）</div>
              <div class="config-row">
                <label>Protocol</label>
                <select v-model="protocol" class="config-input">
                  <option value="udp">UDP</option>
                  <option value="serial">Serial</option>
                </select>
              </div>
              <div class="config-row">
                <label>监听地址</label>
                <input v-model="listenAddress" type="text" class="config-input" placeholder="0.0.0.0" />
              </div>
              <div class="config-row">
                <label>监听端口</label>
                <input v-model.number="hostPort" type="number" class="config-input" placeholder="30509" />
              </div>
            </div>
            
            <!-- 远程端配置 -->
            <div class="config-subsection">
              <div class="subsection-title">远程端（飞控）</div>
              <div class="config-row">
                <label>Remote IP</label>
                <input v-model="remoteIp" type="text" class="config-input" placeholder="127.0.0.2" :disabled="loading" />
              </div>
              <div class="config-row">
                <label>指令上行</label>
                <input v-model.number="commandRecvPort" type="number" class="config-input" placeholder="18504" :disabled="loading" />
              </div>
              <div class="config-row">
                <label>遥测下行</label>
                <input v-model.number="sendOnlyPort" type="number" class="config-input" placeholder="18506" :disabled="loading" />
              </div>
              <div class="config-row">
                <label>LiDAR下行</label>
                <input v-model.number="lidarSendPort" type="number" class="config-input" placeholder="18507" :disabled="loading" />
              </div>
              <div class="config-row">
                <label>规划上行</label>
                <input v-model.number="planningSendPort" type="number" class="config-input" placeholder="18510" :disabled="loading" />
              </div>
              <div class="config-row">
                <label>规划下行</label>
                <input v-model.number="planningRecvPort" type="number" class="config-input" placeholder="18511" :disabled="loading" />
              </div>
            </div>
          </div>
          <div class="config-actions">
            <button
              :class="['connect-btn', { connected: isConnected, loading: loading }]"
              @click="saveConnectionConfig"
              :disabled="loading"
            >
              <span class="status-indicator" v-if="!loading"></span>
              <span v-if="loading">保存中...</span>
              <span v-else>{{ isConnected ? '断开 UDP' : '连接 UDP' }}</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- 数据记录配置 -->
      <div class="config-section">
        <h4 class="section-title">数据记录</h4>
        <div class="config-grid">
          <div class="info-row">
            <span class="info-text">📂 日志自动保存在项目目录的 <strong>Log/</strong> 文件夹下</span>
          </div>
          <div class="config-row switch-row">
            <label>自动记录</label>
            <label class="toggle-switch">
              <input type="checkbox" v-model="autoRecord" :disabled="loading" />
              <span class="slider"></span>
            </label>
          </div>
          <div class="config-row">
            <label>日志格式</label>
            <select v-model="logFormat" class="config-input" :disabled="loading">
              <option value="csv">CSV（可读性强）</option>
              <option value="binary">Binary（高效存储）</option>
            </select>
          </div>
          <div class="config-row">
            <label>日志级别</label>
            <select v-model="logLevel" class="config-input" :disabled="loading">
              <option value="0">DEBUG（调试）</option>
              <option value="1">INFO（信息）</option>
              <option value="2">WARNING（警告）</option>
              <option value="3">ERROR（错误）</option>
            </select>
          </div>
        </div>
        
        <!-- 保存日志配置按钮 -->
        <div class="config-actions">
          <button
            class="apply-btn"
            @click="saveLogConfig"
            :disabled="loading"
          >
            <span v-if="!loading">保存日志配置</span>
            <span v-else>保存中...</span>
          </button>
        </div>
      </div>
      
      <!-- 保存操作配置的消息提示 -->
      <div v-if="saveMessage" class="action-message" :class="{ success: saveSuccess }">
        {{ saveMessage }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import { useWebSocket } from '@/composables/useWebSocket'
import backend from '@/api/backend'

const droneStore = useDroneStore()
const connectionApi = backend.connection
const udpApi = backend.udp
const logApi = backend.log

// WebSocket连接
const { isConnected: wsConnected, lastMessage } = useWebSocket()

// UDP连接状态
const isConnected = ref(false)

// 协议和本地配置
const protocol = ref('udp')
const listenAddress = ref('0.0.0.0')  // 地面站监听地址（支持修改）
const hostPort = ref(30509)           // 地面站监听端口

// 远程端配置
const remoteIp = ref('127.0.0.2')
const commandRecvPort = ref(18504)   // COMMAND_RECV_PORT - 飞控接收地面站指令
const sendOnlyPort = ref(18506)       // SEND_ONLY_PORT - 飞控发送遥测
const lidarSendPort = ref(18507)      // LIDAR_SEND_PORT - LiDAR下行
const planningSendPort = ref(18510)  // PLANNING_SEND_PORT - 规划指令
const planningRecvPort = ref(18511)  // PLANNING_RECV_PORT - 规划响应

// 数据记录配置
const logDirectory = ref('')
const logFileName = ref('')  // 自定义日志文件名
const autoRecord = ref(false)
const logFormat = ref('csv')
const logLevel = ref('1')

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
      listenAddress.value = connConfig.data.listenAddress || '0.0.0.0'
      hostPort.value = connConfig.data.hostPort
      remoteIp.value = connConfig.data.remoteIp
      commandRecvPort.value = connConfig.data.commandRecvPort || 18504
      sendOnlyPort.value = connConfig.data.sendOnlyPort
      lidarSendPort.value = connConfig.data.lidarSendPort
      planningSendPort.value = connConfig.data.planningSendPort
      planningRecvPort.value = connConfig.data.planningRecvPort
    }
    
    // 加载日志配置
    const logConfigData = await logApi.getConfig()
    if (logConfigData.data) {
      logDirectory.value = logConfigData.data.logDirectory || ''
      logFileName.value = logConfigData.data.logFileName || ''
      autoRecord.value = logConfigData.data.autoRecord
      logFormat.value = logConfigData.data.logFormat
      logLevel.value = logConfigData.data.logLevel
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    droneStore.addLog('加载配置失败: ' + error.message, 'error')
  } finally {
    loading.value = false
  }
}

/**
 * 保存连接配置（简化版 - 后端自动判断重启逻辑）
 */
const saveConnectionConfig = async () => {
  loading.value = true
  saveMessage.value = ''
  
  try {
    const config = {
      protocol: protocol.value,
      listenAddress: listenAddress.value,  // 新增：监听地址
      hostPort: hostPort.value,
      remoteIp: remoteIp.value,
      commandRecvPort: commandRecvPort.value,
      sendOnlyPort: sendOnlyPort.value,
      lidarSendPort: lidarSendPort.value,
      planningSendPort: planningSendPort.value,
      planningRecvPort: planningRecvPort.value
    }
    
    droneStore.addLog('保存连接配置...', 'info')
    
    // 直接调用后端API，后端会智能判断：
    // - 如果仅IP改变：只更新发送目标
    // - 如果端口改变：重启UDP服务器
    // - 如果两者都改变：重启并更新目标
    const result = await connectionApi.updateConfig(config)
    
    saveMessage.value = result.message
    saveSuccess.value = result.status === 'success'
    
    // 更新store中的配置
    droneStore.updateConfig(config)
    droneStore.addLog('连接配置已保存: ' + result.message, 'info')
    
  } catch (error) {
    console.error('保存连接配置失败:', error)
    saveMessage.value = '保存失败: ' + error.message
    saveSuccess.value = false
    droneStore.addLog('保存连接配置失败: ' + error.message, 'error')
  } finally {
    loading.value = false
    
    // 验证UDP状态
    try {
      const statusResult = await udpApi.getStatus()
      if (statusResult.data) {
        isConnected.value = statusResult.data.connected
      }
    } catch (error) {
      console.warn('验证UDP状态失败:', error)
    }
    
    // 5秒后清除消息
    if (saveSuccess.value) {
      setTimeout(() => saveMessage.value = '', 5000)
    }
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
 * 保存日志配置
 */
const saveLogConfig = async () => {
  loading.value = true
  saveMessage.value = ''
  try {
    const config = {
      logDirectory: '',
      logFileName: logFileName.value,
      autoRecord: autoRecord.value,
      logFormat: logFormat.value,
      logLevel: logLevel.value
    }
    
    // 移除目录检查，默认保存到项目Log目录
    
    const result = await logApi.updateConfig(config)
    saveMessage.value = result.message
    saveSuccess.value = result.status === 'success'
    
    // 更新store中的配置
    droneStore.updateConfig({ logConfig: config })
    droneStore.addLog('日志配置已保存: ' + result.message, 'info')
  } catch (error) {
    console.error('保存日志配置失败:', error)
    saveMessage.value = '保存失败: ' + error.message
    saveSuccess.value = false
    droneStore.addLog('保存日志配置失败: ' + error.message, 'error')
  } finally {
    loading.value = false
    // 3秒后清除消息
    if (saveSuccess.value) {
      setTimeout(() => saveMessage.value = '', 3000)
    }
  }
}

/**
 * 切换连接状态（点击连接/断开按钮）
 */
const toggleConnection = async () => {
  if (isConnected.value) {
    // 断开连接
    await disconnectUDP()
  } else {
    // 建立连接
    await saveConnectionConfig()
  }
}

/**
 * 监听WebSocket消息，处理UDP状态变化
 */
watch(() => lastMessage?.value, (newMessage) => {
  if (!newMessage) return
  
  try {
    const data = typeof newMessage === 'string' ? JSON.parse(newMessage) : newMessage
    
    if (data?.type === 'udp_status_change') {
      const previousState = isConnected.value
      isConnected.value = (data.status === 'connected')
      
      // 状态变化时记录日志
      if (previousState !== isConnected.value) {
        if (isConnected.value) {
          droneStore.addLog('UDP连接已建立', 'success')
          droneStore.addLog(`监听端口: ${data.config?.hostPort}, 告知端口: ${data.config?.sendOnlyPort}`, 'info')
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

/**
 * 清除文件名
 */
const clearFileName = () => {
  logFileName.value = ''
  droneStore.addLog('已清除自定义日志文件名', 'info')
}

/**
 * 浏览文件选择器
 * 注意：由于Web安全限制，无法在浏览器中直接调用原生文件选择对话框
 * 用户需要手动输入目录路径
 */
const browseDirectory = () => {
  // 在纯Web环境中，无法通过JavaScript直接获取系统目录路径
  // 这是一个浏览器安全限制
  // 解决方案：
  // 1. 让用户手动输入目录路径（当前实现）
  // 2. 如果在Electron环境中，可以通过IPC调用原生对话框
  // 3. 如果需要在Web环境中实现，需要后端提供目录浏览API
  
  alert('提示：\n\n请直接在输入框中手动输入日志存储目录路径。\n\n例如：\n• Windows: E:/Logs 或 D:/MissionLogs\n• Linux/macOS: /home/user/logs 或 ./logs\n\n注意：确保指定的目录存在且有写入权限。')
}

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
    console.warn('获取UDP状态失败:', error)
  }
})
</script>

<style scoped>
.config-panel {
  padding: 15px;
  height: 100vh;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 8px;
}

/* 自定义滚动条样式 */
.content-scroll::-webkit-scrollbar {
  width: 6px;
}

.content-scroll::-webkit-scrollbar-track {
  background: rgba(50, 51, 61, 0.5);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb {
  background: rgba(100, 102, 118, 0.8);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 102, 118, 1);
}

.config-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-title {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 15px 0;
  padding-bottom: 10px;
  border-bottom: 2px solid #3288fa;
}

.config-section {
  background: rgba(40, 40, 40, 0.5);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.section-title {
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #333333;
}

.config-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subsection-title {
  font-size: 12px;
  color: #3288fa;
  font-weight: 600;
  margin-bottom: 8px;
  background: rgba(50, 136, 250, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

.config-subsection {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  background: rgba(30, 30, 30, 0.5);
  border-radius: 6px;
  border: 1px solid #333;
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
  color: #cccccc;
  font-size: 12px;
  min-width: 110px;
}

.config-input {
  background: rgba(20, 20, 20, 0.8);
  border: 1px solid #444444;
  border-radius: 4px;
  color: #ffffff;
  padding: 6px 10px;
  font-size: 12px;
  width: 140px;
  transition: all 0.2s;
}

.config-input:focus {
  border-color: #3288fa;
  outline: none;
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
  background: #3288fa;
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
  background: #2676ea;
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
  background-color: #555555;
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
  background-color: #3288fa;
}

.toggle-switch input:checked + .slider:before {
  transform: translateX(18px);
}

.config-actions {
  padding: 12px 0;
  border-top: 1px solid rgba(255,255,255,0.05);
}

.action-message {
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  margin-top: 12px;
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
  color: #ff5252;
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
  color: #4caf50;
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
  color: #d32f2f;
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
  background: rgba(50, 136, 250, 0.2);
  border: 1px solid #3288fa;
  border-radius: 6px;
  color: #3288fa;
  padding: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s;
}

.apply-btn:hover {
  background: rgba(50, 136, 250, 0.3);
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
  color: #999;
  font-size: 11px;
  line-height: 1.4;
  background: rgba(50, 136, 250, 0.1);
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 3px solid #3288fa;
}
</style>