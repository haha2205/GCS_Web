<template>
  <div class="right-sidebar-content">
    <div class="panel-content">
      <RightMonitorTabsPanel
        :show-control-panel="showControlPanel"
        :show-system-panel="showSystemPanel"
        :show-link-health="showLinkHealth"
        :show-online-analysis="showOnlineAnalysis"
        @close-link-health="$emit('close-link-health')"
        @close-online-analysis="$emit('close-online-analysis')"
      />
    </div>
  </div>
</template>

<script setup>
import RightMonitorTabsPanel from './RightMonitorTabsPanel.vue'

defineEmits(['close-link-health', 'close-online-analysis'])

// 接收props而不是内部管理状态
defineProps({
  isMaximized: {
    type: Boolean,
    default: false
  },
  showControlPanel: {
    type: Boolean,
    default: true
  },
  showSystemPanel: {
    type: Boolean,
    default: false
  },
  showLinkHealth: {
    type: Boolean,
    default: false
  },
  showOnlineAnalysis: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
/* ==================== 右侧栏容器 ==================== */
.right-sidebar-content {
  width: 100%;
  height: 100%;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
  background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
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