/**
 * Electron 预加载脚本
 * 暴露安全的 API 给渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron')

// 暴露 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取系统信息
  getSystemInfo: () => ipcRenderer.invoke('get-system-info'),
  
  // 重启 Python 后端
  restartPythonBackend: () => ipcRenderer.send('restart-python-backend'),
  
  // 获取 Python 后端状态
  getPythonBackendStatus: () => ipcRenderer.invoke('get-python-backend-status'),
  
  // 打开开发者工具
  openDevTools: () => ipcRenderer.send('open-devtools'),
  
  // 监听 Python 后端状态变化
  onPythonBackendStatusChange: (callback) => {
    // 这里可以添加状态变化监听
  }
})

// 移除 Node 集成（安全）
delete window.require
delete window.exports
delete window.module