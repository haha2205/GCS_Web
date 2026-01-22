# Apollo GCS Web

Apollo Dreamview 风格的无人机地面站 Web 版

## 项目概述

Apollo GCS Web 是一个基于 Electron + Vue 3 + Python FastAPI 的现代化无人机地面站应用。它复刻了 Apollo Dreamview 的深色界面风格，提供了实时监控、任务规划等功能。

## 技术栈

- **前端**: Vue 3 + Vite + Naive UI + Three.js + ECharts
- **后端**: Python FastAPI + WebSocket + UDP
- **桌面容器**: Electron
- **协议**: MiniQGCLinkV2.0

## 项目结构

```
Apollo-GCS-Web/
├── src-electron/          # Electron 主进程
│   ├── main.js           # 应用入口
│   └── preload.js         # 预加载脚本
├── src-frontend/          # Vue 3 前端
│   ├── src/
│   │   ├── App.vue         # 根组件
│   │   ├── main.js        # 前端入口
│   │   ├── router/        # 路由配置
│   │   ├── components/     # Vue 组件
│   │   │   └── layout/  # 布局组件
│   │   ├── views/         # 页面视图
│   │   └── assets/        # 静态资源
│   ├── index.html          # HTML 入口
│   ├── package.json        # 前端依赖
│   └── vite.config.js      # Vite 配置
├── src-python/            # Python FastAPI 后端
│   ├── main.py            # FastAPI 应用入口
│   ├── requirements.txt    # Python 依赖
│   ├── protocol/          # 协议解析模块
│   └── websocket/         # WebSocket 管理器
└── package.json            # 项目根配置
```

## 快速开始

### 环境要求

- Node.js 16+
- Python 3.8+
- npm 或 yarn
- Windows 11 / macOS / Linux

### 安装依赖

#### 方式一：一键安装（推荐）

```bash
# 在项目根目录执行
npm install
```

这个命令会自动：
- 安装根目录的Node.js依赖（Electron、concurrently等）
- 安装前端的Node.js依赖（Vue 3、Vite、Naive UI等）
- 安装后端的Python依赖（FastAPI、uvicorn等）

#### 方式二：分别安装

```bash
# 1. 安装根目录依赖
npm install

# 2. 安装前端依赖
cd src-frontend
npm install
cd ..

# 3. 安装后端依赖
cd src-python
pip install -r requirements.txt
```

### 启动项目

#### 方式一：一键启动所有服务（推荐）

```bash
# 在项目根目录执行，同时启动 Electron、前端和后端
npm run dev
```

这个命令会同时启动：
- Electron 桌面应用
- Vue 3 前端开发服务器（端口：5173）
- Python FastAPI 后端服务器（端口：8000）

**启动顺序说明：**
1. 后端服务器启动完毕后显示：`Uvicorn running on http://0.0.0.0:8000`
2. 前端服务器启动完毕后显示：`Local: http://localhost:5173/`
3. Electron 应用会自动加载前端页面

#### 方式二：分别启动各个服务

如果您需要分别控制各个服务，可以使用以下命令：

**步骤1：启动后端服务**

```bash
# 在项目根目录执行
npm run dev:backend
```

或者直接使用Python命令：

```bash
cd src-python
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**验证后端启动成功：**
- 终端显示：`INFO: Uvicorn running on http://0.0.0.0:8000`
- 浏览器访问：http://localhost:8000/docs 查看API文档
- 浏览器访问：http://localhost:8000/health 检查服务状态

**步骤2：启动前端服务**

```bash
# 在项目根目录执行
npm run dev:frontend
```

或者直接使用Vite命令：

```bash
cd src-frontend
npm run dev
```

**验证前端启动成功：**
- 终端显示：`Local: http://localhost:5173/`
- 浏览器访问：http://localhost:5173/ 查看前端界面

**步骤3：启动Electron桌面应用（可选）**

```bash
# 在项目根目录执行
npm run dev:electron
```

**注意：** Electron应用需要在前端和后端都已启动的情况下才能正常工作。

### 启动流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     启动流程                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. npm install (安装所有依赖)                               │
│         ↓                                                   │
│  2. npm run dev (一键启动)                                   │
│         │                                                   │
│         ├───→ 后端服务 (Python FastAPI)                     │
│         │        端口: 8000                                   │
│         │        功能: UDP通信、WebSocket、数据解析           │
│         │                                                   │
│         ├───→ 前端服务 (Vue 3 + Vite)                        │
│         │        端口: 5173                                   │
│         │        功能: 用户界面、WebSocket连接               │
│         │                                                   │
│         └───→ Electron应用 (桌面容器)                         │
│                  功能: 封装前后端为桌面应用                  │
│                                                              │
│  3. 浏览器访问 http://localhost:5173/                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 常见启动问题排查

#### 问题1：后端启动失败 - 端口被占用

