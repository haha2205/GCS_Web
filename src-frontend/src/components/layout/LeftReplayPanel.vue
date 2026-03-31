<template>
  <div class="replay-panel">
    <div class="panel-header">
      <h3 class="panel-title">历史数据回放</h3>
      <button
        v-if="fileLoaded"
        @click="showFileManager = true"
        class="back-btn"
      >
        ← 文件管理
      </button>
    </div>
    
    <div class="content-scroll">
      <div class="replay-content">
        <!-- 文件选择区域 -->
        <div class="file-selector-section">
          <div class="selector-title">选择回放文件</div>
          <div class="file-input-group">
            <input
              ref="fileInput"
              type="file"
              accept=".csv"
              @change="handleFileSelected"
              style="display: none"
            />
            <button class="select-file-btn" @click="triggerFileSelect">
              <span class="btn-icon">📄</span>
              <span class="btn-text">选择 CSV 文件</span>
            </button>
            <div class="selected-file-info" v-if="selectedFile">
              <span class="file-name">{{ selectedFile.name }}</span>
              <span class="file-size">({{ formatFileSize(selectedFile.size) }})</span>
            </div>
          </div>
          <div class="separator">
            <span class="separator-text">或</span>
          </div>
        </div>

        <!-- 项目文件列表标题 -->
        <div class="list-title" v-if="!showCustomOnly">
          项目日志文件（Log/ 文件夹）
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-section">
          <div class="loading-spinner"></div>
          <div class="loading-text">加载中...</div>
        </div>
        
        <!-- 空状态 -->
        <div v-else-if="files.length === 0 && !selectedFile" class="empty-section">
          <div class="empty-icon">📂</div>
          <div class="empty-text">暂无回放文件</div>
          <div class="empty-hint">
            提示：点击"选择 CSV 文件"按钮加载本地文件，或在"配置"中启用"自动记录"
          </div>
        </div>
        
        <!-- 文件列表 -->
        <div v-else class="file-list">
          <div 
            v-for="file in files" 
            :key="file.name" 
            class="file-item"
            @click="loadLog(file)"
          >
            <div class="file-icon">📄</div>
            <div class="file-info">
              <div class="file-name">{{ file.name }}</div>
              <div class="file-meta">
                <span class="file-date">{{ file.date }}</span>
                <span class="file-size">{{ formatFileSize(file.size) }}</span>
              </div>
            </div>
            <button class="play-btn" @click.stop="loadLog(file)">
              <span v-if="loadingFile === file.name" class="loading-icon">⏳</span>
              <span v-else>▶</span>
            </button>
          </div>
        </div>
      </div>
      
      <!-- 自定义文件播放按钮 -->
      <div v-if="selectedFile && !showFileManager" class="play-custom-section">
        <button
          class="play-custom-btn"
          @click="playCustomFile"
          :disabled="loading"
        >
          <span class="btn-icon">▶</span>
          <span v-if="!loading">播放选中的文件</span>
          <span v-else>准备中...</span>
        </button>
        <button
          class="cancel-btn"
          @click="clearSelectedFile"
          :disabled="loading"
        >
          取消
        </button>
      </div>

      <!-- 刷新按钮 -->
      <div class="refresh-section" v-if="!selectedFile && !showFileManager && !fileLoaded">
        <button
          class="refresh-btn"
          @click="loadFileList"
          :disabled="loading"
        >
          <span v-if="!loading">🔄 刷新列表</span>
          <span v-else>刷新中...</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useDroneStore } from '@/store/drone'
 
const droneStore = useDroneStore()
 
const fileLoaded = ref(false)
const showFileManager = ref(false)
const loading = ref(false)
const loadingFile = ref(null)
const files = ref([])
const selectedFile = ref(null)
const fileInput = ref(null)
const showCustomOnly = ref(false)
 
// 加载文件列表
onMounted(async () => {
  await loadFileList()
})

