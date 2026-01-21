<template>
  <div class="apollo-sidebar">
    <div class="sidebar-header">
      <div class="logo">
        <span class="logo-icon">🚁</span>
        <span class="logo-text">Apollo</span>
      </div>
    </div>
    
    <nav class="sidebar-nav">
      <button
        v-for="item in navItems"
        :key="item.key"
        class="nav-item"
        :class="{ 'nav-item-active': activeTab === item.key }"
        @click="handleNavClick(item)"
        title="切换到" + item.label
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>
    
    <div class="sidebar-footer">
      <div class="quick-actions">
        <button class="action-btn" title="连接">
          <span>🔌</span>
        </button>
        <button class="action-btn" title="设置">
          <span>⚙️</span>
        </button>
        <button class="action-btn" title="帮助">
          <span>❓</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('dashboard')

const navItems = ref([
  { key: 'dashboard', label: '仪表盘', icon: '📊' },
  { key: 'map', label: '地图', icon: '🗺️' },
  { key: 'mission', label: '任务', icon: '🎯' },
  { key: 'monitor', label: '监控', icon: '📈' },
  { key: 'config', label: '配置', icon: '⚙️' },
  { key: 'log', label: '日志', icon: '📋' }
])

const handleNavClick = (item) => {
  activeTab.value = item.key
  // TODO: 实现左侧面板内容切换逻辑
  // 可以通过emit事件到父组件，或使用Pinia状态管理
  console.log('切换到:', item.label)
}
</script>

<style scoped>
.apollo-sidebar {
  width: 200px;
  background: linear-gradient(180deg, #0f0f0f 0%, #1a1a1a 100%);
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #333;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 28px;
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
  color: #00bcd4;
  letter-spacing: 1px;
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px 0;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  color: #b0b0b0;
  border: none;
  background: transparent;
  font-size: 14px;
  font-weight: 500;
  text-align: left;
  transition: all 0.2s;
  border-left: 3px solid transparent;
  cursor: pointer;
}

.nav-item:hover {
  background: rgba(0, 188, 212, 0.1);
  color: #00bcd4;
}

.nav-item-active {
  background: rgba(0, 188, 212, 0.15);
  color: #00bcd4;
  border-left-color: #00bcd4;
}

.nav-icon {
  font-size: 20px;
  width: 24px;
  text-align: center;
}

.nav-label {
  font-size: 14px;
  font-weight: 500;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid #333;
}

.quick-actions {
  display: flex;
  justify-content: space-around;
}

.action-btn {
  width: 40px;
  height: 40px;
  border: 1px solid #333;
  background: #1a1a1a;
  border-radius: 8px;
  color: #b0b0b0;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn:hover {
  background: #333;
  color: #00bcd4;
  border-color: #00bcd4;
}
</style>