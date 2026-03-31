<template>
  <div class="dsm-export-panel">
    <div class="panel-header">DSM数据导出</div>
    
    <div class="panel-content">
      <!-- 步骤指示器 -->
      <div class="steps-indicator">
        <div class="step" :class="{ active: currentStep >= 1, completed: currentStep > 1 }">
          <div class="step-number">1</div>
          <div class="step-label">选择会话</div>
        </div>
        <div class="step-line"></div>
        <div class="step" :class="{ active: currentStep >= 2, completed: currentStep > 2 }">
          <div class="step-number">2</div>
          <div class="step-label">配置参数</div>
        </div>
        <div class="step-line"></div>
        <div class="step" :class="{ active: currentStep >= 3 }">
          <div class="step-number">3</div>
          <div class="step-label">生成报告</div>
        </div>
      </div>

      <!-- 步骤1: 选择会话 -->
      <div v-if="currentStep === 1" class="step-content">
        <div class="section-title">历史录制会话</div>
        
        <div class="sessions-list">
          <div 
            v-for="session in sessions" 
            :key="session.session_id"
            class="session-item"
            :class="{ selected: selectedSessionId === session.session_id }"
            @click="selectSession(session.session_id)"
          >
            <div class="session-header">
              <div class="session-name">{{ session.session_id }}</div>
              <div class="session-date">{{ formatDate(session.start_time) }}</div>
            </div>
            <div class="session-details">
              <div class="detail-item">
                <span class="detail-label">时长:</span>
                <span class="detail-value">{{ formatDuration(session.duration) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">数据包:</span>
                <span class="detail-value">{{ session.packet_count }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">状态:</span>
                <span class="detail-value status-ok">已完成</span>
              </div>
            </div>
          </div>
          
          <div v-if="sessions.length === 0" class="no-sessions">
            暂无录制会话
          </div>
        </div>

        <div class="step-actions">
          <button 
            class="action-btn secondary-btn" 
            @click="refreshSessions"
          >
            <span class="btn-icon">🔄</span>
            刷新列表
          </button>
          <button 
            class="action-btn primary-btn" 
            @click="nextStep"
            :disabled="!selectedSessionId"
          >
            <span class="btn-icon">→</span>
            下一步
          </button>
        </div>
      </div>

      <!-- 步骤2: 配置参数 -->
      <div v-if="currentStep === 2" class="step-content">
        <div class="section-title">DSM生成配置</div>
        
        <div class="config-form">
          <div class="form-group">
            <div class="form-label">会话</div>
            <div class="form-value">{{ selectedSessionId }}</div>
          </div>

          <div class="form-group">
            <div class="form-label">时间范围</div>
            <div class="form-control">
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="full" 
                  v-model="timeRange"
                  @change="updateTimeRange"
                />
                <span>全时段</span>
              </label>
              <label class="radio-label">
                <input 
                  type="radio" 
                  value="range" 
                  v-model="timeRange"
                  @change="updateTimeRange"
                />
                <span>自定义范围</span>
              </label>
            </div>
          </div>

          <div v-if="timeRange === 'range'" class="form-group">
            <div class="form-label">开始时间</div>
            <input 
              type="datetime-local" 
              v-model="customStartTime"
              class="datetime-input"
            />
          </div>

          <div v-if="timeRange === 'range'" class="form-group">
            <div class="form-label">结束时间</div>
            <input 
              type="datetime-local" 
              v-model="customEndTime"
              class="datetime-input"
            />
          </div>

          <div class="form-group">
            <div class="form-label">映射配置</div>
            <select v-model="selectedMappingConfig" class="select-input">
              <option value="default">默认配置</option>
              <option value="custom">自定义配置</option>
            </select>
          </div>

          <div class="form-group">
            <div class="form-label">输出格式</div>
            <div class="checkbox-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="exportFormats.json" />
                <span>JSON</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="exportFormats.csv" />
                <span>CSV矩阵</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="exportFormats.report" />
                <span>分析报告</span>
              </label>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <button class="action-btn secondary-btn" @click="prevStep">
            <span class="btn-icon">←</span>
            上一步
          </button>
          <button 
            class="action-btn primary-btn" 
            @click="generateReport"
            :disabled="isGenerating"
          >
            <span v-if="!isGenerating">
              <span class="btn-icon">📊</span>
              生成DSM报告
            </span>
            <span v-else>
              <span class="btn-icon spinning">⏳</span>
              生成中...
            </span>
          </button>
        </div>
      </div>

      <!-- 步骤3: 生成结果 -->
      <div v-if="currentStep === 3" class="step-content">
        <div v-if="!reportResult" class="loading-spinner">
          <div class="spinner"></div>
          <div class="loading-text">正在生成DSM报告...</div>
        </div>

        <div v-else class="report-result">
          <div class="section-title">生成成功</div>
          
          <div class="result-summary">
            <div class="summary-item">
              <div class="summary-label">节点数量</div>
              <div class="summary-value">{{ reportResult.nodeCount }}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">交互数量</div>
              <div class="summary-value">{{ reportResult.edgeCount }}</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">分析时长</div>
              <div class="summary-value">{{ reportResult.analysisDuration }}</div>
            </div>
          </div>

          <div class="download-section">
            <div class="section-title">下载文件</div>
            <div class="download-list">
              <button 
                v-if="exportFormats.json"
                class="download-btn"
                @click="downloadFile('json')"
              >
                <span class="btn-icon">📄</span>
                DSM数据结构.json
              </button>
              <button 
                v-if="exportFormats.csv"
                class="download-btn"
                @click="downloadFile('csv')"
              >
                <span class="btn-icon">📊</span>
                DSM矩阵.csv
              </button>
              <button 
                v-if="exportFormats.report"
                class="download-btn"
                @click="downloadFile('report')"
              >
                <span class="btn-icon">📋</span>
                分析报告.pdf
              </button>
            </div>
          </div>

          <div class="step-actions">
            <button class="action-btn secondary-btn" @click="exportAnother">
              <span class="btn-icon">🔄</span>
              导出其他
            </button>
            <button class="action-btn primary-btn" @click="closePanel">
              <span class="btn-icon">✓</span>
              完成
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiGenerateDSMReport, apiGetRecordingSessions } from '@/api/backend'

const emit = defineEmits(['close'])

const currentStep = ref(1)
const sessions = ref([])
const selectedSessionId = ref('')
const timeRange = ref('full')
const customStartTime = ref('')
const customEndTime = ref('')
const selectedMappingConfig = ref('default')
const exportFormats = ref({
  json: true,
  csv: true,
  report: false
})
const isGenerating = ref(false)
const reportResult = ref(null)

// 加载会话列表
const loadSessions = async () => {
  try {
    const response = await apiGetRecordingSessions()
    if (response.success && response.data) {
      sessions.value = response.data.sessions || []
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
  }
}

// 刷新会话列表
const refreshSessions = () => {
  loadSessions()
}

// 选择会话
const selectSession = (sessionId) => {
  selectedSessionId.value = sessionId
}

// 步骤导航
const nextStep = () => {
  if (currentStep.value < 3) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

// 更新时间范围
const updateTimeRange = () => {
  if (timeRange.value === 'full' && selectedSessionId.value) {
    const session = sessions.value.find(s => s.session_id === selectedSessionId.value)
    if (session) {
      customStartTime.value = session.start_time
      customEndTime.value = session.end_time
    }
  }
}

// 生成报告
const generateReport = async () => {
  isGenerating.value = true
  currentStep.value = 3
  
  try {
    const config = {
      session_id: selectedSessionId.value,
      time_range: timeRange.value,
      start_time: timeRange.value === 'range' ? customStartTime.value : undefined,
      end_time: timeRange.value === 'range' ? customEndTime.value : undefined,
      mapping_config: selectedMappingConfig.value,
      export_formats: exportFormats.value
    }
    
    const response = await apiGenerateDSMReport(config)
    if (response.success && response.data) {
      reportResult.value = response.data
    } else {
      alert('生成失败: ' + response.message)
      currentStep.value = 2
    }
  } catch (error) {
    console.error('生成报告失败:', error)
    alert('生成失败: ' + error.message)
    currentStep.value = 2
  } finally {
    isGenerating.value = false
  }
}

// 下载文件
const downloadFile = (format) => {
  // 实现文件下载逻辑
  console.log('下载文件:', format)
  alert(`下载${format}格式的功能待实现`)
}

// 导出其他
const exportAnother = () => {
  currentStep.value = 1
  selectedSessionId.value = ''
  reportResult.value = null
}

// 关闭面板
const closePanel = () => {
  emit('close')
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

// 格式化时长
const formatDuration = (seconds) => {
  if (!seconds) return '0s'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.dsm-export-panel {
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #0f0f0f 0%, #1a1a1a 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid #333;
  font-size: 14px;
  font-weight: bold;
  color: #00bcd4;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.steps-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  padding: 16px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #333;
  color: #666;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  transition: all 0.3s ease;
}

.step.active .step-number {
  background: #00bcd4;
  color: #ffffff;
}

.step.completed .step-number {
  background: #2ed573;
  color: #ffffff;
}

.step-label {
  font-size: 11px;
  color: #666;
  transition: all 0.3s ease;
}

.step.active .step-label,
.step.completed .step-label {
  color: #00bcd4;
}

.step.completed .step-label {
  color: #2ed573;
}

.step-line {
  flex: 1;
  height: 2px;
  background: #333;
  margin: 0 16px;
  margin-bottom: 24px;
}

.step-content {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 20px;
}

.section-title {
  font-size: 13px;
  color: #00bcd4;
  font-weight: 600;
  margin-bottom: 16px;
  text-transform: uppercase;
}

.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

.session-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid #333;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: #00bcd4;
}

.session-item.selected {
  background: rgba(0, 188, 212, 0.1);
  border-color: #00bcd4;
}

.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.session-name {
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
}

.session-date {
  font-size: 11px;
  color: #888;
}

.session-details {
  display: flex;
  gap: 16px;
}

.detail-item {
  display: flex;
  gap: 4px;
}

.detail-label {
  font-size: 11px;
  color: #888;
}

.detail-value {
  font-size: 11px;
  color: #ffffff;
  font-family: 'Courier New', monospace;
}

.status-ok {
  color: #2ed573;
}

.no-sessions {
  text-align: center;
  padding: 40px;
  color: #666;
  font-size: 13px;
}

.step-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.primary-btn {
  background: linear-gradient(135deg, #00bcd4, #008ba3);
  color: #ffffff;
}

.primary-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #00acc1, #006064);
  box-shadow: 0 4px 12px rgba(0, 188, 212, 0.4);
}

.secondary-btn {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
  border: 1px solid #333;
}

.secondary-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}

.btn-icon {
  font-size: 14px;
}

.btn-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 12px;
  color: #888;
  font-weight: 500;
}

.form-value {
  font-size: 14px;
  color: #ffffff;
  font-family: 'Courier New', monospace;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
}

.form-control {
  display: flex;
  gap: 20px;
}

.radio-label,
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #ffffff;
  cursor: pointer;
}

.radio-label input,
.checkbox-label input {
  accent-color: #00bcd4;
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.datetime-input,
.select-input {
  width: 100%;
  padding: 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid #333;
  border-radius: 6px;
  color: #ffffff;
  font-size: 13px;
}

.datetime-input:focus,
.select-input:focus {
  outline: none;
  border-color: #00bcd4;
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(0, 188, 212, 0.1);
  border-top-color: #00bcd4;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-text {
  margin-top: 16px;
  font-size: 14px;
  color: #888;
}

.report-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.summary-item {
  background: rgba(255, 255, 255, 0.03);
  padding: 16px;
  border-radius: 8px;
  text-align: center;
}

.summary-label {
  font-size: 11px;
  color: #888;
  margin-bottom: 6px;
  text-transform: uppercase;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
  color: #00bcd4;
}

.download-section {
  padding: 16px;
  background: rgba(0, 188, 212, 0.05);
  border: 1px solid rgba(0, 188, 212, 0.3);
  border-radius: 8px;
}

.download-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.download-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(0, 188, 212, 0.1);
  border: 1px solid rgba(0, 188, 212, 0.3);
  border-radius: 6px;
  color: #00bcd4;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.download-btn:hover {
  background: rgba(0, 188, 212, 0.2);
  transform: translateX(4px);
}
</style>