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
const http = require('http')

const FIXED_BACKEND_BASE_URL = 'http://localhost:8000'

let mainWindow
let pythonProcess = null
let backendManagedByElectron = false
let appQuitting = false
let backendRestartTimer = null
const BACKEND_HEALTH_URL = `${FIXED_BACKEND_BASE_URL}/health`

function getFrontendBuildIndexPath() {
  if (app.isPackaged) {
    return path.join(__dirname, '../src-frontend/dist/index.html')
  }

  return path.join(__dirname, '../src-frontend/dist/index.html')
}

function resolveFrontendEntry() {
  if (app.isPackaged) {
    return {
      mode: 'file',
      target: getFrontendBuildIndexPath()
    }
  }

  return {
    mode: 'url',
    target: 'http://localhost:5173'
  }
}

function buildLoadingScreen(title = 'TJU-GCS', message = '前端加载中，请稍候...') {
  return `data:text/html;charset=UTF-8,${encodeURIComponent(`<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${title}</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: radial-gradient(circle at top, #22324a 0%, #10151d 45%, #0a0d12 100%);
        color: #e2e8f0;
        font-family: "Segoe UI", sans-serif;
      }
      .shell {
        text-align: center;
      }
      .spinner {
        width: 42px;
        height: 42px;
        margin: 0 auto 16px;
        border-radius: 50%;
        border: 3px solid rgba(148, 163, 184, 0.25);
        border-top-color: #38bdf8;
        animation: spin 0.8s linear infinite;
      }
      .title {
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 8px;
      }
      .message {
        font-size: 13px;
        color: #94a3b8;
      }
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="spinner"></div>
      <div class="title">${title}</div>
      <div class="message">${message}</div>
    </div>
  </body>
</html>`)}`
}

function checkHttpEndpoint(url, timeoutMs = 1200) {
  return new Promise((resolve) => {
    const request = http.get(url, (response) => {
      response.resume()
      resolve(response.statusCode >= 200 && response.statusCode < 500)
    })

    request.setTimeout(timeoutMs, () => {
      request.destroy()
      resolve(false)
    })

    request.on('error', () => {
      resolve(false)
    })
  })
}

async function waitForHttpEndpoint(url, timeoutMs = 15000, retryIntervalMs = 500) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const ready = await checkHttpEndpoint(url, Math.min(1200, retryIntervalMs + 700))
    if (ready) {
      return true
    }
    await new Promise((resolve) => setTimeout(resolve, retryIntervalMs))
  }
  return false
}

async function loadFrontendIntoWindow(window) {
  const frontendEntry = resolveFrontendEntry()
  const buildIndexPath = getFrontendBuildIndexPath()

  if (frontendEntry.mode === 'file') {
    if (!fs.existsSync(frontendEntry.target)) {
      throw new Error(`前端文件不存在: ${frontendEntry.target}`)
    }

    await window.loadFile(frontendEntry.target)
    return
  }

  const devServerReady = await waitForHttpEndpoint(frontendEntry.target)
  if (devServerReady) {
    await window.loadURL(frontendEntry.target)
    window.webContents.openDevTools()
    return
  }

  if (fs.existsSync(buildIndexPath)) {
    console.warn(`Vite 开发服务器不可用，回退到本地构建页面: ${buildIndexPath}`)
    await window.loadFile(buildIndexPath)
    return
  }

  throw new Error(`无法加载前端页面。开发地址不可用: ${frontendEntry.target}`)
}

function resolveBundledPythonScript() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', 'src-python', 'main.py')
  }
  return path.join(__dirname, '../src-python/main.py')
}

function resolveBundledPythonCwd() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', 'src-python')
  }
  return path.join(__dirname, '../src-python')
}

function resolveProjectRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend')
  }
  return path.join(__dirname, '..')
}

function resolveBackendDataRoot() {
  const targetDir = path.join(app.getPath('userData'), 'backend-data')
  fs.mkdirSync(targetDir, { recursive: true })
  return targetDir
}

function resolveDevelopmentPythonCommand() {
  const candidates = process.platform === 'win32'
    ? [
        path.join(__dirname, '../src-python/.packenv/python.exe'),
        path.join(__dirname, '../src-python/.venv/Scripts/python.exe'),
        'python'
      ]
    : [
        path.join(__dirname, '../src-python/.packenv/bin/python3'),
        path.join(__dirname, '../src-python/.venv/bin/python3'),
        'python3'
      ]

  return candidates.find((candidate) => candidate === 'python' || candidate === 'python3' || fs.existsSync(candidate))
}

function resolveBackendExecutable() {
  if (!app.isPackaged) {
    return null
  }

  const executableName = process.platform === 'win32' ? 'ApolloGCSBackend.exe' : 'apollo-gcs-backend'
  const packagedCandidate = path.join(process.resourcesPath, 'backend', executableName)
  if (fs.existsSync(packagedCandidate)) {
    return packagedCandidate
  }

  return null
}

