<template>
  <div
    class="layout-splitter"
    :class="{ 'dragging': isDragging }"
    @dblclick="resetPositions"
  >
    <div class="splitter-handle" @mousedown="startDrag">
      <div class="handle-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'

const props = defineProps({
  position: {
    type: String,
    default: 'right', // 'left' or 'right'
  },
  direction: {
    type: String,
    default: 'vertical'
  }
})

const emit = defineEmits(['resize'])

const isDragging = ref(false)
const startX = ref(0)
const startWidth = ref(0)

const getTargetPanel = () => document.querySelector('.monitor-panel')

const startDrag = (mouseEvent) => {
  isDragging.value = true
  startX.value = mouseEvent.clientX

  const panel = getTargetPanel()
  startWidth.value = panel ? panel.offsetWidth : 400
  
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  
  // 阻止默认选择行为
  mouseEvent.preventDefault()
}

const onDrag = (mouseEvent) => {
  if (!isDragging.value) return
  
  const deltaX = props.position === 'left'
    ? mouseEvent.clientX - startX.value
    : startX.value - mouseEvent.clientX
  
  const maxWidth = Math.min(900, Math.round(window.innerWidth * 0.72))
  const newWidth = Math.max(250, Math.min(maxWidth, startWidth.value + deltaX))
  emit('resize', newWidth)
}

const stopDrag = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

const resetPositions = () => {
  const defaultWidth = props.position === 'left' ? 380 : 400
  emit('resize', defaultWidth)
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
})
</script>

<style scoped>
.layout-splitter {
  width: 6px;
  height: 100%;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 100;
  background: transparent;
  transition: background 0.2s;
  user-select: none;
}

.layout-splitter:hover {
  background: rgba(50, 136, 250, 0.15);
}

.layout-splitter.dragging {
  background: rgba(50, 136, 250, 0.3);
}

.splitter-handle {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.handle-dots {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
}

.handle-dots span {
  width: 4px;
  height: 4px;
  background: #555;
  border-radius: 50%;
  transition: all 0.2s;
}

.layout-splitter:hover .handle-dots span {
  background: #3288fa;
  transform: scale(1.2);
}

.layout-splitter.dragging .handle-dots span {
  background: #3288fa;
  box-shadow: 0 0 4px rgba(50, 136, 250, 0.5);
}
</style>