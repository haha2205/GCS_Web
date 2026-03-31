<template>
  <div class="left-sidebar">
    <div class="sidebar-icons">
      <div
        v-for="mode in modes"
        :key="mode.id"
        class="icon-btn"
        :class="{ active: activeMode === mode.id }"
        @click="toggleMode(mode.id)"
        :title="mode.label"
      >
        <span class="icon">{{ mode.icon }}</span>
        <span v-if="activeMode === mode.id" class="active-indicator"></span>
      </div>
    </div>

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
import { ref } from 'vue'
import ConfigModule from './LeftConfigPanel.vue'
import CommandModule from './LeftCommandPanel.vue'
import ParamsModule from './LeftParamsPanel.vue'

const modes = [
  { id: 'config', icon: '⚙️', label: '配置' },
  { id: 'command', icon: '🚀', label: '飞控指令' },
  { id: 'params', icon: '🔧', label: '参数配置' }
]

const activeMode = ref('command')

function toggleMode(mode) {
  activeMode.value = activeMode.value === mode ? null : mode
}

function closePanel(mode) {
  if (activeMode.value === mode) {
    activeMode.value = null
  }
}

defineExpose({ closePanel })
</script>

<style scoped>
.left-sidebar {
  display: flex;
  align-items: flex-start;
  flex-shrink: 0;
  height: 100%;
}

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
  height: 100%;
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
</style>