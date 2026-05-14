# Apollo GCS Web 使用与二次开发说明

本文档面向软件交付、部署使用和后续飞控适配开发，说明 Apollo GCS Web 的组成、核心功能、运行环境、启动顺序、数据接口和二次开发方式。

## 1. 软件组成

Apollo GCS Web 是一个“前端界面 + Python 通信后端 + 可选 Electron 桌面壳”的无人机地面站软件。当前代码仓库中与运行直接相关的部分如下：

| 组成 | 路径 | 作用 |
| --- | --- | --- |
| 前端界面 | `src-frontend/` | Vue 3 + Vite 页面，负责地面站界面、仪表盘、图表、3D 视图、任务/参数/录制控制、WebSocket 实时数据展示。 |
| Python 后端 | `src-python/` | FastAPI 服务，负责 UDP 通信、MiniQGCLinkV2.0 协议解析、指令编码下发、WebSocket 推送、数据录制、在线分析转发。 |
| Electron 桌面容器 | `src-electron/` | 可选桌面外壳，负责启动/复用 Python 后端、加载前端页面、提供桌面应用窗口。 |
| 根目录工程配置 | `package.json` | 统一安装、启动、构建脚本，以及 Electron 打包配置。 |
| 数据与记录目录 | `Log/Records/` | 实飞或联调数据记录输出目录。开发模式默认写入项目根目录；Electron 打包后默认写入用户数据目录。 |
| 文档与架构图 | `docs/` | 架构说明、传输审计、界面性能排查等工程文档。 |

### 是否只提供两个代码包就能使用

如果“两个代码包”指 `src-frontend/` 和 `src-python/`：

- 可以支撑浏览器版 Web 地面站运行。用户分别安装前端和后端依赖，先启动 Python 后端，再启动 Vite 前端，即可通过浏览器访问界面。
- 需要同时提供运行配置说明，尤其是 UDP 监听地址、监听端口、飞控目标 IP、目标端口，以及 Python/Node.js 环境。
- 如果需要 Electron 桌面应用、一键启动脚本、打包安装包，则还需要根目录 `package.json`、`src-electron/` 和相关图标/构建配置。只给 `src-frontend/` 与 `src-python/` 不包含完整桌面应用交付能力。
- 如果要连接真实飞控，还必须保证飞控输出协议与当前后端的 MiniQGCLinkV2.0 帧格式、功能字、字段布局一致；否则需要进行协议适配开发。

建议交付方式：

1. 浏览器版交付：提供 `src-frontend/`、`src-python/`、`README.md`、本说明文档、`.env.example` 或等价配置说明。
2. 桌面版源码交付：提供完整仓库，包含根目录 `package.json` 和 `src-electron/`。
3. 免环境安装交付：提供已打包安装包或压缩包，并附带网络参数配置说明。

## 2. 核心功能

### 2.1 实时数据接收与解析

后端启动后会自动启动 UDP 接收链路。当前默认监听端口为：

| 端口 | 用途 |
| --- | --- |
| `30509` | 当前实机飞控遥测主入口。 |
| `18506` | 飞控遥测兼容降级监听口，同时也是上行指令固定源端口相关配置。 |
| `18507` | LiDAR/雷达兼容数据口。 |
| `18511` | 规划模块遥测入口。 |

后端接收 UDP 数据后，通过 `src-python/protocol/protocol_parser.py` 调用 `src-python/protocol/nclink_protocol.py` 解析 MiniQGCLinkV2.0 二进制帧，并转换成前端可消费的消息类型，例如：

| 消息类型 | 说明 |
| --- | --- |
| `fcs_states` | 飞控状态，经纬高、姿态、速度等状态量。 |
| `fcs_pwms` | 电机/PWM 输出。 |
| `fcs_datactrl` | 控制环内部数据。 |
| `fcs_gncbus` | 飞控与 GNC/SoC 相关总线数据。 |
| `fcs_datagcs` | 飞控回传给地面站的数据。 |
| `fcs_param` | 飞控参数回传。 |
| `avoiflag` | 避障相关标志。 |
| `planning_telemetry` | 规划遥测、路径、轨迹、障碍物等信息。 |