**错误信息：**
```
[Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000):
address already in use
```

**解决方案：**

Windows系统：
```bash
# 查找占用8000端口的进程
netstat -ano | findstr :8000

# 根据PID结束进程
taskkill /PID <进程ID> /F
```

Linux/macOS系统：
```bash
# 查找占用8000端口的进程
lsof -i :8000

# 根据PID结束进程
kill <进程ID>
```

#### 问题2：前端启动失败 - 依赖缺失

**错误信息：**
```
Error: Cannot find module 'vite'
```

**解决方案：**
```bash
cd src-frontend
npm install
```

#### 问题3：Python依赖安装失败

**错误信息：**
```
error: Microsoft Visual C++ 14.0 is required
```

**解决方案：**
- 下载并安装 [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- 或使用预编译的wheel包：`pip install --only-binary :all: -r requirements.txt`

### 生产构建

```bash
# 构建前端
npm run build:frontend

# 构建桌面应用
npm run build
```

## 主要功能

### 1. 实时监控
- 飞行姿态显示（滚转、俯仰、偏航）
- 速度信息显示（地速 X/Y/Z）
- 位置信息显示（经纬度、高度）
- 系统状态监控（GPS、电池、连接状态）

### 2. 地图显示
- 实时位置跟踪
- 航线显示
- 障碍物标记
- 安全区域显示

### 3. 任务规划
- 航点编辑
- 任务上传
- 轨迹预览
- 任务执行监控

### 4. 数据记录
- 飞行日志记录
- 数据导出
- 数据回放

## 协议说明

项目使用 MiniQGCLinkV2.0 协议进行数据通信：

### UDP 数据包格式

- **包头**: `\xAA\xBB\xCC\xDD` (4 字节)
- **数据类型**: 2 字节 unsigned short
- **数据长度**: 2 字节 unsigned short
- **数据内容**: 根据数据类型变化

### 数据类型

- `0x0001`: 状态数据 (STATES)
- `0x0002`: 控制数据 (GNCBUS)
- `0x0003`: 航点数据 (WAYPOINT)
- `0x0004`: 雷达数据 (LIDAR)

### WebSocket 通信

前后端通过 WebSocket 进行实时数据推送：

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/drone');

// 接收数据
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // 处理接收到的数据
};
```

## 开发规范

### 代码风格
- 使用 ESLint 进行代码检查
- 遵循 Vue 3 Composition API 规范
- 使用 TypeScript 类型检查（待添加）

### 提交规范
- 提交前运行 `npm run lint`
- 提交信息格式：`type(scope): subject`
- types: feat, fix, docs, style, refactor, test, chore

### 分支策略
- `main`: 稳定主分支
- `develop`: 开发分支
- `feature/*`: 功能分支
- `bugfix/*`: 修复分支

## 配置说明

### UDP 配置
- 默认监听端口: `14550`
- 默认监听地址: `0.0.0.0`

### WebSocket 配置
- WebSocket 端点: `/ws/drone`
- 支持多客户端并发连接

### 前端配置
- 开发服务器端口: `5173`
- 生产构建输出: `src-frontend/dist/`

## 故障排查

### 问题：前端界面空白或无法正常显示

#### 1. 清除浏览器缓存
```bash
# 在浏览器中按 F12 打开开发者工具
# 右键点击刷新按钮，选择"清空缓存并硬性重新加载"
# 或者使用 Ctrl + Shift + Delete 清除浏览器缓存
```

#### 2. 检查浏览器控制台
按 F12 打开浏览器开发者工具，查看 Console 标签页：
- 是否有 JavaScript 错误？
- 是否有网络请求失败？
- 资源是否正确加载？

#### 3. 检查网络请求
在开发者工具的 Network 标签页中：
- 确认 `/src/main.js` 正确加载
- 确认所有 CSS 和字体文件正确加载
- 确认 WebSocket 连接正常

#### 4. 强制刷新页面
- Windows: `Ctrl + F5`
- Mac: `Cmd + Shift + R`

#### 5. 检查前端服务是否正常
```bash
# 确认前端开发服务器正在运行
cd Apollo-GCS-Web
npm run dev:frontend

# 应该在终端中看到类似输出：
# VITE v4.x.x  ready in xxx ms
# ➜  Local:   http://localhost:5173/
```

#### 6. 检查端口是否被占用
```bash
# Windows
netstat -ano | findstr :5173

# 如果端口被占用，可以终止进程
taskkill /PID <进程ID> /F
```

#### 7. 重启开发服务器
```bash
# 停止当前运行的前端服务 (Ctrl + C)
# 重新启动
cd Apollo-GCS-Web
npm run dev:frontend
```

#### 8. 检查 Vue 组件是否正确渲染
在浏览器控制台中运行：
```javascript
// 检查 Vue 应用是否挂载
document.querySelector('#app')._vnode

// 检查路由是否正常工作
console.log(window.$router)
```

#### 9. 验证 CSS 样式
在浏览器控制台中运行：
```javascript
// 检查全局 CSS 是否加载
document.querySelectorAll('link[rel="stylesheet"]')

// 检查 Apollo 布局元素的样式
document.querySelector('#app').style
```

### 问题：WebSocket 连接失败

#### 1. 确认后端服务运行
```bash
# 启动 Python 后端
cd Apollo-GCS-Web
npm run dev:backend

# 应该看到输出：
# INFO: Uvicorn running on http://0.0.0.0:8000
```

#### 2. 测试 WebSocket 连接
在浏览器控制台中运行：
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/drone');
ws.onopen = () => console.log('WebSocket 已连接');
ws.onclose = (e) => console.log('WebSocket 已关闭', e);
ws.onerror = (e) => console.error('WebSocket 错误', e);
```

#### 3. 检查防火墙设置
确保 Windows 防火墙允许以下端口的入站连接：
- 端口 8000 (HTTP/WS)
- 端口 5173 (Vite 开发服务器)

#### 4. 检查后端日志
在 Python 后端终端中查看是否有错误信息或连接日志。

### 问题：UDP 数据无法接收

#### 1. 确认飞控设备是否发送数据
确认飞控设备或模拟器正在向正确的地址和端口发送 UDP 数据。

#### 2. 检查端口配置
确认 `src-python/main.py` 中的 UDP 端口配置正确：
```python
HOST = "0.0.0.0"  # 监听所有接口
PORT = 14550       # 默认端口
```

#### 3. 使用网络调试工具测试
使用 Wireshark 或其他网络抓包工具验证 UDP 数据包是否到达。

#### 4. 检查 Python WebSocket 日志
在后端终端中查看是否有数据接收和解析的日志输出。

### 问题：组件样式异常

#### 1. 确认全局 CSS 已加载
检查 `src-frontend/src/assets/styles/main.css` 文件是否存在且内容正确。

#### 2. 检查 CSS 导入
在 `src-frontend/src/App.vue` 中确认有全局样式导入：
```javascript
import './assets/styles/main.css';
```

#### 3. 使用浏览器开发工具检查样式
- 右键点击元素 → 检查
- 在 Styles 面板中查看应用到元素的样式
- 检查是否有样式被覆盖

#### 4. 验证 Naive UI 组件库
确认 Naive UI 组件库已正确安装和配置：
```bash
# 检查 package.json 中是否有 naive-ui 依赖
cat src-frontend/package.json | grep naive-ui

# 如果没有，重新安装
cd src-frontend
npm install naive-ui
```

### 问题：Electron 应用无法启动

#### 1. 检查 Electron 安装
```bash
cd Apollo-GCS-Web
npm install electron --save-dev
```

#### 2. 检查 preload.js 路径
在 `src-electron/main.js` 中确认 preload 脚本路径正确。

#### 3. 启动 Electron 开发模式
```bash
# 先启动前端和后端
npm run dev:frontend
npm run dev:backend

# 然后启动 Electron
npm run dev:electron
```

#### 4. 查看 Electron 控制台
在 Electron 窗口中按 `Ctrl + Shift + I` 打开开发者工具，查看控制台错误。

## 已知问题与解决方案

| 问题 | 解决方案 |
|------|----------|
| Windows 上 Python asyncio 不兼容 | 使用 `loop.create_datagram_endpoint()` 而非 `sock_recvfrom()` |
| 前端界面空白 | 清除浏览器缓存或使用无痕模式 |
| WebSocket 连接超时 | 检查后端服务是否正常运行，确认防火墙设置 |
| UDP 数据解析失败 | 确认协议格式正确，检查 `protocol_parser.py` 中的字节序配置 |
| Three.js 场景黑屏 | 检查 WebGL 支持，更新显卡驱动程序 |

## 性能优化

- 使用 WebSocket 进行实时数据推送，避免轮询
- 数据更新频率控制在 20Hz 以内
- 大量数据更新使用批量更新
- 图表数据点数量限制在 500 个以内

## 安全考虑

- WebSocket 连接需要验证（待实现）
- UDP 通信需要加密（可选）
- 文件路径需要安全验证
- 避免直接执行用户输入的命令

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -am 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

MIT License - 详见 LICENSE 文件

## 联系方式

- 项目负责人: Tianjin University
- 技术支持: [待添加]
- 问题反馈: [待添加]

## 致谢

- 原项目 MiniQGC_Pro 协议定义来源于天津大学无人机项目
- Apollo Dreamview 设计灵感来源于 Apollo Auto 项目
- 感谢所有贡献者的支持

## 版本历史

### v0.1.0 (当前版本)
- 初始框架搭建
- MiniQGCLinkV2.0 协议迁移
- Vue 3 + Pinia 状态管理
- WebSocket 实时通信
- Apollo 风格基础界面