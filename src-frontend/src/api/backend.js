/**
 * 后端 API 客户端
 * 提供 RESTful API 调用接口
 */

function normalizeBaseUrl(url) {
  return url ? url.replace(/\/$/, '') : ''
}

const DEFAULT_BACKEND_BASE_URL = 'http://localhost:8000'

function isTransientNetworkError(error) {
  if (!error) {
    return false
  }

  return error.name === 'AbortError' || error.message === 'Failed to fetch'
}

function buildBackendUnavailableError() {
  return new Error('后端暂未就绪，请稍后重试')
}

export function isBackendUnavailableError(error) {
  return error?.message === '后端暂未就绪，请稍后重试'
}

function getDesktopRuntimeBaseUrl() {
  if (typeof window === 'undefined') {
    return ''
  }

  const runtimeBaseUrl = window.electronAPI?.runtime?.backendBaseUrl
  return normalizeBaseUrl(runtimeBaseUrl)
}

let cachedBackendBaseUrl = null

function uniqueBaseUrls(urls = []) {
  return [...new Set(urls.filter(Boolean).map((url) => normalizeBaseUrl(url)))]
}

function getBackendBaseUrlCandidates() {
  const envBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)
  if (envBaseUrl) {
    return [envBaseUrl]
  }

  const desktopRuntimeBaseUrl = getDesktopRuntimeBaseUrl()
  if (desktopRuntimeBaseUrl) {
    return uniqueBaseUrls([desktopRuntimeBaseUrl])
  }

  const browserHost = typeof window !== 'undefined' ? window.location.hostname : ''
  const normalizedHost = browserHost && browserHost !== '0.0.0.0' ? browserHost : 'localhost'

  return uniqueBaseUrls([
    `http://${normalizedHost}:8000`,
    DEFAULT_BACKEND_BASE_URL,
    'http://127.0.0.1:8000'
  ])
}

async function probeBackendBaseUrl(baseUrl, timeoutMs = 900) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${baseUrl}/health`, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-store'
    })
    return response.ok
  } catch (error) {
    return false
  } finally {
    clearTimeout(timer)
  }
}

function getDefaultBackendBaseUrl() {
  return getBackendBaseUrlCandidates()[0] || DEFAULT_BACKEND_BASE_URL
}

export function getBackendBaseUrl() {
  if (cachedBackendBaseUrl) {
    return cachedBackendBaseUrl
  }

  return getDefaultBackendBaseUrl()
}

export function clearBackendBaseUrlCache() {
  cachedBackendBaseUrl = null
}

export async function resolveBackendBaseUrl(forceRefresh = false) {
  if (!forceRefresh && cachedBackendBaseUrl) {
    const cachedHealthy = await probeBackendBaseUrl(cachedBackendBaseUrl)
    if (cachedHealthy) {
      return cachedBackendBaseUrl
    }
  }

  const candidates = getBackendBaseUrlCandidates()
  for (const candidate of candidates) {
    const healthy = await probeBackendBaseUrl(candidate)
    if (healthy) {
      cachedBackendBaseUrl = candidate
      return candidate
    }
  }

  cachedBackendBaseUrl = getDefaultBackendBaseUrl()
  return cachedBackendBaseUrl
}

export function buildApiUrl(endpoint = '') {
  const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${getBackendBaseUrl()}${normalizedEndpoint}`
}

/**
 * 通用 API 请求封装
 * @param {string} endpoint - API端点
 * @param {object} data - 请求数据
 * @param {string} method - HTTP方法 (GET/POST)
 * @returns {Promise<any>}
 */
async function apiRequest(endpoint, data = null, method = 'GET') {
  const baseUrl = await resolveBackendBaseUrl()
  const url = `${baseUrl}${endpoint}`
  
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
    clearBackendBaseUrlCache()

    if (isTransientNetworkError(error)) {
      throw buildBackendUnavailableError()
    }

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
 * UDP连接管理 API
 */
export const udpApi = {
  /**
   * 启动UDP服务器
   */
  startServer: async () => {
    return await apiRequest('/api/udp/start', {}, 'POST')
  },
  
  /**
   * 停止UDP服务器
   */
  stopServer: async () => {
    return await apiRequest('/api/udp/stop', {}, 'POST')
  },
  
  /**
   * 获取UDP连接状态
   */
  getStatus: async () => {
    return await apiRequest('/api/udp/status')
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
 * 回放数据 API
 */
export const replayApi = {
  /**
   * 获取回放文件列表
   */
  getFiles: async () => {
    return await apiRequest('/api/replay/files')
  },
  
  /**
   * 上传回放文件
   * @param {File} file - CSV文件
   */
  uploadFile: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    
    const url = buildApiUrl('/api/replay/upload')
    const options = {
      method: 'POST'
    }
    
    try {
      const response = await fetch(url, options)
      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`API 请求失败: ${response.status} - ${errorText}`)
      }
      return await response.json()
    } catch (error) {
      console.error('上传回放文件失败:', error)
      throw error
    }
  },
  
  /**
   * 获取回放状态
   */
  getStatus: async () => {
    return await apiRequest('/api/replay/status')
  },
  
  /**
   * 控制回放
   * @param {object} params - 控制参数
   */
  controlReplay: async (params) => {
    return await apiRequest('/api/replay/control', params, 'POST')
  },
  
  /**
   * 获取回放变量列表（新增）
   */
  getHeaders: async () => {
    return await apiRequest('/api/replay/headers')
  },
  
  /**
   * 获取回放变量数据（新增）
   * @param {object} params - {variables, max_points}
   */
  getSeries: async (params) => {
    return await apiRequest('/api/replay/series', params, 'POST')
  }
}

/**
 * 统一导出
 */
export default {
  connection: connectionApi,
  log: logApi,
  recording: recordingApi,
  replay: replayApi,
  udp: udpApi,
  request: apiRequest
}

/**
 * 便捷导出函数
 */
export const apiGetRecordingSessions = () => recordingApi.getSessions()
export const apiStartRecording = (config) => recordingApi.startRecording(config)
export const apiStopRecording = () => recordingApi.stopRecording()
export const apiGetRecordingStatus = () => recordingApi.getStatus()