### 2.2 实时前端显示

前端通过 WebSocket 连接后端 `/ws/drone`，接收统一格式的消息：

```json
{
  "type": "udp_data",
  "timestamp": 1710000000000,
  "source": "apollo_backend",
  "schema_version": "v1.0",
  "data": {
    "type": "fcs_states",
    "data": {}
  }
}
```

前端 `src-frontend/src/store/drone.js` 根据 `data.type` 分发到不同的状态更新函数，用于仪表盘、右侧监控面板、图表、3D 视图、规划轨迹、障碍物显示等界面。

### 2.3 指令下发

后端提供 REST 和 WebSocket 两种入口，最终都会调用统一的 UDP 指令发送链路。

REST 入口：

```http
POST /api/command
```

支持的指令类型：

| 指令类型 | 通道 | 说明 |
| --- | --- | --- |
| `cmd_idx` | 飞控 | 下发飞控瞬时指令编号。编号 `1..25` 会按 500 ms 间隔重复发送 6 次，之后自动发送 `cmd_idx=0` 清零。 |
| `cmd_mission` | 飞控 | 下发飞控任务指令及参数值。 |
| `set_pids` | 飞控 | 更新后端缓存的 PID/控制参数，并编码到飞控上行结构。 |
| `gcs_command` | 规划 | 下发目标点、巡航速度、使能位、命令编号等规划指令。 |
| `waypoints_upload` | 规划 | 上传航点列表和巡航速度。 |

后端对飞控通道和规划通道分别做发送节流，当前同通道最小发送间隔为 500 ms。

### 2.4 数据录制

后端支持 REST 和 WebSocket 启停录制。

REST 入口：

```http
POST /api/recording/start
POST /api/recording/stop
GET  /api/recording/status
```

默认输出目录：

```text
Log/Records/<session_id>/
```

典型输出包括：

| 输出 | 说明 |
| --- | --- |
| `records/fcs/fcs_telemetry.csv` | 飞控遥测宽表。 |
| `records/planning/planning_telemetry.csv` | 规划遥测、路径、轨迹、障碍物 JSON。 |
| `records/lidar/radar_data.csv` | 雷达/障碍物相关数据。 |
| `records/bus/bus_traffic.csv` | 按逻辑模块归类的链路流量记录。 |
| `records/communication/backend_communication.log` | 后端通信事件、录制启停、上行指令日志。 |
| `session_meta.json` | 本次录制的元数据、case id、时间范围等。 |

### 2.5 在线分析转发

后端包含 OnlineAnalysis 转发入口。默认配置为 `ONLINE_ANALYSIS_ENABLED=1`、`ONLINE_ANALYSIS_MODE=embedded`。如果项目旁边存在 OnlineAnalysis 工程，后端会尝试嵌入或转发实时消息，用于在线评测摘要显示。没有 OnlineAnalysis 时，地面站基础通信、展示和录制功能仍可使用，但在线分析面板会缺少实时评测结果。

### 2.6 运行状态与诊断

后端提供以下诊断接口：

| 接口 | 说明 |
| --- | --- |
| `GET /health` | 后端健康状态、WebSocket 连接数、队列状态、传输统计、OnlineAnalysis 状态。 |
| `GET /api/udp/status` | UDP 是否运行、监听端口、目标地址、流水线状态。 |
| `GET /api/traffic/stats` | 近窗口收发包速率、解析消息计数、拒包/问题统计。 |
| `GET /api/online-analysis/status` | 在线分析启用状态、模式、最近错误和快照。 |

## 3. 运行环境安装

### 3.1 基础环境

推荐环境：

