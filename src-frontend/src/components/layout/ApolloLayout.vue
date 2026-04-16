<template>
  <div class="app-layout">
    <aside class="layout-left">
      <LeftPanel />
    </aside>

    <main class="layout-right">
      <header class="top-bar">
        <TopStatusBar />
        <div class="view-toggles">
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
            class="icon-btn health-btn"
            :class="[{ active: showLinkHealth }, trafficHealthLevel]"
            @click="toggleLinkHealth()"
            title="显示链路健康"
          >
            <span class="health-icon">⛓</span>
            <span class="health-dot" :class="trafficHealthLevel"></span>
          </button>
          <button
            v-if="showMonitorPanel"
            class="icon-btn health-btn"
            :class="[{ active: showOnlineAnalysisDrawer }, onlineAnalysisLevel]"
            @click="toggleOnlineAnalysisDrawer()"
            title="显示在线评测"
          >
            <span class="health-icon">◔</span>
            <span class="health-dot" :class="onlineAnalysisLevel"></span>
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

      <div class="content-area">
        <div class="viz-container" :style="vizContainerStyle">
          <HomeView />
        </div>

        <LayoutSplitter
          v-if="showMonitorPanel && !isMonitorMaximized"
          position="right"
          @resize="onSplitterResize"
        />

        <transition name="panel-slide">
          <div
            v-if="showMonitorPanel"
            class="monitor-panel"
            :class="{ 'is-maximized': isMonitorMaximized }"
            :style="monitorPanelStyle"
          >
            <RightPanel
              :is-maximized="isMonitorMaximized"
              :show-control-panel="showControlStatus"
              :show-system-panel="showSystemPerformance"
              :show-link-health="showLinkHealth"
              :show-online-analysis="showOnlineAnalysisDrawer"
              @close-link-health="showLinkHealth = false"
              @close-online-analysis="showOnlineAnalysisDrawer = false"
            />
          </div>
        </transition>
      </div>

      <footer class="bottom-panel" :class="{ 'is-collapsed': isBottomCollapsed }">
        <div class="panel-handle" @click="isBottomCollapsed = !isBottomCollapsed">
          <span class="handle-text">{{ isBottomCollapsed ? '▲ 展开控制台' : '▼ 收起' }}</span>
        </div>

        <div class="panel-body" v-show="!isBottomCollapsed">
          <BottomControlBar />
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import LeftPanel from './LeftPanel.vue'
import TopStatusBar from './TopStatusBar.vue'
import RightPanel from './RightPanel.vue'
import BottomControlBar from './BottomControlBar.vue'
import HomeView from '@/views/HomeView.vue'
import LayoutSplitter from './LayoutSplitter.vue'
import { useDroneStore } from '@/store/drone'

const droneStore = useDroneStore()

const showMonitorPanel = ref(true)
const isMonitorMaximized = ref(false)
const isBottomCollapsed = ref(false)
const showControlStatus = ref(true)
const showSystemPerformance = ref(true)
const showLinkHealth = ref(false)
const showOnlineAnalysisDrawer = ref(false)
const vizFlex = ref(44)
const panelFlex = ref(56)
const trafficHealthLevel = computed(() => droneStore.trafficHealthLevel)
const onlineAnalysisLevel = computed(() => {
  if (!droneStore.onlineAnalysis.enabled) return 'idle'
  if (droneStore.onlineAnalysis.ready) return 'healthy'
  return 'warning'
})

const vizContainerStyle = computed(() => {
  if (!showMonitorPanel.value) return { flex: '1' }
  if (isMonitorMaximized.value) return { flex: '0', overflow: 'hidden' }
  return { flex: `${vizFlex.value} 1 0%`, minWidth: '280px' }
})

const monitorPanelStyle = computed(() => {
  if (!showMonitorPanel.value) return { flex: '0', display: 'none' }
  if (isMonitorMaximized.value) return { flex: '1 1 auto', width: '100%' }
  return { flex: `${panelFlex.value} 1 0%`, minWidth: '560px', maxWidth: '72%' }
})

const onSplitterResize = (pixelWidth) => {
  const containerWidth = document.querySelector('.content-area')?.offsetWidth || window.innerWidth
  const percentage = Math.min(72, Math.max(42, (pixelWidth / containerWidth) * 100))
  if (percentage > 0) {
    panelFlex.value = Math.round(percentage)
    vizFlex.value = Math.round(100 - percentage)
  }
}

const toggleLinkHealth = () => {
  const next = !showLinkHealth.value
  showLinkHealth.value = next
  if (next) {
    showOnlineAnalysisDrawer.value = false
  }
}

const toggleOnlineAnalysisDrawer = () => {
  const next = !showOnlineAnalysisDrawer.value
  showOnlineAnalysisDrawer.value = next
  if (next) {
    showLinkHealth.value = false
  }
}

onMounted(() => {
  droneStore.connect()
})
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.layout-left {
  flex: 0 0 auto;
  height: 100%;
  padding: 12px 0 12px 12px;
  z-index: 4;
}

.layout-right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  padding: 8px 12px 12px 10px;
  gap: 8px;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex: 0 0 auto;
}

.view-toggles {
  display: flex;
  gap: 8px;
}

.icon-btn {
  position: relative;
  width: 34px;
  height: 34px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  cursor: pointer;
}

.icon-btn.active {
  background: rgba(37, 99, 235, 0.12);
}

.health-btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.health-icon {
  font-size: 15px;
  line-height: 1;
}

.health-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  border: 1.5px solid rgba(255, 255, 255, 0.95);
  background: #94a3b8;
}

.health-dot.healthy {
  background: #16a34a;
}

.health-dot.warning,
.health-dot.watch {
  background: #d97706;
}

.health-dot.blocked,
.health-dot.stale {
  background: #dc2626;
}

.health-dot.offline,
.health-dot.idle {
  background: #94a3b8;
}

.content-area {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 0;
  position: relative;
  overflow: hidden;
}

.viz-container {
  min-width: 0;
  min-height: 0;
  border-radius: 12px;
  overflow: hidden;
}

.monitor-panel {
  min-height: 0;
  overflow: hidden;
  padding-left: 10px;
}

.monitor-panel.is-maximized {
  padding-left: 0;
}

.bottom-panel {
  flex: 0 0 200px;
  min-height: 54px;
  transition: flex-basis 0.2s ease;
}

.bottom-panel.is-collapsed {
  flex-basis: 34px;
}

.panel-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}

.panel-body {
  height: calc(100% - 28px);
}
</style>