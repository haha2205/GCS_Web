<template>
  <div class="home-view">
    <ThreeDroneView />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useDroneStore } from '@/store/drone'
import ThreeDroneView from '@/components/ThreeDroneView.vue'

const droneStore = useDroneStore()

onMounted(() => {
  if (!droneStore.isConnected) {
    droneStore.connect()
  }
})
</script>

<style scoped>
.home-view {
  position: relative;
  width: 100%;
  height: 100%;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 28%),
    radial-gradient(circle at 80% 12%, rgba(34, 197, 94, 0.1), transparent 20%),
    linear-gradient(180deg, #06111f 0%, #091827 42%, #0b1220 100%);
}
</style>