| 环境 | 建议版本 |
| --- | --- |
| 操作系统 | Windows 10/11，Linux 或 macOS 也可运行 Web 版。 |
| Node.js | 16+，建议 18+。 |
| npm | 随 Node.js 安装。 |
| Python | 3.8+，当前打包环境使用 Python 3.11。 |
| 网络 | 地面站电脑与飞控/规划计算机处于同一可达网段，防火墙允许 UDP 端口和后端 HTTP 端口。 |

### 3.2 安装依赖

完整仓库方式：

```powershell
cd E:\Apollo-GCS-Web
npm install
```

根目录 `postinstall` 会继续安装前端依赖，并在 `src-python` 中执行：

```powershell
pip install -r requirements.txt
```

分别安装方式：

```powershell
cd E:\Apollo-GCS-Web\src-python
python -m pip install -r requirements.txt

cd E:\Apollo-GCS-Web\src-frontend
npm install
```

如果使用独立 Python 虚拟环境：

```powershell
cd E:\Apollo-GCS-Web\src-python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 3.3 网络参数配置

后端配置位于 `src-python/config.py`，也支持通过环境变量覆盖。示例见 `src-python/.env.example`。

常用变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GCS_LISTEN_HOST` | `192.168.16.13` | 地面站 UDP 绑定地址。若不确定本机地址，可联调时改为 `0.0.0.0`。 |
| `GCS_LISTEN_PORT` | `30509` | 主接收端口。 |
| `GCS_LISTEN_PORTS` | `30509,18511,18507,18506` | 多端口监听列表。 |
| `GCS_TARGET_IP` | `192.168.16.116` | 飞控或机载端接收指令的 IP。 |
| `GCS_TARGET_PORT` | `18504` | 飞控接收上行指令的端口。 |
| `GCS_HTTP_BIND_ALL` | 空 | 设为 `1` 时后端 HTTP 绑定 `0.0.0.0`，便于其他电脑访问。默认只绑定 `127.0.0.1`。 |
| `ONLINE_ANALYSIS_ENABLED` | `1` | 是否启用在线分析转发。 |
| `ONLINE_ANALYSIS_MODE` | `embedded` | 在线分析模式。 |
| `ONLINE_ANALYSIS_PROJECT_ROOT` | `../OnlineAnalysis` | OnlineAnalysis 工程路径。 |

PowerShell 临时配置示例：

```powershell
$env:GCS_LISTEN_HOST = "0.0.0.0"
$env:GCS_LISTEN_PORTS = "30509,18511,18507,18506"
$env:GCS_TARGET_IP = "192.168.16.116"
$env:GCS_TARGET_PORT = "18504"
$env:GCS_HTTP_BIND_ALL = "1"
python .\main.py
```

注意：当前前端配置页调用 `/api/config/connection` 后，后端仍会回到固定链路配置。正式部署时应通过环境变量或修改 `config.py` 设置网络参数，不应依赖运行时页面修改长期保存配置。

## 4. 启动顺序

### 4.1 浏览器版推荐启动顺序

第一步，启动 Python 后端：

```powershell
cd E:\Apollo-GCS-Web\src-python
python .\main.py
```

启动成功后，终端应出现类似信息：

```text
Uvicorn running on http://127.0.0.1:8000
UDP监听器已启动
```

验证后端：

```text
http://localhost:8000/health
http://localhost:8000/docs
```

第二步，启动前端：

```powershell
cd E:\Apollo-GCS-Web\src-frontend
npm run dev
```

访问：

```text
http://localhost:5173/
```

第三步，在前端界面连接后端。前端会自动探测：

```text
http://<浏览器访问主机>:8000
http://localhost:8000
http://127.0.0.1:8000
```

如果前后端部署在不同电脑上，应设置 `VITE_API_BASE_URL` 指向后端地址，并确保后端设置 `GCS_HTTP_BIND_ALL=1`。

### 4.2 根目录脚本启动

根目录脚本如下：

```powershell
cd E:\Apollo-GCS-Web
npm run dev:web
```

`dev:web` 会同时启动前端和后端。

