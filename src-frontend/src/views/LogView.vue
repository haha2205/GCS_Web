<template>
  <div class="log-view">
    <div class="log-container">
      <div class="log-header">
        <h2>系统日志</h2>
        <div class="log-controls">
          <select v-model="logLevel" @change="filterLogs">
            <option value="all">全部</option>
            <option value="info">信息</option>
            <option value="warning">警告</option>
            <option value="error">错误</option>
          </select>
          <button class="clear-btn" @click="clearLogs">清空日志</button>
        </div>
      </div>
      <div class="log-content" ref="logContainer">
        <div 
          v-for="(log, index) in filteredLogs" 
          :key="index" 
          :class="['log-item', `log-${log.level}`]"
        >
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span class="log-level">{{ log.level }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'

const logLevel = ref('all')
const logContainer = ref(null)

const logs = ref([
  { level: 'info', message: '系统启动中...', timestamp: Date.now() - 60000 },
  { level: 'info', message: '正在连接 WebSocket 服务器...', timestamp: Date.now() - 50000 },
  { level: 'info', message: '已连接到后端服务器 http://localhost:8000', timestamp: Date.now() - 45000 },
  { level: 'warning', message: '未检测到飞控信号', timestamp: Date.now() - 30000 },
  { level: 'info', message: '等待飞控连接中...', timestamp: Date.now() - 20000 },
  { level: 'info', message: '系统初始化完成', timestamp: Date.now() - 10000 }
])

const filteredLogs = computed(() => {
  if (logLevel.value === 'all') {
    return logs.value
  }
  return logs.value.filter(log => log.level === logLevel.value)
})

const formatTime = (timestamp) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

const filterLogs = () => {
  console.log('过滤日志:', logLevel.value)
}

const clearLogs = () => {
  logs.value = []
  console.log('日志已清空')
}

onMounted(() => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.log-view {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(13, 13, 13, 0.6);
  border-radius: 8px;
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background: rgba(31, 31, 31, 0.8);
  border-bottom: 1px solid #424242;
}

.log-header h2 {
  color: #00BCD4;
  margin: 0;
  font-size: 18px;
}

.log-controls {
  display: flex;
  gap: 10px;
}

.log-controls select {
  padding: 6px 12px;
  background: rgba(13, 13, 13, 0.8);
  border: 1px solid #424242;
  border-radius: 4px;
  color: #ffffff;
  cursor: pointer;
}

.log-controls select:focus {
  outline: none;
  border-color: #00BCD4;
}

.clear-btn {
  padding: 6px 16px;
  background: #f44336;
  border: none;
  border-radius: 4px;
  color: #ffffff;
  cursor: pointer;
  font-size: 13px;
}

.clear-btn:hover {
  background: #d32f2f;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px 20px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.log-content::-webkit-scrollbar {
  width: 8px;
}

.log-content::-webkit-scrollbar-track {
  background: rgba(13, 13, 13, 0.6);
}

.log-content::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

.log-content::-webkit-scrollbar-thumb:hover {
  background: #616161;
}

.log-item {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid rgba(66, 66, 66, 0.3);
}

.log-time {
  color: #B0BEC5;
  width: 90px;
  margin-right: 15px;
}

.log-level {
  width: 60px;
  margin-right: 15px;
  font-weight: bold;
}

.log-info .log-level {
  color: #2196F3;
}

.log-warning .log-level {
  color: #FF9800;
}

.log-error .log-level {
  color: #f44336;
}

.log-message {
  flex: 1;
  color: #E0E0E0;
}
</style>