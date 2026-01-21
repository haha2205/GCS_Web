<template>
  <div class="app-layout">
    <!-- [左侧固定区域] 左侧栏 -->
    <aside class="layout-left">
      <LeftPanel />
    </aside>
 
    <!-- [右侧舞台区域] -->
    <main class="layout-right">
      
      <!-- 顶部状态栏（固定） -->
      <header class="top-bar">
        <TopStatusBar />
        <div class="view-toggles">
          <!-- 控制右侧面板显示的开关 -->
          <button
            class="icon-btn"
            :class="{ active: showMonitorPanel }"
            @click="showMonitorPanel = !showMonitorPanel"
            title="切换监控面板"
          >
            📊
          </button>
        </div>
      </header>
 
      <!-- 中间内容区域（flex布局） -->
      <div class="content-area">
        <!-- 3D视图容器（自适应） -->
        <div class="viz-container" :style="vizContainerStyle">
          <HomeView />
        </div>
        
        <!-- 可调整的分隔线（仅当右侧面板显示且非最大化时显示） -->
        <LayoutSplitter
          v-if="showMonitorPanel && !isMonitorMaximized"
          direction="vertical"
          @resize="onSplitterResize"
        />
        
        <!-- 右侧监控面板（与3D视图动态共享空间） -->
        <transition name="panel-slide">
          <div
            v-if="showMonitorPanel"
            class="monitor-panel"
            :class="{ 'is-maximized': isMonitorMaximized }"
            :style="monitorPanelStyle"
          >
            <RightPanel
              :is-maximized="isMonitorMaximized"
              @toggle-maximize="isMonitorMaximized = !isMonitorMaximized"
              @toggle-hide="showMonitorPanel = false"
            />
          </div>
        </transition>
      </div>
 
      <!-- 底部功能面板（固定） -->
      <footer class="bottom-panel" :class="{ 'is-collapsed': isBottomCollapsed }">
        <!-- 折叠把手：点击折叠/展开 -->
        <div class="panel-handle" @click="isBottomCollapsed = !isBottomCollapsed">
          <span class="handle-text">{{ isBottomCollapsed ? '▲ 展开控制台' : '▼ 收起' }}</span>
        </div>
        
        <!-- 只有在展开状态时才显示底部控制栏内容 -->
        <div class="panel-body" v-show="!isBottomCollapsed">
          <BottomControlBar />
        </div>
      </footer>
 
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import LeftPanel from './LeftPanel.vue'
import TopStatusBar from './TopStatusBar.vue'
import RightPanel from './RightPanel.vue'
import BottomControlBar from './BottomControlBar.vue'
import HomeView from '@/views/HomeView.vue'
import LayoutSplitter from './LayoutSplitter.vue'
import { useDroneStore } from '@/store/drone'

// 状态控制
const showMonitorPanel = ref(true)
const isMonitorMaximized = ref(false)
const isBottomCollapsed = ref(false)

// 3D容器和右侧面板的flex值（总和为1）
const vizFlex = ref(3)      // 3D区域默认占3份
const panelFlex = ref(1)    // 右侧面板默认占1份

// 计算3D容器和右侧面板的flex分配
const vizContainerStyle = computed(() => {
  if (!showMonitorPanel.value) {
    return { flex: '1' }
  }
  if (isMonitorMaximized.value) {
    return { flex: '0', overflow: 'hidden' }
  }
  // 使用flex-grow实现动态空间共享：3D区域自适应剩余空间
  return { flex: vizFlex.value.toString() }
})

const monitorPanelStyle = computed(() => {
  if (!showMonitorPanel.value) {
    return { flex: '0', display: 'none' }
  }
  if (isMonitorMaximized.value) {
    return { flex: '3' }
  }
  // 使用flex-grow实现动态空间共享：右侧面板使用flex比例，允许在合理范围内调整
  return { flex: panelFlex.value.toString(), minWidth: '300px', maxWidth: '70%' }
})