async function loadFileList() {
  try {
    loading.value = true
    const response = await fetch('http://localhost:8000/api/replay/files')
    const data = await response.json()
    
    if (data.type === 'replay_files') {
      files.value = data.files
      console.log('回放文件列表:', files.value)
    }
  } catch (error) {
    console.error('加载回放文件列表失败:', error)
    droneStore.addLog('加载回放文件列表失败: ' + error.message, 'error')
  } finally {
    loading.value = false
  }
}

// 触发文件选择对话框
function triggerFileSelect() {
  if (fileInput.value) {
    fileInput.value.click()
  }
}

// 处理文件选择
function handleFileSelected(event) {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    droneStore.addLog(`已选择文件: ${file.name}`, 'info')
  }
}

// 清除选中的文件
function clearSelectedFile() {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  droneStore.addLog('已取消文件选择', 'info')
}

// 播放自定义文件
async function playCustomFile() {
  if (!selectedFile.value) {
    droneStore.addLog('请先选择文件', 'warning')
    return
  }

  try {
    loading.value = true
    
    // 将文件内容读取并上传到后端
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    // 上传文件
    const uploadResponse = await fetch('http://localhost:8000/api/replay/upload', {
      method: 'POST',
      body: formData
    })
    
    const uploadResult = await uploadResponse.json()
    
    if (uploadResult.status === 'success') {
      const filePath = uploadResult.file_path
      
      // 加载文件
      const response = await fetch('http://localhost:8000/api/replay/control', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          action: 'load',
          file_path: filePath
        })
      })
      
      const result = await response.json()
      
      if (result.status === 'success') {
        console.log('回放文件已加载:', selectedFile.value.name)
        droneStore.addLog(`回放文件已加载: ${selectedFile.value.name}`, 'success')
        
        // 标记文件已加载
        fileLoaded.value = true
        showFileManager.value = false
        
        // 开始播放
        await startPlayback()
      } else {
        console.error('加载回放文件失败:', result.message)
        droneStore.addLog(`加载回放文件失败: ${result.message}`, 'error')
      }
    } else {
      console.error('上传文件失败:', uploadResult.message)
      droneStore.addLog(`上传文件失败: ${uploadResult.message}`, 'error')
    }
    
  } catch (error) {
    console.error('播放自定义文件失败:', error)
    droneStore.addLog(`播放文件失败: ${error.message}`, 'error')
  } finally {
    loading.value = false
  }
}

// 加载并播放日志（项目文件）
async function loadLog(file) {
  try {
    loadingFile.value = file.name
    
    // 通知后端加载文件
    const response = await fetch('http://localhost:8000/api/replay/control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        action: 'load',
        file_path: file.path
      })
    })
    
    const result = await response.json()
    
    if (result.status === 'success') {
      console.log('回放文件已加载:', file.name)
      droneStore.addLog(`回放文件已加载: ${file.name}`, 'success')
      
      // 标记文件已加载
      fileLoaded.value = true
      showFileManager.value = false
      
      // 开始播放
      await startPlayback()
    } else {
      console.error('加载回放文件失败:', result.message)
      droneStore.addLog(`加载回放文件失败: ${result.message}`, 'error')
    }
    
  } catch (error) {
    console.error('加载回放文件失败:', error)
    droneStore.addLog(`加载回放文件失败: ${error.message}`, 'error')
  } finally {
    loadingFile.value = null
  }
}

async function startPlayback() {
  try {
    const response = await fetch('http://localhost:8000/api/replay/control', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        action: 'play'
      })
    })
    
    const result = await response.json()
    console.log('回放已开始:', result)
  } catch (error) {
    console.error('开始回放失败:', error)
    droneStore.addLog(`开始回放失败: ${error.message}`, 'error')
  }
}

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 暴露关闭方法供父组件调用
defineExpose({
  loadFileList
})
</script>

<style scoped>
.replay-panel {
  padding: 15px;
  height: 100vh;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 8px;
}

/* 自定义滚动条样式 */
.content-scroll::-webkit-scrollbar {
  width: 6px;
}