```powershell
npm run dev
```

当前 `dev` 脚本会同时启动 Electron 和前端。Electron 会自行检测并启动或复用 Python 后端。因此桌面调试时可使用 `npm run dev`，纯 Web 调试时建议使用 `npm run dev:web` 或分别启动。

### 4.3 Electron 桌面版启动

开发模式：

```powershell
cd E:\Apollo-GCS-Web
npm run dev
```

Electron 逻辑：

1. 检查 `http://localhost:8000/health` 是否已有后端。
2. 如果已有后端，则直接复用。
3. 如果没有，则使用 `src-python/.packenv/python.exe`、`src-python/.venv/Scripts/python.exe` 或系统 `python` 启动 `src-python/main.py`。
4. 加载 `http://localhost:5173` 前端开发服务。

打包构建：

```powershell
cd E:\Apollo-GCS-Web
npm run build:win
```

后端打包依赖：

```powershell
cd E:\Apollo-GCS-Web\src-python
python -m pip install -r requirements-build.txt
```

## 5. 数据接口说明

### 5.1 后端 REST 接口

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/` | 后端基本信息。 |
| `GET` | `/health` | 健康检查与运行状态。 |
| `GET` | `/api/traffic/stats` | UDP 收发、解析、拒包统计。 |
| `GET` | `/api/config/connection` | 获取连接配置与端口语义。 |
| `POST` | `/api/config/connection` | 触发连接配置刷新；当前固定链路模式下不保存运行时修改。 |
| `GET` | `/api/config/log` | 获取日志配置。 |
| `POST` | `/api/config/log` | 更新自动日志配置。 |
| `POST` | `/api/log/save` | 写入日志条目。 |
| `POST` | `/api/udp/start` | 启动或重启 UDP 服务器。 |
| `POST` | `/api/udp/stop` | 停止 UDP 服务器。 |
| `GET` | `/api/udp/status` | 获取 UDP 状态。 |
| `GET` | `/api/online-analysis/status` | 获取在线分析状态。 |
| `POST` | `/api/command` | 下发飞控/规划指令。 |
| `GET` | `/api/recording/status` | 获取录制状态。 |
| `POST` | `/api/recording/start` | 开始录制。 |
| `POST` | `/api/recording/stop` | 停止录制。 |

### 5.2 WebSocket 接口

地址：

```text
ws://localhost:8000/ws/drone
```

客户端可发送：

| 消息 | 说明 |
| --- | --- |
| `{"type":"ping"}` | 心跳测试，后端返回 `pong`。 |
| `{"type":"command","command":"cmd_idx","params":{"cmdId":1}}` | WebSocket 方式下发指令。 |
| `{"type":"recording","action":"start"}` | WebSocket 方式开始录制。 |
| `{"type":"recording","action":"stop"}` | WebSocket 方式停止录制。 |
| `{"type":"get_config","data":{"config_type":"all"}}` | 获取连接/日志配置。 |

后端会推送：

| 推送类型 | 说明 |
| --- | --- |
| `system` | WebSocket 建连消息。 |
| `udp_data` | 实时 UDP 解析数据。 |
| `udp_status_change` | UDP 链路状态。 |
| `config_update` | 配置更新。 |
| `recording_status` | 录制状态。 |
| `command_response` | 指令发送结果。 |
| `online_analysis_config` | 在线分析配置。 |
| `online_analysis_status` | 在线分析结果快照。 |

### 5.3 MiniQGCLinkV2.0 协议边界

当前后端假定机载端发送 MiniQGCLinkV2.0 二进制帧，帧头、帧尾和功能字由 `src-python/protocol/nclink_protocol.py` 定义。

基础帧常量：

| 常量 | 值 |
| --- | --- |
| 帧头 | `0xFF 0xFC` |
| 帧尾 | `0xA1 0xA2` |

关键功能字：

| 功能字 | 名称 | 对应消息 |
| --- | --- | --- |
| `0x40` | `NCLINK_SEND_EXTU_FCS` | 地面站发往飞控的控制/PID/任务上行数据。 |
| `0x41` | `NCLINK_RECEIVE_EXTY_FCS_PWMS` | `fcs_pwms`。 |
| `0x42` | `NCLINK_RECEIVE_EXTY_FCS_STATES` | `fcs_states`。 |
| `0x43` | `NCLINK_RECEIVE_EXTY_FCS_DATACTRL` | `fcs_datactrl`。 |
| `0x44` | `NCLINK_RECEIVE_EXTY_FCS_GNCBUS` | `fcs_gncbus`。 |
| `0x45` | `NCLINK_RECEIVE_EXTY_FCS_AVOIFLAG` | `avoiflag`。 |
| `0x46` | `NCLINK_RECEIVE_EXTY_FCS_DATAGCS` | `fcs_datagcs`。 |
| `0x47` | `NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AIM2AB` | `fcs_line_aim2ab`。 |
| `0x48` | `NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AB` | `fcs_line_ab`。 |
| `0x49` | `NCLINK_RECEIVE_EXTY_FCS_PARAM` | `fcs_param`。 |
| `0x4A` | `NCLINK_RECEIVE_EXTY_FCS_ESC` | `fcs_esc`。 |
| `0x70` | `NCLINK_GCS_COMMAND` | 地面站发往规划模块的任务/航点指令。 |
| `0x71` | `NCLINK_GCS_TELEMETRY` | `planning_telemetry`。 |

字段布局采用小端序解析，许多结构直接按 C/C++ 结构体长度进行校验。例如 `fcs_pwms` 为 8 个 double，共 64 字节；`fcs_states` 为 56 字节；`fcs_datactrl` 为 53 个 float，共 212 字节。

## 6. 适配其他飞控的二次开发指南

### 6.1 总体原则

你的理解基本正确：如果要适配其他飞控，核心工作就是把“飞控的数据接口”对齐到本软件后端已经使用的标准消息模型。

但这里的“接口对齐”包括三个层面：

1. 传输层对齐：飞控通过 UDP、串口、TCP、MAVLink 或其他方式发送数据，后端要能接收到。
2. 协议层对齐：后端要能解析飞控帧格式、功能字、校验和、payload 字段布局。
3. 语义层对齐：解析后的数据要映射成前端已有消息类型和字段名，例如 `fcs_states.states_lat`、`fcs_states.states_height`、`fcs_pwms.pwms`、`planning_telemetry.global_path`。

只要第三层输出保持一致，前端大部分界面可以不改或少改。

### 6.2 推荐适配方式 A：机载端转换为 MiniQGCLinkV2.0

这是改动最小的方式。

适用场景：可以修改飞控侧、伴随计算机或协议网关程序。

开发方式：

1. 在机载端或中间网关把新飞控数据转换为 MiniQGCLinkV2.0 帧。
2. 使用当前功能字和 payload 字段布局发送到地面站 UDP 端口。
3. 地面站无需改动协议解析器，只需配置 IP 和端口。

优点：

- 前端和后端主体代码无需变化。
- 录制文件、在线分析、指令通道保持原有口径。
- 最适合工程交付和稳定运行。

缺点：

- 需要在飞控侧或网关侧实现协议转换。

### 6.3 推荐适配方式 B：在后端新增协议适配器

适用场景：不能修改飞控侧协议，地面站必须直接接收新飞控原始数据。

开发位置：

| 文件 | 需要做的事 |
| --- | --- |
| `src-python/protocol/` | 新增协议解析文件，例如 `mavlink_adapter.py`、`custom_fc_adapter.py`。 |
| `src-python/protocol/protocol_parser.py` | 在 UDP 收包后根据端口、帧头或配置选择解析器。 |
| `src-python/events/standard_event.py` | 如需要，把新消息补充到标准事件层。 |
| `src-python/recorder/data_recorder.py` | 如新增数据类型，需要补充录制逻辑和表头。 |
| `src-frontend/src/store/drone.js` | 如果前端需要展示全新字段，需要补充状态更新逻辑。 |

目标输出格式应尽量复用现有消息类型。例如一个新飞控的状态包应转换为：

```python
{
    "type": "fcs_states",
    "timestamp": 1710000000000,
    "func_code": 0x42,
    "data": {
        "states_lat": 39.0,
        "states_lon": 117.0,
        "states_height": 120.0,
        "states_phi": 0.5,
        "states_theta": -1.2,
        "states_psi": 35.0,
        "states_Vx_GS": 3.0,
        "states_Vy_GS": 0.1,
        "states_Vz_GS": -0.2
    }
}
```

前端当前主要依赖字段包括：

| 消息 | 前端常用字段 |
| --- | --- |
| `fcs_states` | `states_lat`、`states_lon`、`states_height`、姿态角、地速/垂速。 |
| `fcs_pwms` | `pwms` 或各 PWM 通道值。 |
| `fcs_datactrl` | 控制环 P/I/D、误差、指令量等。 |
| `fcs_gncbus` | GNC/SoC 相关状态。 |
| `fcs_datagcs` | 地面站回传状态、任务/模式相关字段。 |
| `planning_telemetry` | `global_path`、`local_path`、`obstacles`、当前位置、速度、状态位。 |

适配时应先保证 `fcs_states` 和 `fcs_pwms` 两类消息稳定，因为它们决定基础姿态、位置、电机输出和监控图表是否可用。

### 6.4 推荐适配方式 C：新增传输层

如果新飞控不是 UDP，而是串口、TCP 或 MAVLink，可以保留现有 WebSocket/REST/录制链路，只替换数据入口。

建议做法：

1. 抽象一个接收器接口，例如 `TelemetryReceiver`，输出统一 `dict` 消息。
2. UDP 接收器继续使用现有 `UDPHandler`。
3. 新增 `SerialReceiver`、`TcpReceiver` 或 `MavlinkReceiver`。
4. 所有接收器最终都调用类似 `on_udp_message_received(message)` 的统一入口，把数据放入后端处理队列。

这样后续的 WebSocket 推送、录制、OnlineAnalysis 转发都可以复用。

### 6.5 指令下发适配

适配其他飞控时，下行遥测对齐只是第一步。若需要从地面站控制飞控，还要适配上行指令。

当前上行入口在 `src-python/main.py` 的 `send_command_to_drone()`：

| 指令 | 当前编码函数 |
| --- | --- |
| `cmd_idx`、`cmd_mission`、`set_pids` | `encode_extu_fcs_from_dict()` + `encode_command_packet(0x40, payload)` |
| `gcs_command` | `encode_gcs_command()` + `encode_command_packet(0x70, payload)` |
| `waypoints_upload` | `encode_waypoints_upload()` + `encode_command_packet(0x70, payload)` |

如果新飞控的上行协议不同，应新增编码函数，并保持 `/api/command` 的请求结构尽量不变。例如前端仍提交：

```json
{
  "type": "cmd_idx",
  "params": {
    "cmdId": 1
  }
}
```

后端根据当前飞控类型选择不同编码器。这样前端按钮、任务面板、日志记录不需要大改。

### 6.6 适配开发建议顺序

建议按以下顺序开发和验收：

1. 只接收数据，不下发指令：确认后端能收到原始包，`/api/traffic/stats` 中 `rx_datagrams` 增长。
2. 解析基础状态：确认 `parsed_messages.by_type_total.fcs_states` 增长。
3. 前端基础显示：确认姿态、位置、高度、速度刷新。
4. 解析 PWM/控制环：确认图表和控制状态刷新。
5. 接入规划/障碍物：确认轨迹、局部路径、障碍物显示。
6. 开启录制：确认 `Log/Records/<session_id>` 有输出，CSV 字段不为空。
7. 接入上行指令：先用测试飞控或仿真环境验证，不直接用于实机风险动作。
8. 做异常测试：断网、端口占用、飞控重启、前端刷新、后端重启。

## 7. 常见部署问题

### 7.1 后端启动但没有数据

检查顺序：

1. `GET /health` 是否正常。
2. `GET /api/udp/status` 中 `connected` 是否为 `true`。
3. `GET /api/traffic/stats` 中 `rx_datagrams.packets_total` 是否增长。
4. 如果 `rx_datagrams` 增长但 `parsed_messages` 不增长，说明数据进入了 UDP 端口，但帧格式、功能字、payload 长度或校验不匹配。
5. 如果 `rx_datagrams` 不增长，检查本机 IP、端口绑定、防火墙、飞控目标地址配置。

### 7.2 前端连不上后端

检查：

1. 浏览器访问 `http://localhost:8000/health`。
2. 如果跨电脑访问，后端必须设置 `GCS_HTTP_BIND_ALL=1`。
3. 前端跨电脑部署时设置 `VITE_API_BASE_URL=http://后端IP:8000`。
4. 检查 Windows 防火墙是否允许 8000 端口。

