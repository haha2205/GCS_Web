<template>
  <div class="test-page">
    <h1>前端组件测试页面</h1>
    
    <div class="test-section">
      <h2>✅ 基础显示测试</h2>
      <p>如果您能看到这段文字，说明 Vue 基础功能正常。</p>
      <p>当前时间：{{ currentTime }}</p>
      <button @click="handleClick">点击测试按钮</button>
      <p v-if="clicked" style="color: #00C853;">按钮点击成功！✓</p>
    </div>
    
    <div class="test-section">
      <h2>📦 组件加载测试</h2>
      <div class="test-item">
        <span>ApolloLayout 组件：</span>
        <span :class="componentStatus.ApolloLayout ? 'status-ok' : 'status-fail'">
          {{ componentStatus.ApolloLayout ? '✓ 加载成功' : '✗ 未加载' }}
        </span>
      </div>
      <div class="test-item">
        <span>TopStatusBar 组件：</span>
        <span :class="componentStatus.TopStatusBar ? 'status-ok' : 'status-fail'">
          {{ componentStatus.TopStatusBar ? '✓ 加载成功' : '✗ 未加载' }}
        </span>
      </div>
      <div class="test-item">
        <span>ApolloSidebar 组件：</span>
        <span :class="componentStatus.ApolloSidebar ? 'status-ok' : 'status-fail'">
          {{ componentStatus.ApolloSidebar ? '✓ 加载成功' : '✗ 未加载' }}
        </span>
      </div>
      <div class="test-item">
        <span>RightMonitorPanel 组件：</span>
        <span :class="componentStatus.RightMonitorPanel ? 'status-ok' : 'status-fail'">
          {{ componentStatus.RightMonitorPanel ? '✓ 加载成功' : '✗ 未加载' }}
        </span>
      </div>
      <div class="test-item">
        <span>BottomControlBar 组件：</span>
        <span :class="componentStatus.BottomControlBar ? 'status-ok' : 'status-fail'">
          {{ componentStatus.BottomControlBar ? '✓ 加载成功' : '✗ 未加载' }}
        </span>
      </div>
    </div>
    
    <div class="test-section">
      <h2>🔌 WebSocket 测试</h2>
      <div class="test-item">
        <span>连接状态：</span>
        <span :class="droneStore.isConnected ? 'status-ok' : 'status-fail'">
          {{ droneStore.isConnected ? '✓ 已连接' : '✗ 未连接' }}
        </span>
      </div>
      <div class="test-item">
        <span>WebSocket URL：</span>
        <span>ws://localhost:8000/ws/drone</span>
      </div>
      <button @click="connectWebSocket" :disabled="droneStore.isConnected">
        {{ connecting ? '连接中...' : '连接 WebSocket' }}
      </button>
    </div>
    
    <div class="test-section">
      <h2>🚀 返回主界面</h2>
      <button @click="goToMain">点击返回 Apollo 主界面</button>
    </div>
    
    <div class="test-info">
      <h3>🔍 调试信息</h3>
      <p>如果 Apollo 界面无法显示，请：</p>
      <ol>
        <li>按 F12 打开浏览器开发者工具</li>
        <li>查看 Console 标签页是否有红色错误</li>
        <li>查看 Network 标签页确认资源是否加载</li>
        <li>按 Ctrl + Shift + R 强制刷新页面</li>
        <li>清空浏览器缓存后重试</li>
      </ol>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDroneStore } from '@/store/drone'

const router = useRouter()
const droneStore = useDroneStore()

const currentTime = ref('')
const clicked = ref(false)
const connecting = ref(false)

const componentStatus = ref({
  ApolloLayout: true,
  TopStatusBar: true,
  ApolloSidebar: true,
  RightMonitorPanel: true,
  BottomControlBar: true
})

let timeInterval = null

const handleClick = () => {
  clicked.value = !clicked.value
}

const connectWebSocket = async () => {
  connecting.value = true
  try {
    droneStore.connect()
    setTimeout(() => {
      connecting.value = false
    }, 1000)
  } catch (error) {
    console.error('WebSocket 连接失败:', error)
    connecting.value = false
  }
}

const goToMain = () => {
  router.push('/dashboard')
}

onMounted(() => {
  // 更新时间
  timeInterval = setInterval(() => {
    const now = new Date()
    currentTime.value = now.toLocaleString('zh-CN')
  }, 1000)
  
  console.log('TestPage 已挂载')
  console.log('当前路由:', router.currentRoute.value.path)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.test-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

h1 {
  text-align: center;
  color: #00bcd4;
  margin-bottom: 40px;
  font-size: 28px;
}

h2 {
  color: #00bcd4;
  margin: 30px 0 15px 0;
  font-size: 20px;
}

h3 {
  color: #ff9800;
  margin: 20px 0 10px 0;
  font-size: 16px;
}

.test-section {
  background-color: #1f1f1f;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #333;
}

.test-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #333;
}

.test-item:last-child {
  border-bottom: none;
}

.test-item span:first-child {
  color: #b0b0b0;
}

.status-ok {
  color: #00c853;
  font-weight: bold;
}

.status-fail {
  color: #ff5252;
  font-weight: bold;
}

button {
  background-color: #00bcd4;
  color: #ffffff;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  margin-top: 10px;
  transition: all 0.2s;
}

button:hover {
  background-color: #008ba3;
  transform: translateY(-2px);
}

button:disabled {
  background-color: #333;
  cursor: not-allowed;
  transform: none;
}

.test-info {
  background-color: #2a2a2a;
  border-radius: 8px;
  padding: 20px;
  border-left: 4px solid #ff9800;
}

.test-info p {
  margin-bottom: 10px;
  color: #b0b0b0;
}

.test-info ol {
  margin-left: 20px;
  color: #b0b0b0;
}

.test-info li {
  margin: 8px 0;
  line-height: 1.5;
}
</style>