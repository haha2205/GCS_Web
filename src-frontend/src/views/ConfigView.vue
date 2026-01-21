<template>
  <div class="config-view">
    <div class="config-container">
      <h2>配置中心</h2>
      <p>系统配置界面</p>
      <div class="config-section">
        <h3>网络配置</h3>
        <div class="config-item">
          <label>服务器地址:</label>
          <input type="text" v-model="config.serverAddress" placeholder="192.168.1.1" />
        </div>
        <div class="config-item">
          <label>UDP 端口:</label>
          <input type="number" v-model="config.udpPort" placeholder="18506" />
        </div>
      </div>
      <button class="save-btn" @click="saveConfig">保存配置</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const config = ref({
  serverAddress: '192.168.1.1',
  udpPort: 18506
})

const saveConfig = () => {
  console.log('保存配置:', config.value)
  alert('配置已保存!')
}
</script>

<style scoped>
.config-view {
  padding: 20px;
  color: #ffffff;
}

.config-container {
  max-width: 800px;
  margin: 0 auto;
}

.config-container h2 {
  color: #00BCD4;
  margin-bottom: 10px;
}

.config-section {
  background: rgba(31, 31, 31, 0.8);
  border-radius: 8px;
  padding: 20px;
  margin-top: 20px;
}

.config-section h3 {
  color: #2196F3;
  margin-bottom: 15px;
}

.config-item {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
}

.config-item label {
  width: 120px;
  color: #B0BEC5;
}

.config-item input {
  flex: 1;
  padding: 8px 12px;
  background: rgba(13, 13, 13, 0.8);
  border: 1px solid #424242;
  border-radius: 4px;
  color: #ffffff;
  font-size: 14px;
}

.config-item input:focus {
  outline: none;
  border-color: #00BCD4;
}

.save-btn {
  margin-top: 20px;
  padding: 10px 30px;
  background: #00BCD4;
  border: none;
  border-radius: 4px;
  color: #ffffff;
  cursor: pointer;
  font-size: 14px;
}

.save-btn:hover {
  background: #00ACC1;
}
</style>