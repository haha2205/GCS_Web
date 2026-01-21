/**
 * 后端 API 客户端
 * 提供 RESTful API 调用接口
 */

const API_BASE_URL = 'http://localhost:8000'

/**
 * 通用 API 请求封装
 * @param {string} endpoint - API端点
 * @param {object} data - 请求数据
 * @param {string} method - HTTP方法 (GET/POST)
 * @returns {Promise<any>}
 */
async function apiRequest(endpoint, data = null, method = 'GET') {
  const url = `${API_BASE_URL}${endpoint}`
  
  try {
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json'
      }
    }
    
    if (data && method === 'POST') {
      options.body = JSON.stringify(data)
    }
    
    const response = await fetch(url, options)
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`API 请求失败: ${response.status} - ${errorText}`)
    }
    
    return await response.json()
  } catch (error) {
    console.error(`API错误 [${endpoint}]:`, error)
    throw error
  }
}

/**
 * 连接配置 API
 */
export const connectionApi = {
  /**
   * 获取连接配置
   */
  getConfig: async () => {
    return await apiRequest('/api/config/connection')
  },
  
  /**
   * 更新连接配置
   * @param {object} config - 连接配置对象
   */
  updateConfig: async (config) => {
    return await apiRequest('/api/config/connection', config, 'POST')
  }
}

/**
 * 日志配置 API
 */
export const logApi = {
  /**
   * 获取日志配置
   */
  getConfig: async () => {
    return await apiRequest('/api/config/log')
  },
  
  /**
   * 更新日志配置
   * @param {object} config - 日志配置对象
   */
  updateConfig: async (config) => {
    return await apiRequest('/api/config/log', config, 'POST')
  },
  
  /**
   * 保存日志条目
   * @param {object} data - 日志数据
   */
  saveLogEntry: async (data) => {
    return await apiRequest('/api/log/save', data, 'POST')
  }
}

/**
 * DSM录制 API
 */
export const recordingApi = {
  /**
   * 获取录制状态
   */
  getStatus: async () => {
    return await apiRequest('/api/recording/status')
  },
  
  /**
   * 开始录制
   * @param {object} config - 录制配置
   */
  startRecording: async (config) => {
    return await apiRequest('/api/recording/start', config, 'POST')
  },
  
  /**
   * 停止录制
   */
  stopRecording: async () => {
    return await apiRequest('/api/recording/stop', {}, 'POST')
  },
  
  /**
   * 获取录制会话列表
   */
  getSessions: async () => {
    return await apiRequest('/api/recording/sessions')
  }
}

/**
 * DSM报告生成 API
 */
export const dsmApi = {
  /**
   * 生成DSM报告
   * @param {object} config - DSM生成配置
   */
  generateReport: async (config) => {
    return await apiRequest('/api/dsm/generate', config, 'POST')
  },
  
  /**
   * 获取DSM配置
   */
  getConfig: async () => {
    return await apiRequest('/api/dsm/config')
  },
  
  /**
   * 更新DSM配置
   * @param {object} config - DSM配置对象
   */
  updateConfig: async (config) => {
    return await apiRequest('/api/dsm/config', config, 'POST')
  },
  
  /**
   * 导出DSM数据
   * @param {string} sessionId - 会话ID
   * @param {string} format - 导出格式 (json/csv)
   */
  exportData: async (sessionId, format = 'json') => {
    return await apiRequest(`/api/dsm/export/${sessionId}?format=${format}`)
  }
}

/**
 * 统一导出
 */
export default {
  connection: connectionApi,
  log: logApi,
  recording: recordingApi,
  dsm: dsmApi,
  request: apiRequest
}

/**
 * 便捷导出函数
 */
export const apiGetRecordingSessions = () => recordingApi.getSessions()
export const apiStartRecording = (config) => recordingApi.startRecording(config)
export const apiStopRecording = () => recordingApi.stopRecording()
export const apiGetRecordingStatus = () => recordingApi.getStatus()
export const apiGenerateDSMReport = (config) => dsmApi.generateReport(config)
export const apiGetDSMConfig = () => dsmApi.getConfig()
export const apiUpdateDSMConfig = (config) => dsmApi.updateConfig(config)
export const apiExportDSMData = (sessionId, format) => dsmApi.exportData(sessionId, format)