<template>
  <div class="left-sidebar">
    <!-- 1. 侧导航条（60px 固定宽度）-->
    <div class="sidebar-icons">
      <div
        v-for="mode in modes"
        :key="mode.id"
        class="icon-btn"
        :class="{ active: activeModes.includes(mode.id) }"
        @click="toggleMode(mode.id)"
        :title="mode.label"
      >
        <span class="icon">{{ mode.icon }}</span>
        <span v-if="activeModes.includes(mode.id)" class="active-indicator"></span>
      </div>
    </div>
    
    <!-- 2. 内容抽屉（自适应高度和宽度）-->
    <div class="drawer-content" v-if="activeModes.length > 0">
      <TransitionGroup name="slide-in">
        <ConfigModule
          v-if="activeModes.includes('config')"
          key="config"
          :style="panelFlexStyle"
          :closePanel="() => closePanel('config')"
        />
        <CommandModule
          v-if="activeModes.includes('command')"
          key="command"
          :style="panelFlexStyle"
          :closePanel="() => closePanel('command')"
        />
        <MissionModule
          v-if="activeModes.includes('mission')"
          key="mission"
          :style="panelFlexStyle"
          :closePanel="() => closePanel('mission')"
        />
        <ParamsModule
          v-if="activeModes.includes('params')"
          key="params"
          :style="panelFlexStyle"
          :closePanel="() => closePanel('params')"
        />
        <ModulesModule
          v-if="activeModes.includes('modules')"
          key="modules"
          :style="panelFlexStyle"
          :closePanel="() => closePanel('modules')"
        />
        <RecorderModule
          v-if="activeModes.includes('recorder')"
          key="recorder"
          :style="panelFlexStyle"
          :closePanel="() => closePanel('recorder')"
        />
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import ConfigModule from './LeftConfigPanel.vue'
import CommandModule from './LeftCommandPanel.vue'
import MissionModule from './LeftMissionPanel.vue'
import ParamsModule from './LeftParamsPanel.vue'
import ModulesModule from './LeftModulesPanel.vue'

const modes = [
  { id: 'config', icon: '⚙️', label: '配置' },
  { id: 'command', icon: '🚀', label: '飞控指令' },
  { id: 'mission', icon: '📍', label: '任务' },
  { id: 'params', icon: '🔧', label: '参数配置' },
  { id: 'modules', icon: '📦', label: '模块' }
]

// 改为数组以支持多个面板同时打开，最多3个
const activeModes = ref([])

// 计算各个面板的flex值，实现动态高度分配
const panelFlexStyle = computed(() => {
  const count = activeModes.value.length
  if (count === 1) {
    return { flex: '1' }
  } else if (count === 2) {
    return { flex: '1' }
  } else {
    // 3个面板时，每个占1份，平均分配高度
    return { flex: '1' }
  }
})

function toggleMode(mode) {
  const index = activeModes.value.indexOf(mode)
  const count = activeModes.value.length
  
  if (index > -1) {
    // 如果已打开，则关闭
    activeModes.value.splice(index, 1)
  } else {
    // 未打开，则添加（最多3个面板）
    if (count < 3) {
      activeModes.value.push(mode)
    } else {
      alert('最多只能同时显示3个面板')
    }
  }
}

function closePanel(mode) {
  const index = activeModes.value.indexOf(mode)
  if (index > -1) {
    activeModes.value.splice(index, 1)
  }
}

// 导出关闭方法供子组件调用
defineExpose({
  closePanel
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
  background: rgba(20, 20, 20, 0.95);
  border: 1px solid #333333;
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
  background: rgba(50, 136, 250, 0.2);
}

.icon-btn.active {
  background: rgba(50, 136, 250, 0.3);
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
  background: #3288fa;
  border-radius: 0 2px 2px 0;
}

/* ==================== 内容抽屉 ==================== */
.drawer-content {
  /* 宽度自适应，根据容器最小宽度和最大宽度 */
  min-width: 280px;
  max-width: 360px;
  /* 高度100%，继承父容器的高度 */
  height: 100%;
  /* 使用flex布局来管理多个面板 */
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: rgba(25, 25, 25, 0.95);
  border: 1px solid #333333;
  border-left: none;
  border-radius: 8px;
  overflow: hidden;  /* 抽屉容器不滚动，由子面板内部滚动 */
  backdrop-filter: blur(10px);
  box-shadow: 4px 0 12px rgba(0, 0, 0, 0.3);
}

/* ==================== 滚动条样式 ==================== */
.drawer-content::-webkit-scrollbar {
  width: 6px;
}

.drawer-content::-webkit-scrollbar-track {
  background: rgba(30, 30, 30, 0.5);
}

.drawer-content::-webkit-scrollbar-thumb {
  background: #3288fa;
  border-radius: 3px;
}

.drawer-content::-webkit-scrollbar-thumb:hover {
  background: #2676ea;
}

/* ==================== 动态加载的面板样式 ==================== */
.drawer-content > * {
  /* 动态加载的面板都需要这些基础样式 */
  min-height: 0;
  overflow: hidden;
  height: 100%;  /* 确保面板占满可用高度 */
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