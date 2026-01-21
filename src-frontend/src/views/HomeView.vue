<template>
  <div class="home-view">
    <ThreeDroneView
      :pitch="droneStore.fcsStates?.pitch ?? 0"
      :roll="droneStore.fcsStates?.roll ?? 0"
      :yaw="droneStore.fcsStates?.yaw ?? 0"
    />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import ThreeDroneView from '@/components/ThreeDroneView.vue'

const droneStore = useDroneStore()

// 初始化时自动连接 WebSocket
onMounted(() => {
  if (!droneStore.isConnected) {
    droneStore.connect()
  }
})
</script>

<style scoped>
.home-view {
  width: 100%;
  height: 100%;
  background: #0a0a0a;
}
</style>