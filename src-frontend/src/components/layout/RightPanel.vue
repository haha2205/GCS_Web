<template>
  <div class="right-sidebar-content">
    <div class="panel-content">
      <RightMonitorTabsPanel />
    </div>
  </div>
</template>

<script setup>
import RightMonitorTabsPanel from './RightMonitorTabsPanel.vue'

// 接收props而不是内部管理状态
const props = defineProps({
  isMaximized: {
    type: Boolean,
    default: false
  }
})

// 定义emits
const emit = defineEmits(['toggle-maximize', 'toggle-hide'])

const splitPanel = () => {
  // 拆分面板的功能可以在这里实现
  console.log('Split panel clicked')
}
</script>

<style scoped>
/* ==================== 右侧栏容器 ==================== */
.right-sidebar-content {
  width: 100%;
  height: 100%;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
}

.maximized .right-sidebar-content {
  max-width: 800px !important;
  margin: 0 auto !important;
}

.hidden .right-sidebar-content {
  width: 0 !important;
  overflow: hidden !important;
}

/* ==================== 面板内容区域 ==================== */
.panel-content {
  flex: 1 !important;
  overflow: hidden !important;
  display: flex !important;
  flex-direction: column !important;
  min-height: 0 !important;
}
</style>