function resolveBackendLaunchSpec() {
  const bundledExecutable = resolveBackendExecutable()
  if (bundledExecutable) {
    return {
      command: bundledExecutable,
      args: [],
      cwd: path.dirname(bundledExecutable),
      mode: 'binary'
    }
  }

  const pythonScript = resolveBundledPythonScript()
  const pythonCwd = resolveBundledPythonCwd()
  const pythonCommand = resolveDevelopmentPythonCommand()
  if (!pythonCommand) {
    throw new Error('未找到可用的 Python 解释器，请检查 src-python/.packenv 或 .venv 环境')
  }
  return {
    command: pythonCommand,
    args: [pythonScript],
    cwd: pythonCwd,
    mode: 'python-script'
  }
}

// ==================== 窗口创建 ====================

async function createWindow() {
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

  mainWindow.maximize()

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error('前端页面加载失败:', { errorCode, errorDescription, validatedURL })
  })

  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    console.error('渲染进程异常退出:', details)
  })

  mainWindow.on('unresponsive', () => {
    console.error('主窗口无响应')
  })

  await mainWindow.loadURL(buildLoadingScreen())

  try {
    await loadFrontendIntoWindow(mainWindow)
  } catch (error) {
    console.error('加载前端失败:', error)
    await mainWindow.loadURL(buildLoadingScreen('Apollo GCS', error.message || '前端加载失败'))
  }

  // 窗口关闭事件
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  console.log('主窗口已创建')
}

function checkBackendHealth(timeoutMs = 1200) {
  return new Promise((resolve) => {
    const request = http.get(BACKEND_HEALTH_URL, (response) => {
      response.resume()
      resolve(response.statusCode === 200)
    })

    request.setTimeout(timeoutMs, () => {
      request.destroy()
      resolve(false)
    })

    request.on('error', () => {
      resolve(false)
    })
  })
}

// ==================== Python 后端管理 ====================

function startPythonBackend() {
  if (pythonProcess) {
    console.log('Python 后端已在运行，跳过重复启动')
    return true
  }

  console.log('正在启动 Python 后端...')
  const backendLaunchSpec = resolveBackendLaunchSpec()
  console.log('后端启动模式:', backendLaunchSpec.mode)
  console.log('后端启动路径:', backendLaunchSpec.command)

  if (backendLaunchSpec.mode === 'python-script' && !fs.existsSync(backendLaunchSpec.args[0])) {
    console.error('Python 脚本不存在:', backendLaunchSpec.args[0])
    return false
  }

  if (backendLaunchSpec.mode === 'binary' && !fs.existsSync(backendLaunchSpec.command)) {
    console.error('后端可执行文件不存在:', backendLaunchSpec.command)
    return false
  }

  pythonProcess = spawn(backendLaunchSpec.command, backendLaunchSpec.args, {
    cwd: backendLaunchSpec.cwd,
    stdio: 'pipe',
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      APOLLO_GCS_PYTHON_ROOT: resolveBundledPythonCwd(),
      APOLLO_GCS_PROJECT_ROOT: resolveProjectRoot(),
      APOLLO_GCS_DATA_ROOT: resolveBackendDataRoot()
    }
  })
  backendManagedByElectron = true

  // 处理标准输出
  pythonProcess.stdout.on('data', (data) => {
    console.log('[Python Output]:', data.toString())
  })

  // 处理标准错误（Python logging 默认输出到 stderr，INFO 级别也会走这里）
  pythonProcess.stderr.on('data', (data) => {
    console.log('[Python Log]:', data.toString())
  })

  // 处理进程退出
  pythonProcess.on('close', (code) => {
    console.log(`Python 进程已退出，退出码: ${code}`)
    pythonProcess = null

    if (backendRestartTimer) {
      clearTimeout(backendRestartTimer)
      backendRestartTimer = null
    }

    if (!appQuitting && backendManagedByElectron) {
      backendRestartTimer = setTimeout(async () => {
        backendRestartTimer = null
        const backendAlive = await checkBackendHealth()
        if (!backendAlive && !pythonProcess) {
          console.log('检测到后端进程意外退出，正在自动重启...')
          startPythonBackend()
        }
      }, 1200)
    }
  })

  // 处理进程错误
  pythonProcess.on('error', (error) => {
    console.error('Python 进程错误:', error)
  })

  console.log('Python 后端启动成功')
  return true
}

async function ensurePythonBackend() {
  const backendAlive = await checkBackendHealth()
  if (backendAlive) {
    console.log('检测到已有后端实例在运行，Electron 将直接复用')
    backendManagedByElectron = false
    return true
  }

  return startPythonBackend()
}

function stopPythonBackend() {
  if (backendRestartTimer) {
    clearTimeout(backendRestartTimer)
    backendRestartTimer = null
  }

  if (pythonProcess && backendManagedByElectron) {
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

ipcMain.handle('get-runtime-config', async () => {
  return {
    isDesktopApp: true,
    backendBaseUrl: FIXED_BACKEND_BASE_URL
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
  ensurePythonBackend()
  
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
  
  // macOS 除外，其他平台退出
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 应用退出前
app.on('before-quit', () => {
  console.log('应用即将退出')
  appQuitting = true
  stopPythonBackend()
})

// ==================== 错误处理 ====================

process.on('uncaughtException', (error) => {
  console.error('未捕获的异常:', error)
})

process.on('unhandledRejection', (reason, promise) => {
  console.error('未处理的 Promise 拒绝:', reason)
})