### 7.3 UDP 端口被占用

Windows 查询端口：

```powershell
netstat -ano | findstr :30509
netstat -ano | findstr :18511
netstat -ano | findstr :18507
netstat -ano | findstr :18506
```

结束占用进程：

```powershell
taskkill /PID <进程ID> /F
```

### 7.4 Electron 打开后页面有了但后端不可用

检查：

1. 是否安装了 Python 依赖。
2. 是否存在 `src-python/.packenv/python.exe`、`.venv/Scripts/python.exe` 或系统 `python`。
3. 直接在 `src-python` 中运行 `python .\main.py`，观察报错。
4. 如果已有后端占用 8000，Electron 会复用已有后端。

### 7.5 真实飞控能收到指令但前端不刷新

常见原因：

1. 上行指令端口正确，但下行遥测目标地址没有指向地面站电脑。
2. 飞控发送到的端口不是地面站监听端口。
3. 数据协议不是当前 MiniQGCLinkV2.0 格式。
4. 帧能被接收但解析失败，可查看 `/api/traffic/stats` 的 `parser_rejections` 和 `parser_issues`。

## 8. 交付检查清单

交付给他人使用前，建议至少检查以下内容：

| 检查项 | 要求 |
| --- | --- |
| 环境 | Node.js、Python、依赖安装完成。 |
| 后端 | `http://localhost:8000/health` 正常。 |
| 前端 | `http://localhost:5173/` 正常打开。 |
| UDP | `/api/udp/status` 显示监听端口正确。 |
| 飞控链路 | `/api/traffic/stats` 收包和解析计数增长。 |
| WebSocket | 前端日志显示连接已建立。 |
| 录制 | 开始/停止录制后，`Log/Records/<session_id>` 有 CSV 和 `session_meta.json`。 |
| 指令 | 在安全测试环境确认 `/api/command` 返回 success，并由飞控侧确认收到。 |
| 跨电脑访问 | 后端设置 `GCS_HTTP_BIND_ALL=1`，防火墙放行 8000 和 UDP 端口。 |

## 9. 最小使用流程

单机开发或演示：

```powershell
cd E:\Apollo-GCS-Web
npm install
npm run dev:web
```

访问：

```text
http://localhost:5173/
```

真实飞控联调：

```powershell
cd E:\Apollo-GCS-Web\src-python
$env:GCS_LISTEN_HOST = "0.0.0.0"
$env:GCS_TARGET_IP = "192.168.16.116"
$env:GCS_TARGET_PORT = "18504"
$env:GCS_HTTP_BIND_ALL = "1"
python .\main.py
```

另开终端：

```powershell
cd E:\Apollo-GCS-Web\src-frontend
npm run dev
```

然后在浏览器访问前端，确认 WebSocket 连接、UDP 状态、实时遥测、录制功能和指令功能。
