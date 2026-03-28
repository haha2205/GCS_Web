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
        <div class="view-toggles" v-if="!showWorkbenchOverlay">
          <button
            class="icon-btn"
            :class="{ active: showMonitorPanel }"
            @click="showMonitorPanel = !showMonitorPanel"
            title="切换监控面板"
          >
            📊
          </button>
          <button
            v-if="showMonitorPanel"
            class="icon-btn"
            :class="{ active: showControlStatus }"
            @click="showControlStatus = !showControlStatus"
            title="显示控制状态"
          >
            🎛
          </button>
          <button
            v-if="showMonitorPanel"
            class="icon-btn"
            :class="{ active: showSystemPerformance }"
            @click="showSystemPerformance = !showSystemPerformance"
            title="显示系统性能"
          >
            ⚙
          </button>
          <button
            v-if="showMonitorPanel"
            class="icon-btn"
            :class="{ active: isMonitorMaximized }"
            @click="isMonitorMaximized = !isMonitorMaximized"
            title="最大化/最小化监控面板"
          >
            {{ isMonitorMaximized ? '🗗' : '🗖' }}
          </button>
        </div>
      </header>
 
      <!-- 中间内容区域（flex布局） -->
      <div class="content-area">
        <!-- 3D视图容器（自适应） -->
        <div class="viz-container" :style="vizContainerStyle">
          <HomeView />
        </div>

        <ExperimentWorkbenchOverlay
          :visible="showWorkbenchOverlay"
          @close="setWorkbenchOverlay(false)"
        />
        
        <!-- 可调整的分隔线（仅当右侧面板显示且非最大化时显示） -->
        <LayoutSplitter
          v-if="showMonitorPanel && !isMonitorMaximized && !showWorkbenchOverlay"
          direction="vertical"
          @resize="onSplitterResize"
        />
        
        <!-- 右侧监控面板（与3D视图动态共享空间） -->
        <transition name="panel-slide">
          <div
            v-if="showMonitorPanel && !showWorkbenchOverlay"
            class="monitor-panel"
            :class="{ 'is-maximized': isMonitorMaximized }"
            :style="monitorPanelStyle"
          >
            <RightPanel
              :is-maximized="isMonitorMaximized"
              :show-control-panel="showControlStatus"
              :show-system-panel="showSystemPerformance"
            />
          </div>
        </transition>
      </div>
 
      <!-- 底部功能面板（固定） -->
      <footer v-if="!showWorkbenchOverlay" class="bottom-panel" :class="{ 'is-collapsed': isBottomCollapsed }">
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
import ExperimentWorkbenchOverlay from '@/components/experiment/ExperimentWorkbenchOverlay.vue'
import { useDroneStore } from '@/store/drone'

// 状态控制
const showMonitorPanel = ref(true)
const isMonitorMaximized = ref(false)
const isBottomCollapsed = ref(false)
const showControlStatus = ref(true)
const showSystemPerformance = ref(true)
const showWorkbenchOverlay = ref(false)

// 默认把更多空间让给右侧监控，3D保留态势观察所需最小面积。
const vizFlex = ref(44)
const panelFlex = ref(56)

// 计算3D容器和右侧面板的flex分配
const vizContainerStyle = computed(() => {
  if (!showMonitorPanel.value) {
    return { flex: '1' }
  }
  if (isMonitorMaximized.value) {
    return { flex: '0', overflow: 'hidden' }
  }
  return {
    flex: `${vizFlex.value} 1 0%`,
    minWidth: '280px'
  }
})

const monitorPanelStyle = computed(() => {
  if (!showMonitorPanel.value) {
    return { flex: '0', display: 'none' }
  }
  if (isMonitorMaximized.value) {
    return { flex: '3' }
  }
  return {
    flex: `${panelFlex.value} 1 0%`,
    minWidth: '560px',
    maxWidth: '72%'
  }
})