// 分隔线调整回调 - 根据拖动位置调整flex比例
const onSplitterResize = (pixelWidth) => {
  // pixelWidth是右侧面板的像素宽度（250-600之间）
  // 计算基于容器宽度的比例
  const containerWidth = document.querySelector('.content-area')?.offsetWidth || window.innerWidth
  const percentage = Math.min(70, Math.max(20, (pixelWidth / containerWidth) * 100))
  
  // 计算flex比例：右侧面板占1份，3D区域占根据百分比比例
  // 使用相对比值，例如：右侧25%时，3D区为75%，比例为3:1
  if (percentage > 0) {
    panelFlex.value = 1
    vizFlex.value = Math.round((100 - percentage) / percentage * 10) / 10  // 保留一位小数
  }
}

// Drone store初始化
const droneStore = useDroneStore()

// 监听面板控制事件
onMounted(() => {
  // 初始化WebSocket连接
  console.log('ApolloLayout mounted, 初始化WebSocket连接...')
  droneStore.connect()
  
  window.addEventListener('panel-toggle-right', () => {
    showMonitorPanel.value = !showMonitorPanel.value
  })
  window.addEventListener('panel-fullscreen-center', () => {
    // 中央全屏逻辑可以在这里实现
  })
  window.addEventListener('panel-reset', () => {
    showMonitorPanel.value = true
    isMonitorMaximized.value = false
    isBottomCollapsed.value = false
    vizFlex.value = 3
    panelFlex.value = 1
  })
})

onUnmounted(() => {
  // 断开WebSocket连接
  console.log('ApolloLayout unmounted, 断开WebSocket连接...')
  droneStore.disconnect()
})
</script>

<style scoped>
/* ==================== 根容器 ==================== */
.app-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background-color: #000;
  overflow: hidden;
}

/* ==================== 左侧固定区域 ==================== */
.layout-left {
  flex: 0 0 auto;
  height: 100%;
  z-index: 20;
  border-right: 1px solid #333;
}

/* ==================== 右侧舞台区域 ==================== */
.layout-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ==================== 顶部状态栏（固定） ==================== */
.top-bar {
  flex: 0 0 50px;
  background: rgba(20, 20, 20, 0.95);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #333;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 30;
}

.view-toggles {
  display: flex;
  gap: 8px;
}

.icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(50, 50, 50, 0.5);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 6px;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
}

.icon-btn:hover {
  background: rgba(50, 136, 250, 0.3);
  color: #3288fa;
}

.icon-btn.active {
  background: rgba(50, 136, 250, 0.4);
  color: #3288fa;
  border-color: #3288fa;
  box-shadow: 0 0 8px rgba(50, 136, 250, 0.3);
}

/* ==================== 中间内容区域（flex布局） ==================== */
.content-area {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  position: relative;
  width: 100%;
}

/* 3D视图容器 - 使用flex动态共享空间 */
.viz-container {
  min-width: 200px;
  min-height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: flex 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 右侧监控面板 - 使用flex动态共享空间 */
.monitor-panel {
  height: 100%;
  background: rgba(25, 25, 25, 0.98);
  border-left: 2px solid #444;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: flex 0.3s cubic-bezier(0.16, 1, 0.3, 1), width 0.3s ease;
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.3);
}

.monitor-panel.is-maximized {
  border-left: 2px solid #3288fa;
  box-shadow: 0 0 30px rgba(50, 136, 250, 0.3);
}

/* Vue 动画过渡类 */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.3s ease;
}

.panel-slide-enter-from {
  width: 0;
  opacity: 0;
}

.panel-slide-enter-to {
  opacity: 1;
}

.panel-slide-leave-to {
  width: 0;
  opacity: 0;
  overflow: hidden;
}

/* ==================== 底部功能面板（固定） ==================== */
.bottom-panel {
  flex: 0 0 auto;
  background: rgba(20, 20, 20, 0.98);
  border-top: 1px solid #333;
  display: flex;
  flex-direction: column;
  z-index: 30;
  transition: height 0.3s ease;
}

.bottom-panel:not(.is-collapsed) {
  height: 160px;
}

.bottom-panel.is-collapsed {
  height: 28px;
}

.panel-handle {
  height: 28px;
  background: rgba(40, 40, 40, 0.9);
  color: #888;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  flex-shrink: 0;
}

.panel-handle:hover {
  color: #fff;
  background: rgba(50, 136, 250, 0.2);
}

.handle-text {
  font-weight: 500;
  letter-spacing: 0.5px;
}

.panel-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>