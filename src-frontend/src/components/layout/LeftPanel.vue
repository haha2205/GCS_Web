<template>
  <div class="left-sidebar">
    <!-- 1. 侧导航条（60px 固定宽度）-->
    <div class="sidebar-icons">
      <div
        v-for="mode in modes"
        :key="mode.id"
        class="icon-btn"
        :class="{ active: activeMode === mode.id || (mode.id === 'workbench' && workbenchVisible) }"
        @click="toggleMode(mode.id)"
        :title="mode.label"
      >
        <span class="icon">{{ mode.icon }}</span>
        <span v-if="activeMode === mode.id || (mode.id === 'workbench' && workbenchVisible)" class="active-indicator"></span>
      </div>
    </div>
    
    <!-- 2. 内容抽屉（统一单面板切换） -->
    <div class="drawer-content" v-if="activeMode">
      <transition name="slide-in" mode="out-in">
        <ConfigModule
          v-if="activeMode === 'config'"
          key="config"
          :closePanel="() => closePanel('config')"
        />
        <CommandModule
          v-else-if="activeMode === 'command'"
          key="command"
          :closePanel="() => closePanel('command')"
        />
        <ParamsModule
          v-else
          key="params"
          :closePanel="() => closePanel('params')"
        />
      </transition>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import ConfigModule from './LeftConfigPanel.vue'
import CommandModule from './LeftCommandPanel.vue'
import ParamsModule from './LeftParamsPanel.vue'

const modes = [
  { id: 'config', icon: '⚙️', label: '配置' },
  { id: 'workbench', icon: '🧪', label: '实验工作台' },
  { id: 'command', icon: '🚀', label: '飞控指令' },
  { id: 'params', icon: '🔧', label: '参数配置' }
]

const activeMode = ref('command')
const workbenchVisible = ref(false)

function toggleMode(mode) {
  if (mode === 'workbench') {
    workbenchVisible.value = !workbenchVisible.value
    window.dispatchEvent(new CustomEvent('toggle-workbench', {
      detail: { visible: workbenchVisible.value }
    }))
    return
  }

  activeMode.value = activeMode.value === mode ? null : mode
}

function closePanel(mode) {
  if (activeMode.value === mode) {
    activeMode.value = null
  }
}

// 导出关闭方法供子组件调用
defineExpose({
  closePanel
})

const syncWorkbenchVisibility = (event) => {
  workbenchVisible.value = !!event.detail?.visible
}

onMounted(() => {
  window.addEventListener('workbench-visibility-change', syncWorkbenchVisibility)
})

onUnmounted(() => {
  window.removeEventListener('workbench-visibility-change', syncWorkbenchVisibility)
})
</script>

<style scoped>
/* ==================== 左侧栏容器 ==================== */
.left-sidebar {
  display: flex;
  align-items: flex-start;
  flex-shrink: 0;
  height: 100%;  /* 关键修复：继承父容器高度 */
}

/* ==================== 侧边导航条 ==================== */
.sidebar-icons {
  width: 60px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--border-color);
  border-radius: 8px 0 0 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 10px 0;
  backdrop-filter: blur(10px);
  height: 100%;  /* 确保图标栏占满高度 */
}

.icon-btn {
  width: 50px;
  height: 50px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 6px;
  position: relative;
}

.icon-btn:hover {
  background: rgba(37, 99, 235, 0.1);
}

.icon-btn.active {
  background: rgba(37, 99, 235, 0.14);
}

.icon {
  font-size: 24px;
}

.active-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: var(--accent-color);
  border-radius: 0 2px 2px 0;
}

/* ==================== 内容抽屉 ==================== */
.drawer-content {
  min-width: 320px;
  width: 320px;
  max-width: 320px;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 8px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid var(--border-color);
  border-left: none;
  border-radius: 8px;
  overflow: hidden;
  backdrop-filter: blur(10px);
  box-shadow: 4px 0 18px rgba(15, 23, 42, 0.08);
}

/* ==================== 滚动条样式 ==================== */
.drawer-content::-webkit-scrollbar {
  width: 6px;
}

.drawer-content::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.8);
}

.drawer-content::-webkit-scrollbar-thumb {
  background: rgba(37, 99, 235, 0.45);
  border-radius: 3px;
}

.drawer-content::-webkit-scrollbar-thumb:hover {
  background: rgba(37, 99, 235, 0.72);
}

/* ==================== 动态加载的面板样式 ==================== */
.drawer-content > * {
  min-height: 0;
  overflow: hidden;
  height: 100%;
}

/* ==================== 过渡动画 ==================== */
.slide-in-enter-active {
  transition: all 0.3s ease;
}

.slide-in-leave-active {
  transition: all 0.3s ease;
}

.slide-in-enter-from {
  transform: translateX(-30px);
  opacity: 0;
}

.slide-in-leave-to {
  transform: translateX(-30px);
  opacity: 0;
}
</style>