const setWorkbenchOverlay = (visible) => {
  showWorkbenchOverlay.value = visible
  window.dispatchEvent(new CustomEvent('workbench-visibility-change', {
    detail: { visible }
  }))
}

// 分隔线调整回调 - 根据拖动位置调整flex比例
const onSplitterResize = (pixelWidth) => {
  const containerWidth = document.querySelector('.content-area')?.offsetWidth || window.innerWidth
  const percentage = Math.min(72, Math.max(42, (pixelWidth / containerWidth) * 100))

  if (percentage > 0) {
    panelFlex.value = Math.round(percentage)
    vizFlex.value = Math.round(100 - percentage)
  }
}

// Drone store初始化
const droneStore = useDroneStore()

const handleWorkbenchToggle = (event) => {
  const nextVisible = event.detail?.visible
  setWorkbenchOverlay(typeof nextVisible === 'boolean' ? nextVisible : !showWorkbenchOverlay.value)
}

// 监听面板控制事件
onMounted(() => {
  // 初始化WebSocket连接
  console.log('ApolloLayout mounted, 初始化WebSocket连接...')
  droneStore.connect()
  
  window.addEventListener('panel-toggle-right', () => {
    showMonitorPanel.value = !showMonitorPanel.value
  })
  window.addEventListener('toggle-workbench', handleWorkbenchToggle)
  window.addEventListener('panel-fullscreen-center', () => {
    // 中央全屏逻辑可以在这里实现
  })
  window.addEventListener('panel-reset', () => {
    showMonitorPanel.value = true
    isMonitorMaximized.value = false
    isBottomCollapsed.value = false
    showControlStatus.value = true
    showSystemPerformance.value = false
    vizFlex.value = 44
    panelFlex.value = 56
    setWorkbenchOverlay(false)
  })
})

onUnmounted(() => {
  // 断开WebSocket连接
  console.log('ApolloLayout unmounted, 断开WebSocket连接...')
  droneStore.disconnect()
  window.removeEventListener('toggle-workbench', handleWorkbenchToggle)
})
</script>

<style scoped>
/* ==================== 根容器 ==================== */
.app-layout {
  display: flex;
  width: 100vw;
  height: 100vh;
  background: linear-gradient(180deg, var(--surface-primary) 0%, #dde8f4 100%);
  overflow: hidden;
}

/* ==================== 左侧固定区域 ==================== */
.layout-left {
  flex: 0 0 auto;
  height: 100%;
  z-index: 20;
  border-right: 1px solid var(--border-color);
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
  flex: 0 0 56px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  z-index: 30;
}

.view-toggles {
  display: flex;
  gap: 8px;
}

.icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}

.icon-btn:hover {
  background: rgba(37, 99, 235, 0.1);
  color: var(--accent-color);
}

.icon-btn.active {
  background: rgba(37, 99, 235, 0.12);
  color: var(--accent-color);
  border-color: var(--accent-color);
  box-shadow: 0 0 10px rgba(37, 99, 235, 0.12);
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
  min-width: 0;
  min-height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: flex 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 右侧监控面板 - 使用flex动态共享空间 */
.monitor-panel {
  height: 100%;
  background: rgba(255, 255, 255, 0.94);
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: flex 0.3s cubic-bezier(0.16, 1, 0.3, 1), width 0.3s ease;
  box-shadow: -4px 0 16px rgba(15, 23, 42, 0.08);
}

.monitor-panel.is-maximized {
  border-left: 2px solid var(--accent-color);
  box-shadow: 0 0 24px rgba(37, 99, 235, 0.12);
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
  background: rgba(248, 250, 252, 0.88);
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  z-index: 30;
  transition: height 0.3s ease;
}

.bottom-panel:not(.is-collapsed) {
  height: 188px;
}

.bottom-panel.is-collapsed {
  height: 28px;
}

.panel-handle {
  height: 28px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-secondary);
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