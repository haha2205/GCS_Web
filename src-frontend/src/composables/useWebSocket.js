/**
 * WebSocket Composable
 * 提供 WebSocket 连接管理功能
 */
import { ref } from 'vue'

export function useWebSocket(url) {
  const ws = ref(null)
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref(null)
  
  // KPI 数据状态
  const kpiData = ref({
    timestamp: null,
    dimensions: {
      computing: null,
      communication: null,
      energy: null,
      mission: null,
      performance: null
    },
    overallScore: null
  })
  
  // 消息处理器回调
  let messageHandler = null
  let openHandler = null
  let closeHandler = null
  let errorHandler = null
  
  // 手动清理函数，由调用者在组件的 onUnmounted 中调用
  function cleanup() {
    disconnect()
  }
  
  /**
   * 连接 WebSocket
   */
  function connect() {
    if (connected.value || connecting.value) {
      console.warn('WebSocket 已连接或正在连接中')
      return
    }
    
    connecting.value = true
    error.value = null
    
    try {
      ws.value = new WebSocket(url)
      
      ws.value.onopen = () => {
        console.log('WebSocket 连接已建立:', url)
        connected.value = true
        connecting.value = false
        error.value = null
        
        if (openHandler) {
          openHandler()
        }
      }
      
      ws.value.onmessage = (event) => {
        if (messageHandler) {
          try {
            const data = typeof event.data === 'string'
              ? JSON.parse(event.data)
              : event.data
            
            // 处理 KPI 更新消息
            if (data.type === 'kpi_update') {
              handleKPIUpdate(data)
            }
            
            messageHandler(data)
          } catch (e) {
            console.error('解析消息失败:', e)
          }
        }
      }
      
      ws.value.onclose = (event) => {
        console.log('WebSocket 连接已关闭, code:', event.code)
        connected.value = false
        connecting.value = false
        
        if (closeHandler) {
          closeHandler(event)
        }
      }
      
      ws.value.onerror = (event) => {
        console.error('WebSocket 错误:', event)
        error.value = event
        connecting.value = false
        
        if (errorHandler) {
          errorHandler(event)
        }
      }
    } catch (e) {
      console.error('创建 WebSocket 失败:', e)
      error.value = e
      connecting.value = false
      
      if (errorHandler) {
        errorHandler(e)
      }
    }
  }
  
  /**
   * 处理 KPI 数据更新
   */
  function handleKPIUpdate(messageData) {
    if (messageData.type === 'kpi_update' && messageData.data) {
      kpiData.value = {
        timestamp: messageData.timestamp,
        dimensions: messageData.data.dimensions || {},
        overallScore: messageData.data.overallScore
      }
      console.log('[WebSocket] KPI数据已更新:', kpiData.value)
    }
  }
  
  /**
   * 启动录制
   */
  function startRecording() {
    if (!connected.value) {
      console.warn('[WebSocket] 未连接，无法启动录制')
      return false
    }
    
    const message = {
      type: 'recording',
      action: 'start'
    }
    send(message)
    return true
  }
  
  /**
   * 停止录制
   */
  function stopRecording() {
    if (!connected.value) {
      console.warn('[WebSocket] 未连接，无法停止录制')
      return false
    }
    
    const message = {
      type: 'recording',
      action: 'stop'
    }
    send(message)
    return true
  }
  
  /**
   * 断开连接
   */
  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
      connected.value = false
      connecting.value = false
    }
  }
  
  /**
   * 发送消息
   */
  function send(data) {
    if (!ws.value || !connected.value) {
      console.warn('WebSocket 未连接，无法发送消息')
      return false
    }
    
    try {
      const message = typeof data === 'object' 
        ? JSON.stringify(data) 
        : data
      
      ws.value.send(message)
      console.log('发送消息:', message)
      return true
    } catch (e) {
      console.error('发送消息失败:', e)
      return false
    }
  }
  
  /**
   * 设置消息处理器
   */
  function onMessage(handler) {
    messageHandler = handler
  }
  
  function onOpen(handler) {
    openHandler = handler
  }
  
  function onClose(handler) {
    closeHandler = handler
  }
  
  function onError(handler) {
    errorHandler = handler
  }
  
  return {
    ws,
    connected,
    connecting,
    error,
    connect,
    disconnect,
    cleanup,
    send,
    onMessage,
    onOpen,
    onClose,
    onError,
    kpiData,
    startRecording,
    stopRecording
  }
}