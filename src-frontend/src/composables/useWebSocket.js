/**
 * WebSocket Composable
 * 提供 WebSocket 连接管理功能
 */
import { ref } from 'vue'

export function useWebSocket(url, options = {}) {
  const ws = ref(null)
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref(null)
  const reconnectEnabled = ref(true)
  const reconnectAttempts = ref(0)
  const pingIntervalMs = Number(options.pingIntervalMs) || 2500
  const staleTimeoutMs = Math.max(Number(options.staleTimeoutMs) || 8000, pingIntervalMs * 2)
  let reconnectTimer = null
  let manualDisconnect = false
  let keepAliveTimer = null
  let staleCheckTimer = null
  let lastMessageAt = 0
  
  // 消息处理器回调
  let messageHandler = null
  let openHandler = null
  let closeHandler = null
  let errorHandler = null
  
  // 手动清理函数，由调用者在组件的 onUnmounted 中调用
  function cleanup() {
    reconnectEnabled.value = false
    disconnect()
  }

  function stopConnectionMonitors() {
    if (keepAliveTimer) {
      clearInterval(keepAliveTimer)
      keepAliveTimer = null
    }
    if (staleCheckTimer) {
      clearInterval(staleCheckTimer)
      staleCheckTimer = null
    }
  }

  function markAlive() {
    lastMessageAt = Date.now()
  }

  function startConnectionMonitors() {
    stopConnectionMonitors()
    markAlive()

    keepAliveTimer = setInterval(() => {
      if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
        return
      }

      try {
        ws.value.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }))
      } catch (sendError) {
        console.warn('WebSocket ping 发送失败:', sendError)
      }
    }, pingIntervalMs)

    staleCheckTimer = setInterval(() => {
      if (!ws.value || ws.value.readyState !== WebSocket.OPEN || manualDisconnect) {
        return
      }

      if (Date.now() - lastMessageAt <= staleTimeoutMs) {
        return
      }

      console.warn(`WebSocket 超过 ${staleTimeoutMs}ms 未收到消息，准备重连`)
      try {
        ws.value.close(4000, 'stale connection')
      } catch (closeError) {
        console.warn('关闭过期 WebSocket 失败:', closeError)
      }
    }, 1000)
  }
  
  /**
   * 连接 WebSocket
   */
  function connect() {
    if (connected.value || connecting.value) {
      console.warn('WebSocket 已连接或正在连接中')
      return
    }

    manualDisconnect = false
    reconnectEnabled.value = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
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
        reconnectAttempts.value = 0
        markAlive()
        startConnectionMonitors()
        
        if (openHandler) {
          openHandler()
        }
      }
      
      ws.value.onmessage = (event) => {
        markAlive()
        if (messageHandler) {
          try {
            const data = typeof event.data === 'string'
              ? JSON.parse(event.data)
              : event.data

            messageHandler(data)
          } catch (e) {
            console.error('解析消息失败:', e)
          }
        }
      }
      
      ws.value.onclose = (event) => {
        console.log('WebSocket 连接已关闭, code:', event.code)
        stopConnectionMonitors()
        connected.value = false
        connecting.value = false
        ws.value = null
        
        if (closeHandler) {
          closeHandler(event)
        }

        scheduleReconnect()
      }
      
      ws.value.onerror = (event) => {
        console.error('WebSocket 错误:', event)
        error.value = event
        
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

  function scheduleReconnect() {
    if (!reconnectEnabled.value || manualDisconnect) {
      return
    }

    if (reconnectTimer || connected.value || connecting.value) {
      return
    }

    reconnectAttempts.value += 1
    const delay = Math.min(5000, 500 * Math.pow(2, reconnectAttempts.value - 1))

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
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
    manualDisconnect = true
    reconnectEnabled.value = false
    stopConnectionMonitors()
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
    connecting.value = false
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
    startRecording,
    stopRecording
  }
}