.content-scroll::-webkit-scrollbar-track {
  background: rgba(50, 51, 61, 0.5);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb {
  background: rgba(50, 136, 250, 0.5);
  border-radius: 3px;
}

.content-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(50, 136, 250, 0.8);
}

.replay-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 2px solid #3288fa;
  margin-bottom: 15px;
}

.panel-title {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.back-btn {
  padding: 6px 12px;
  background: rgba(50, 136, 250, 0.1);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 4px;
  color: #9ca3af;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: rgba(50, 136, 250, 0.2);
  border-color: rgba(50, 136, 250, 0.5);
  color: #3288fa;
}

.loading-section,
.empty-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #6b7280;
  flex: 1;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(50, 136, 250, 0.2);
  border-top-color: #3288fa;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 14px;
  color: #9ca3af;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
  max-width: 280px;
  line-height: 1.5;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.file-item {
  display: flex;
  align-items: center;
  padding: 12px;
  background: rgba(50, 51, 61, 0.5);
  border: 1px solid rgba(50, 136, 250, 0.2);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.file-item:hover {
  background: rgba(50, 136, 250, 0.1);
  border-color: rgba(50, 136, 250, 0.4);
  transform: translateX(2px);
}

.file-item:active {
  transform: translateX(1px);
}

.file-icon {
  font-size: 24px;
  margin-right: 12px;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: #e6edf3;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #6b7280;
}

.file-date,
.file-size {
  display: flex;
  align-items: center;
  gap: 4px;
}

.play-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: linear-gradient(135deg, #3288fa 0%, #2563eb 100%);
  color: white;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-left: 8px;
}

.play-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(50, 136, 250, 0.4);
}

.play-btn:active {
  transform: scale(0.95);
}

.loading-icon {
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.refresh-section {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid #333;
}

.refresh-btn {
  width: 100%;
  background: rgba(50, 136, 250, 0.1);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 6px;
  color: #9ca3af;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(50, 136, 250, 0.2);
  border-color: rgba(50, 136, 250, 0.5);
  color: #3288fa;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 文件选择区域样式 */
.file-selector-section {
  background: rgba(50, 51, 61, 0.3);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}

.selector-title {
  font-size: 12px;
  font-weight: 600;
  color: #3288fa;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.file-input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.select-file-btn {
  width: 100%;
  background: linear-gradient(135deg, #3288fa 0%, #2563eb 100%);
  border: none;
  border-radius: 6px;
  color: white;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.select-file-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(50, 136, 250, 0.4);
}

.select-file-btn:active {
  transform: translateY(0);
}

.select-file-btn .btn-icon {
  font-size: 18px;
}

.select-file-btn .btn-text {
  font-size: 13px;
}

.selected-file-info {
  background: rgba(50, 136, 250, 0.1);
  border: 1px solid rgba(50, 136, 250, 0.3);
  border-radius: 4px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.selected-file-info .file-name {
  color: #e6edf3;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selected-file-info .file-size {
  color: #9ca3af;
  font-size: 11px;
}

.separator {
  display: flex;
  align-items: center;
  margin: 12px 0;
  position: relative;
}

.separator::before {
  content: '';
  flex: 1;
  height: 1px;
  background: #333;
}

.separator-text {
  color: #6b7280;
  font-size: 11px;
  padding: 0 12px;
  background: inherit;
  position: relative;
  z-index: 1;
}

.list-title {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  margin-bottom: 8px;
  padding-left: 4px;
  border-left: 2px solid #3288fa;
}

.play-custom-section {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid #333;
  display: flex;
  gap: 8px;
}

.play-custom-btn {
  flex: 1;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  border: none;
  border-radius: 6px;
  color: white;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.play-custom-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.4);
}

.play-custom-btn:active:not(:disabled) {
  transform: translateY(0);
}

.play-custom-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.play-custom-btn .btn-icon {
  font-size: 16px;
}

.cancel-btn {
  width: 80px;
  background: rgba(107, 114, 128, 0.2);
  border: 1px solid rgba(107, 114, 128, 0.4);
  border-radius: 6px;
  color: #9ca3af;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.cancel-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.4);
  color: #ef4444;
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>