<template>
  <div class="map-placeholder">
    <div class="grid-text">Map Placeholder</div>
    <p class="hint">地图功能待集成（Mapbox / Leaflet）</p>
  </div>
</template>

<script setup>
// 地图占位组件
// 后续可以集成 Mapbox、Leaflet 等地图库
</script>

<style scoped>
.map-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #ffffff;
}

.grid-text {
  font-size: 32px;
  font-weight: bold;
  color: #3288fa;
  margin-bottom: 20px;
}

.hint {
  font-size: 14px;
  color: #999999;
}
</style>