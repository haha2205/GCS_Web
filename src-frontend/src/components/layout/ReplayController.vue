<template>
  <div class="replay-controller">
    <!-- 播放/暂停按钮 -->
    <button class="ctrl-btn play-pause-btn" @click="togglePlay">
      <span v-if="isPlaying" class="icon">⏸</span>
      <span v-else class="icon">▶</span>
    </button>

    <!-- 停止按钮 -->
    <button class="ctrl-btn stop-btn" @click="stopReplay">
      <span class="icon">⏹</span>
    </button>

    <!-- 进度条 -->
    <div class="timeline-slider">
      <span class="time-label current-time">{{ formatTime(replayCurrentTime) }}</span>
      <div class="slider-container">
        <input
          ref="slider"
          type="range"
          class="progress-slider"
          min="0"
          max="100"
          step="0.1"
          :value="progress"
          @input="onSeekInput"
          @change="onSeekChange"
        />
        <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
      </div>
      <span class="time-label total-time">{{ formatTime(totalTime) }}</span>
    </div>

    <!-- 倍速选择器 -->
    <div class="speed-selector">
      <select 
        v-model="playbackSpeed" 
        @change="changeSpeed"
        class="speed-select"
      >
        <option value="0.25">0.25×</option>
        <option value="0.5">0.5×</option>
        <option value="1.0">1.0×</option>
        <option value="2.0">2.0×</option>
        <option value="5.0">5.0×</option>
      </select>
    </div>

    <!-- 状态指示 -->
    <div class="status-indicator">
      <span class="status-dot" :class="{ active: replayActive }"></span>
      <span class="status-text">回放</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import { storeToRefs } from 'pinia'

const droneStore = useDroneStore()
const { replayStatus } = storeToRefs(droneStore)

const slider = ref(null)

// 播放状态
const isPlaying = ref(false)
const replayActive = ref(false)
const playbackSpeed = ref(1.0)

// 回放进度数据计算属性
const replayCurrentTime = computed(() => replayStatus.value.current_time)
const totalTime = computed(() => replayStatus.value.total_time)
const progress = computed(() => replayStatus.value.progress)

// 监听回放状态更新
  watch(() => replayStatus.value, (newStatus) => {
    if (newStatus) {
      replayActive.value = newStatus.replay_active || newStatus.is_loaded
      isPlaying.value = newStatus.is_playing
      playbackSpeed.value = newStatus.speed || 1.0
    }
  }, { deep: true })

// 切换播放/暂停
function togglePlay() {
  const action = isPlaying.value ? 'pause' : 'play'
  sendReplayCommand(action)
  isPlaying.value = !isPlaying.value
}

// 停止回放
function stopReplay() {
  sendReplayCommand('stop')
  isPlaying.value = false
  replayActive.value = false
}

// 拖拽进度条（直接修改，不触发 change）

// 确认跳转
function onSeekChange(event) {
  sendReplayCommand('seek', { progress_percent: parseFloat(event.target.value) })
}

// 改变播放速度
function changeSpeed(event) {
  const speed = parseFloat(event.target.value)
  sendReplayCommand('set_speed', { speed })
}

// 发送回放控制命令
function sendReplayCommand(action, params = {}) {
  droneStore.sendWebSocketMessage({
    type: 'replay',
    action: action,
    params: params
  })
}

// 格式化时间（秒 -> MM:SS）
function formatTime(seconds) {
  if (!seconds || seconds < 0) return '00:00'
  
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// 组件挂载时初始化
onMounted(async () => {
  // 获取初始回放状态
  try {
    const response = await fetch('http://localhost:8000/api/replay/status')
    const data = await response.json()
    
    if (data.type === 'replay_status' && data.status) {
      replayActive.value = data.status.replay_active
      isPlaying.value = data.status.is_playing
      // 这些值会通过 ReplayStore 自动同步
      playbackSpeed.value = data.status.speed || 1.0
    }
  } catch (error) {
    console.error('获取回放状态失败:', error)
  }
})
</script>

<style scoped>
.replay-controller {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 100%;
  padding: 0 20px;
  background: #141414;
  border-top: 2px solid #3274F6;
  user-select: none;
}

.ctrl-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: linear-gradient(135deg, #3274F6 0%, #2563eb 100%);
  color: white;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.ctrl-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(50, 116, 246, 0.4);
}

.ctrl-btn:active {
  transform: scale(0.95);
}

.ctrl-btn .icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

.stop-btn:hover {
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
}

.timeline-slider {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 200px;
}

.slider-container {
  flex: 1;
  position: relative;
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.progress-slider {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  z-index: 2;
}

.progress-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #3274F6 0%, #60a5fa 100%);
  border-radius: 4px;
  transition: width 0.1s ease;
  pointer-events: none;
}

.time-label {
  font-size: 13px;
  font-weight: 600;
  color: #e6edf3;
  font-family: 'Courier New', monospace;
  min-width: 50px;
  text-align: center;
}

.speed-selector {
  flex-shrink: 0;
}

.speed-select {
  appearance: none;
  background: rgba(50, 116, 246, 0.1);
  border: 1px solid rgba(50, 116, 246, 0.3);
  color: #e6edf3;
  padding: 8px 32px 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%233274F6' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
  min-width: 80px;
}

.speed-select:hover {
  background-color: rgba(50, 116, 246, 0.2);
  border-color: rgba(50, 116, 246, 0.5);
}

.speed-select:focus {
  outline: none;
  border-color: #3274F6;
  box-shadow: 0 0 0 3px rgba(50, 116, 246, 0.2);
}

.speed-select option {
  background: #1e1e1e;
  color: #e6edf3;
  padding: 8px 12px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  flex-shrink: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6b7280;
  transition: all 0.3s ease;
}

.status-dot.active {
  background: #22c55e;
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 12px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>