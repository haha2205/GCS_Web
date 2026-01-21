/**
 * Electron 主进程
 * Apollo-GCS-Web 无人机地面站
 * 
 * 功能：
 * 1. 启动 Python FastAPI 后端
 * 2. 创建主窗口
 * 3. 通过 IPC 与渲染进程通信
 */

const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const fs = require('fs')

let mainWindow
let pythonProcess = null
const PYTHON_PATH = process.platform === 'win32' 
  ? 'python' 
  : 'python3'

const PYTHON_SCRIPT = path.join(__dirname, '../src-python/main.py')

// ==================== 窗口创建 ====================

function createWindow() {
  // 创建浏览器窗口
  mainWindow = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1280,
    minHeight: 800,
    frame: true,
    backgroundColor: '#0D0D0D',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    }
  })

  // 加载应用
  // 开发环境：加载 Vite 开发服务器
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    // 生产环境：加载打包后的文件
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // 窗口关闭事件
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  console.log('主窗口已创建')
}

// ==================== Python 后端管理 ====================

function startPythonBackend() {
  console.log('正在启动 Python 后端...')
  console.log('Python 路径:', PYTHON_SCRIPT)

  // 检查 Python 脚本是否存在
  if (!fs.existsSync(PYTHON_SCRIPT)) {
    console.error('Python 脚本不存在:', PYTHON_SCRIPT)
    return false
  }

  // 启动 Python 进程
  pythonProcess = spawn(PYTHON_PATH, [PYTHON_SCRIPT], {
    cwd: path.join(__dirname, '../src-python'),
    stdio: 'pipe'
  })

  // 处理标准输出
  pythonProcess.stdout.on('data', (data) => {
    console.log('[Python Output]:', data.toString())
  })

  // 处理标准错误
  pythonProcess.stderr.on('data', (data) => {
    console.error('[Python Error]:', data.toString())
  })

  // 处理进程退出
  pythonProcess.on('close', (code) => {
    console.log(`Python 进程已退出，退出码: ${code}`)
    pythonProcess = null
  })

  // 处理进程错误
  pythonProcess.on('error', (error) => {
    console.error('Python 进程错误:', error)
  })

  console.log('Python 后端启动成功')
  return true
}

function stopPythonBackend() {
  if (pythonProcess) {
    console.log('正在停止 Python 后端...')
    pythonProcess.kill()
    pythonProcess = null
  }
}

// ==================== IPC 通信处理 ====================

// 获取系统信息
ipcMain.handle('get-system-info', async () => {
  return {
    platform: process.platform,
    arch: process.arch,
    nodeVersion: process.version,
    electronVersion: process.versions.electron,
    chromeVersion: process.versions.chrome,
    pythonRunning: pythonProcess !== null
  }
})

// 重启 Python 后端
ipcMain.on('restart-python-backend', () => {
  console.log('收到重启 Python 后端请求')
  stopPythonBackend()
  setTimeout(() => {
    startPythonBackend()
  }, 1000)
})

// 获取 Python 后端状态
ipcMain.handle('get-python-backend-status', async () => {
  return {
    running: pythonProcess !== null,
    pid: pythonProcess ? pythonProcess.pid : null
  }
})

// 打开开发者工具
ipcMain.on('open-devtools', () => {
  if (mainWindow) {
    mainWindow.webContents.openDevTools()
  }
})

// ==================== 应用生命周期 ====================

// 应用就绪
app.whenReady().then(() => {
  console.log('应用已就绪')
  
  // 创建窗口
  createWindow()
  
  // 启动 Python 后端
  startPythonBackend()
  
  // macOS 特殊处理
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 所有窗口关闭
app.on('window-all-closed', () => {
  console.log('所有窗口已关闭')
  
  // 停止 Python 后端
  stopPythonBackend()
  
  // macOS 除外，其他平台退出
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 应用退出前
app.on('before-quit', () => {
  console.log('应用即将退出')
  stopPythonBackend()
})

// ==================== 错误处理 ====================

process.on('uncaughtException', (error) => {
  console.error('未捕获的异常:', error)
})

process.on('unhandledRejection', (reason, promise) => {
  console.error('未处理的 Promise 拒绝:', reason)
})