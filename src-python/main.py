"""
Apollo-GCS Web 后端主程序（精简版）
FastAPI + WebSocket + UDP 通信服务器
"""

import sys
import os

# 将当前目录添加到 Python 路径，确保可以导入本地模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import asyncio
import logging
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any, Optional
import json
import time
import math

from protocol.protocol_parser import UDPHandler, NCLinkUDPServerProtocol
from protocol.nclink_protocol import (
    PortType
)
from config import config, Config
from websocket.websocket_manager import WebSocketManager
from recorder import RawDataRecorder
from calculator import RealTimeCalculator
from config import MappingConfig
from dsm import DSMGenerator
from recorder.csv_helper_full import (
    get_full_header, get_data_for_type
)
from replayer import Replayer

# ================================================================
# 数据模型
# ================================================================

class ConnectionConfig(BaseModel):
    """UDP连接配置"""
    protocol: str = "udp"
    listenAddress: str = "0.0.0.0"  # 监听地址（地面站本地IP）
    hostPort: int = 30509
    remoteIp: str = "127.0.0.1"      # 目标地址（飞控IP）
    commandRecvPort: int = 18504
    sendOnlyPort: int = 18506
    lidarSendPort: int = 18507
    planningSendPort: int = 18510
    planningRecvPort: int = 18511

class LogConfig(BaseModel):
    """数据记录配置"""
    autoRecord: bool = False
    logFormat: str = "csv"
    logLevel: str = "1"

class CommandRequest(BaseModel):
    """指令请求"""
    type: str
    params: Dict[str, Any] = {}

class RecordingConfig(BaseModel):
    """录制配置"""
    session_id: str = ""
    auto_start: bool = False
    base_directory: str = "data"

class DSMReportRequest(BaseModel):
    """DSM报告生成请求"""
    session_id: str
    base_directory: str = "data"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    output_format: str = "json"  # json or csv_matrix

class ReplayControlRequest(BaseModel):
    """回放控制请求"""
    action: str  # load, play, pause, seek, set_speed, stop
    file_path: Optional[str] = None
    progress_percent: Optional[float] = None
    speed: Optional[float] = None

# ================================================================
# 全局配置和日志管理
# ================================================================

# 全局连接配置
connection_config = ConnectionConfig()

# 日志管理
log_config = LogConfig()
log_file_handles = {}  # 存储打开的日志文件句柄

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gcs_backend.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 打印初始配置
config.print_config()

# 创建 FastAPI 应用
app = FastAPI(
    title="Apollo GCS Web API",
    description="无人机地面站后端API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================================================
# 全局变量
# ================================================================


# 使用统一的WebSocket管理器
manager = WebSocketManager()
udp_handler = None
udp_server_started = False

# 指令发送状态跟踪
command_send_count = 0
last_valid_cmd_idx = 0
command_send_lock = None

# PID参数缓存（用于cmd_idx指令，保持PID参数不变）
cached_pid_params = {
    'fKaPHI': 0.5, 'fKaP': 0.2, 'fKaY': 0.143, 'fIaY': 0.005,
    'fKaVy': 2.0, 'fIaVy': 0.4, 'fKaAy': 0.28,
    'fKeTHETA': 0.5, 'fKeQ': 0.2, 'fKeX': 0.201, 'fIeX': 0.01,
    'fKeVx': 2.0, 'fIeVx': 0.4, 'fKeAx': 0.55,
    'fKrR': 0.2, 'fIrR': 0.01, 'fKrAy': 0.1, 'fKrPSI': 1.0,
    'fKcH': 0.36, 'fIcH': 0.015, 'fKcHdot': 0.5, 'fIcHdot': 0.05,
    'fKcAz': 0.15, 'fIgRPM': 0.0, 'fKgRPM': 0.01, 'fScale_factor': 1.0
}

# 数据处理模块
recorder = None  # RawDataRecorder实例
calculator = RealTimeCalculator()  # 实时计算引擎
mapping_config = MappingConfig()  # 映射配置
dsm_generator = DSMGenerator(mapping_config)  # DSM生成器
replayer = None  # Replayer实例（数据回放引擎）

# 回放数据缓存（用于变量分析功能）
replay_df_cache = None

# 变量分类映射（基于 ExtY_FCS_T 结构）
VARIABLE_CATEGORIES = {
    'PWMS': ['pwm_'],
    'STATES': ['states_'],
    'DATACTRL': ['ctrl_', 'est_', 'ref_'],
    'GNCBUS': ['GNCBus_', 'pos_', 'vel_', 'euler_'],
    'AVOIFLAG': ['AvoiFlag_'],
    'DATAFUTABA': ['Tele_ftb_'],
    'DATAGCS': ['Tele_GCS_'],
    'PARAM': ['param'],
    'ESC': ['esc']
}

# 初始化指令发送锁
command_send_lock = asyncio.Lock()

# 录制状态
recording_active = False
current_session_id = None

# 回放状态
replay_active = False
current_replay_file = None

# ================================================================
# 全面的数据记录功能
# ================================================================

def save_data_to_log(category: str, message: dict):
    """
    保存数据到日志文件（支持所有数据类型）
    
    支持的数据类型：
    - fcs_states: 飞行状态数据
    - fcs_pwms: PWM电机数据
    - fcs_datactrl: 控制循环数据
    - fcs_gncbus: GN&C总线数据
    - avoiflag: 避障标志
    - fcs_esc: 电机ESC数据（包含6个电机的错误计数、转速、功率）
    - fcs_datagcs: GCS指令数据
    - fcs_datafutaba: Futaba遥控数据
    - fcs_param: 飞控参数
    """
    global log_file_handles
    
    if not log_config.autoRecord:
        return
    
    if 'telemetry' not in log_file_handles:
        return
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        telemetry_data = message.get('data', {})
        
        if log_config.logFormat == "csv":
            # CSV格式：宽表格式 - 使用csv_helper生成数据（无category列，212个数据字段）
            csv_line = get_data_for_type(category, message)
            csv_line += "\n"
            
            # 写入CSV
            log_file_handles['telemetry'].write(csv_line)
            log_file_handles['telemetry'].flush()
            
        elif log_config.logFormat == "binary":
            # Binary格式：直接写入原始JSON
            binary_data = json.dumps({
                'timestamp': timestamp,
                'category': category,
                'message': message
            }).encode('utf-8')
            log_file_handles['telemetry'].write(binary_data + b'\n')
            log_file_handles['telemetry'].flush()
            
    except Exception as e:
        logger.error(f"保存数据到日志失败 [{category}]: {e}")


# ================================================================
# 辅助函数
# ================================================================

def sample_trajectory_points(points: list, step: int = 1) -> list:
    """轨迹点采样函数
    :param points: 轨迹点列表 [Point, Point, ...]
    :param step: 采样步长
    """
    if not points:
        return []
    if step < 1:
        step = 1
    return points[::step]


# ================================================================
# UDP数据处理回调
# ================================================================

def on_udp_message_received(message: dict):
    """
    UDP数据包接收回调
    1. 将接收到的数据通过WebSocket广播到前端
    2. 实时计算KPI指标
    3. 录制数据到CSV文件（如果启用）
    4. 记录UDP接收日志
    """
    global recorder, recording_active
    
    msg_type = message.get('type', 'unknown')
    func_code = message.get('func_code', 0)
    
    # 添加调试日志：显示收到的所有消息类型
    logger.info(f"[调试] 收到UDP消息: type='{msg_type}', func_code={func_code}")
    
    # 分支1: 实时计算KPI
    kpi_result = calculator.process_packet(message)
    
    # 广播KPI结果到前端
    kpi_message = {
        'type': 'kpi_update',
        'timestamp': message.get('timestamp', int(time.time() * 1000)),
        'data': kpi_result
    }
    asyncio.create_task(manager.broadcast(kpi_message))
    
    # 分支2: 录制数据（冷流）- 统一使用RawDataRecorder
    # 检查全局录制状态
    global recorder, recording_active
    
    # 支持左侧面板"配置自动录制" -> 如果启用，尝试确保recorder已启动
    if log_config.autoRecord:
         # 如果尚未激活录制，且没有手动录制正在进行
         if not recording_active and recorder is None:
             # 初始化自动录制会话
             auto_session_id = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
             project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
             base_directory = os.path.join(project_root, 'Log', 'AutoDSM')
             
             try:
                 recorder = RawDataRecorder(auto_session_id, base_directory)
                 recorder.start_recording()
                 recording_active = True
                 current_session_id = auto_session_id
                 logger.info(f"自动录制已启动: {auto_session_id}")
                 
                 # 广播状态
                 asyncio.create_task(manager.broadcast({
                    "type": "recording_status",
                    "is_active": True,
                    "session_id": current_session_id,
                    "timestamp": int(time.time() * 1000)
                }))
             except Exception as e:
                 logger.error(f"无法启动自动录制: {e}")

    # 只要recorder处于活动状态，就记录
    if recording_active and recorder:
        recorder.record_decoded_packet(message)
    
    # 分支3: 广播原始数据到前端（默认广播）
    # 对于planning_telemetry类型，会在下面单独处理并广播包含轨迹的数据
    ws_message = {
        'type': 'udp_data',
        'timestamp': message.get('timestamp', int(time.time() * 1000)),
        'data': message
    }
    
    # 分支4: 根据消息类型处理
    if msg_type == 'fcs_states':
        data = message.get('data', {})
        logger.info(f"[UDP] 飞行状态: 位置({data.get('latitude', 0):.6f}, {data.get('longitude', 0):.6f}), 高度{data.get('altitude', 0):.1f}m")
    elif msg_type == 'planning_telemetry':
        data = message.get('data', {})
        logger.info(f"[UDP] ===== 规划遥测(0x71) =====")
        logger.info(f"[UDP] 遥测序号: {data.get('seq_id', 0)}")
        logger.info(f"[UDP] 时间戳: {data.get('timestamp', 0)}")
        logger.info(f"[UDP] 当前位置: ({data.get('current_pos_x', 0):.2f}, {data.get('current_pos_y', 0):.2f}, {data.get('current_pos_z', 0):.2f}) m")
        logger.info(f"[UDP] 当前速度: {data.get('current_vel', 0):.2f} m/s")
        logger.info(f"[UDP] 更新标志: {data.get('update_flags', 0):02X} (全局路径={bool(data.get('update_flags', 0) & 0x01)}, 局部轨迹={bool(data.get('update_flags', 0) & 0x02)}, 障碍物={bool(data.get('update_flags', 0) & 0x04)})")
        logger.info(f"[UDP] 系统状态: {data.get('status', 0)}")
        logger.info(f"[UDP] 全局路径点数: {data.get('global_path_count', 0)}")
        logger.info(f"[UDP] 局部轨迹点数: {data.get('local_traj_count', 0)}")
        logger.info(f"[UDP] 障碍物数量: {data.get('obstacle_count', 0)}")
        logger.info(f"[UDP] =======================")
        
        # 检查是否包含真实轨迹数据
        global_path_data = data.get('global_path', [])
        local_traj_data = data.get('local_path', [])
        
        if global_path_data and len(global_path_data) > 0:
            # 调试模式：不采样，发送全部点
            sampled_global_path = global_path_data
            logger.info(f"[轨迹处理] 全局路径: 原始{len(global_path_data)}点 -> 发送{len(sampled_global_path)}点")
        else:
            sampled_global_path = []
            logger.info(f"[轨迹处理] 全局路径: 无数据")
        
        if local_traj_data and len(local_traj_data) > 0:
            # 调试模式：不采样，发送全部点
            sampled_local_traj = local_traj_data
            logger.info(f"[轨迹处理] 局部轨迹: 原始{len(local_traj_data)}点 -> 发送{len(sampled_local_traj)}点")
        else:
            sampled_local_traj = []
            logger.info(f"[轨迹处理] 局部轨迹: 无数据")
        
        # 更新ws_message，添加采样后的轨迹信息
        ws_message['type'] = 'planning_telemetry'
        ws_message['data'] = {
            **message.get('data', {}),
            'global_path': sampled_global_path,
            'local_traj': sampled_local_traj
        }
        
        logger.info(f"[WebSocket] 准备发送规划遥测，包含global_path: {len(sampled_global_path)}点, local_traj: {len(sampled_local_traj)}点")
    elif msg_type == 'fcs_pwms':
        logger.info(f"[UDP] PWM数据: 功能码0x{func_code:02X}")
    elif msg_type == 'fcs_datactrl':
        logger.info(f"[UDP] 控制循环数据")
    elif msg_type == 'fcs_gncbus':
        logger.info(f"[UDP] GN&C总线数据")
    elif msg_type == 'avoiflag':
        data = message.get('data', {})
        logger.info(f"[UDP] 避障标志: 雷达={data.get('laser_radar_enabled', False)}, 避障={data.get('avoidance_flag', False)}")
    elif msg_type == 'fcs_esc':
        logger.info(f"[UDP] 电机ESC数据")
    elif msg_type == 'fcs_param':
        logger.info(f"[UDP] 飞控参数: 功能码0x{func_code:02X}")
    elif msg_type == 'lidar_obstacles':
        count = message.get('obstacle_count', 0)
        logger.info(f"[UDP] 雷达障碍物: {count}个")
        if count == 0:
            logger.debug(f"[UDP] 收到空障碍物包: {message}")
    elif msg_type == 'unknown':
        logger.warning(f"[UDP] 未知数据包: 功能码=0x{func_code:02X}")
    else:
        logger.info(f"[UDP] {msg_type} (功能码: 0x{func_code:02X})")
    
    # 广播消息到前端
    asyncio.create_task(manager.broadcast(ws_message))
    
    # 记录数据到日志文件（旧方式已弃用，统一使用 RawDataRecorder）
    # save_data_to_log(msg_type, message)


# ================================================================
# FastAPI 路由
# ================================================================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "Apollo GCS Web Backend",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "websocket_connections": manager.get_connection_count(),
        "timestamp": int(time.time())
    }

@app.websocket("/ws/drone")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点 - 前端连接接收实时数据"""
    await manager.connect(websocket)
    try:
        # 保持连接并处理消息
        while True:
            data = await websocket.receive_text()
            logger.debug(f"收到WebSocket消息: {data}")
            
            try:
                message = json.loads(data)
                await handle_client_message(message, websocket)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        manager.disconnect(websocket)

# ================================================================
# 配置管理 API
# ================================================================

@app.get("/api/config/connection")
async def get_connection_config():
    """获取连接配置"""
    return {
        "type": "connection_config",
        "data": connection_config.dict(),
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/config/connection")
async def update_connection_config(config: ConnectionConfig):
    """更新连接配置（智能判断：IP更新 vs 端口更新）"""
    global connection_config, udp_server_started, udp_handler
    
    logger.info(f"更新连接配置: {config}")
    
    # 检测配置变化类型
    # 1. 监听配置是否改变（监听地址或端口改变，需要重启UDP服务器）
    listen_config_changed = (
        connection_config.listenAddress != config.listenAddress or
        connection_config.hostPort != config.hostPort or
        connection_config.lidarSendPort != config.lidarSendPort or
        connection_config.planningRecvPort != config.planningRecvPort
    )
    
    # 2. 发送目标（IP+端口）是否改变（只需更新目标地址，不需要重启）
    target_changed = (
        connection_config.remoteIp != config.remoteIp or
        connection_config.commandRecvPort != config.commandRecvPort
    )
    
    # 更新配置对象
    connection_config = config
    
    # 场景1: 仅监听配置改变（监听地址或端口）- 需要重启UDP服务器
    if listen_config_changed and not target_changed:
        logger.info(f"场景1: 监听配置已改变，重启UDP服务器")
        logger.info(f"  监听地址: {config.listenAddress}")
        logger.info(f"  监听端口: {config.hostPort}, {config.lidarSendPort}, {config.planningRecvPort}")
        
        if udp_handler and udp_server_started:
            try:
                await udp_handler.stop_server()
                logger.info("UDP服务器已停止")
                udp_server_started = False
            except Exception as e:
                logger.error(f"停止UDP服务器失败: {e}")
        
        # 等待端口完全释放
        await asyncio.sleep(1.0)
        
        # 初始化UDP处理器（如果尚未初始化）
        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)
            logger.info("UDP处理器已初始化")
        
        try:
            ports = [
                connection_config.hostPort,
                connection_config.lidarSendPort,
                connection_config.planningRecvPort
            ]
            # 使用配置中的监听地址
            await udp_handler.start_server(host=config.listenAddress, ports=ports)
            udp_server_started = True
            logger.info(f"✓ UDP服务器已重启")
            logger.info(f"  监听地址: {config.listenAddress}")
            logger.info(f"  监听端口: {ports}")
            
            await manager.broadcast({
                "type": "config_update",
                "config_type": "connection",
                "data": config.dict(),
                "timestamp": int(time.time() * 1000)
            })
            
            return {"status": "success", "message": "端口配置已更新，UDP服务器已重启"}
        except Exception as e:
            logger.error(f"UDP服务器启动失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # 场景2: 仅目标IP/端口改变 - 只需更新发送目标
    elif target_changed and not listen_config_changed:
        logger.info(f"场景2: 仅目标地址改变，更新发送目标")
        logger.info(f"  发送目标: {connection_config.remoteIp}:{connection_config.commandRecvPort}")
        
        # 更新发送目标地址
        if udp_handler and udp_server_started:
            udp_handler.set_target(connection_config.remoteIp, connection_config.commandRecvPort)
            logger.info(f"✓ UDP发送目标已更新: {connection_config.remoteIp}:{connection_config.commandRecvPort}")
        else:
            logger.warning("UDP服务器未运行，仅保存配置")
        
        await manager.broadcast({
            "type": "config_update",
            "config_type": "connection",
            "data": config.dict(),
            "timestamp": int(time.time() * 1000)
        })
        
        return {"status": "success", "message": "配置已更新，发送目标已更改"}
    
    # 场景3: 无任何改变 - 仅保存配置
    elif not target_changed and not listen_config_changed:
        logger.info("场景3: 配置无变化，仅保存配置")
        
        await manager.broadcast({
            "type": "config_update",
            "config_type": "connection",
            "data": config.dict(),
            "timestamp": int(time.time() * 1000)
        })
        
        return {"status": "success", "message": "配置已更新"}
    
    # 场景4: 监听配置和目标都改变 - 需要重启并更新目标
    else:
        logger.info(f"场景4: 监听配置和目标地址都改变")
        
        if udp_handler and udp_server_started:
            try:
                await udp_handler.stop_server()
                logger.info("UDP服务器已停止")
                udp_server_started = False
            except Exception as e:
                logger.error(f"停止UDP服务器失败: {e}")
        
        # 等待端口完全释放
        await asyncio.sleep(1.0)
        
        # 初始化UDP处理器（如果尚未初始化）
        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)
            logger.info("UDP处理器已初始化")
        
        try:
            ports = [
                connection_config.hostPort,
                connection_config.lidarSendPort,
                connection_config.planningRecvPort
            ]
            # 使用配置中的监听地址
            await udp_handler.start_server(
                host=config.listenAddress,
                ports=ports,
                target_host=connection_config.remoteIp,
                target_port=connection_config.commandRecvPort
            )
            udp_server_started = True
            
            logger.info(f"✓ UDP服务器已重启")
            logger.info(f"  监听地址: {config.listenAddress}")
            logger.info(f"  监听端口: {ports}")
            logger.info(f"  发送目标: {connection_config.remoteIp}:{connection_config.commandRecvPort}")
            
            await manager.broadcast({
                "type": "config_update",
                "config_type": "connection",
                "data": config.dict(),
                "timestamp": int(time.time() * 1000)
            })
            
            return {"status": "success", "message": "配置已更新，UDP服务器已重启"}
        except Exception as e:
            logger.error(f"UDP服务器启动失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/udp/start")
async def start_udp_server():
    """启动UDP服务器"""
    global udp_handler, udp_server_started, connection_config
    
    try:
        # 如果已经启动，先停止
        if udp_server_started and udp_handler:
            logger.info("UDP服务器已在运行，先停止...")
            await udp_handler.stop_server()
            udp_server_started = False
        
        # 初始化UDP处理器（如果尚未初始化）
        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)
        
        # 启动UDP服务器
        ports = [
            connection_config.hostPort,
            connection_config.lidarSendPort,
            connection_config.planningRecvPort
        ]
        
        await udp_handler.start_server(host="0.0.0.0", ports=ports)
        udp_server_started = True
        
        logger.info(f"UDP服务器已启动: {ports}")
        logger.info(f"发送目标: {connection_config.remoteIp}:{connection_config.commandRecvPort}")
        
        await manager.broadcast({
            "type": "udp_status_change",
            "status": "connected",
            "config": connection_config.dict(),
            "timestamp": int(time.time() * 1000)
        })
        
        return {
            "status": "success",
            "message": "UDP服务器已启动",
            "data": {
                "ports": ports,
                "target": f"{connection_config.remoteIp}:{connection_config.commandRecvPort}"
            }
        }
    except Exception as e:
        logger.error(f"启动UDP服务器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/udp/stop")
async def stop_udp_server():
    """停止UDP服务器"""
    global udp_handler, udp_server_started
    
    try:
        if udp_handler and udp_server_started:
            await udp_handler.stop_server()
            udp_server_started = False
            
            logger.info("UDP服务器已停止")
            
            await manager.broadcast({
                "type": "udp_status_change",
                "status": "disconnected",
                "timestamp": int(time.time() * 1000)
            })
            
            return {
                "status": "success",
                "message": "UDP服务器已停止"
            }
        else:
            return {
                "status": "success",
                "message": "UDP服务器未运行"
            }
    except Exception as e:
        logger.error(f"停止UDP服务器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/udp/status")
async def get_udp_status():
    """获取UDP连接状态"""
    # 实际检查UDP服务器是否在运行（而不仅仅是标志位）
    is_actually_running = False
    if udp_handler:
        is_actually_running = udp_handler.is_running()
    
    # 更新状态标志以匹配实际状态
    global udp_server_started
    udp_server_started = is_actually_running
    
    return {
        "status": "success",
        "data": {
            "connected": is_actually_running,
            "config": connection_config.dict() if connection_config else None,
            "timestamp": int(time.time() * 1000)
        }
    }

@app.get("/api/config/log")
async def get_log_config():
    """获取日志配置"""
    return {
        "type": "log_config",
        "data": log_config.dict(),
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/config/log")
async def update_log_config(config: LogConfig):
    """更新日志配置"""
    global log_config, log_file_handles
    
    logger.info(f"更新日志配置: {config}")
    
    # 关闭现有日志文件
    for file_handle in log_file_handles.values():
        try:
            file_handle.close()
        except Exception as e:
            logger.error(f"关闭日志文件失败: {e}")
    log_file_handles.clear()
    
    log_config = config
    
    # 创建 Log 目录并创建新日志文件
    if config.autoRecord:
        # 获取项目根目录 (Apollo-GCS-Web)
        # __file__ 是 src-python/main.py -> dirname 是 src-python -> dirname 是 Apollo-GCS-Web
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(project_root, 'Log')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"drone_log_{timestamp_str}.{config.logFormat}"
        log_path = os.path.join(log_dir, log_filename)
        
        try:
            if config.logFormat == "csv":
                log_file_handles['telemetry'] = open(log_path, 'a', newline='', encoding='utf-8')
                # 写入CSV表头 - 宽表格式（212个字段，无category列）
                if os.path.getsize(log_path) == 0:
                    header = get_full_header() + "\n"
                    log_file_handles['telemetry'].write(header)
            else:
                log_file_handles['telemetry'] = open(log_path, 'ab')
            
            logger.info(f"日志文件已创建: {log_path}")
        except Exception as e:
            logger.error(f"创建日志文件失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    await manager.broadcast({
        "type": "config_update",
        "config_type": "log",
        "data": config.dict(),
        "timestamp": int(time.time() * 1000)
    })
    
    return {"status": "success", "message": "日志配置已更新"}

@app.post("/api/log/save")
async def save_log_entry(data: dict):
    """保存单条日志记录（前端调用）"""
    if not log_config.autoRecord:
        return {"status": "skipped", "message": "自动记录未启用"}
    
    try:
        category = data.get('category', 'unknown')
        save_data_to_log(category, data.get('message', {}))
        return {"status": "success", "message": "日志已保存"}
    except Exception as e:
        logger.error(f"保存日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# 指令发送 API
# ================================================================

@app.post("/api/command")
async def send_command_to_drone(request: CommandRequest):
    """发送指令到飞控（实现6次连续发送机制）"""
    try:
        command_type = request.type
        params = request.params
        
        logger.info(f"收到指令: {command_type}, 参数: {params}")
        
        packet = None
        target_host = None
        target_port = None
        
        if command_type == 'cmd_idx':
            cmd_id = params.get('cmdId', 0)
            
            async with command_send_lock:
                global command_send_count, last_valid_cmd_idx
                
                if 1 <= cmd_id <= 25:  # 有效指令ID范围
                    last_valid_cmd_idx = cmd_id
                    command_send_count = 0
                    
                    # 构建6次连续发送的数据包（使用缓存的PID参数）
                    payload = encode_extu_fcs_from_dict(
                        cached_pid_params,
                        cmd_idx=cmd_id,
                        cmd_mission=0,
                        cmd_mission_val=0.0
                    )
                    packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
                    
                    # 选择目标端口
                    target_host = connection_config.remoteIp
                    target_port = connection_config.commandRecvPort
                    
                    # 连续发送6次
                    if packet and udp_handler:
                        for i in range(6):
                            udp_handler.send_data(packet, target_host, target_port)
                            if i < 5:  # 前5次发送后等待100ms
                                await asyncio.sleep(0.1)
                        
                        # 第7次重置指令
                        payload_zero = encode_extu_fcs_from_dict(
                            cached_pid_params,
                            cmd_idx=0,
                            cmd_mission=0,
                            cmd_mission_val=0.0
                        )
                        packet_zero = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload_zero)
                        udp_handler.send_data(packet_zero, target_host, target_port)
                        
                        return {
                            "type": "command_response",
                            "command": command_type,
                            "status": "success",
                            "message": f"指令{cmd_id}已连续发送6次，第7次已重置为0",
                            "timestamp": int(time.time() * 1000)
                        }
                else:
                    # 无效指令（如0），只发送1次
                    payload = encode_extu_fcs_from_dict(
                        cached_pid_params,
                        cmd_idx=cmd_id,
                        cmd_mission=0,
                        cmd_mission_val=0.0
                    )
                    packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
        
        elif command_type == 'cmd_mission':
            # 前端现在使用 cmd_mission 作为参数名（区分 CmdIdx 和 CmdMission）
            cmd_mission_id = params.get('cmd_mission', 0)
            cmd_mission_val = params.get('value', 0.0)
            
            # 编码116字节payload（26个PID参数 + 3个指令字段）
            payload = encode_extu_fcs_from_dict(
                cached_pid_params,
                cmd_idx=0,
                cmd_mission=cmd_mission_id,
                cmd_mission_val=cmd_mission_val
            )
            
            packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
        
        
        elif command_type == 'gcs_command':
            seq_id = params.get('seqId', 0)
            target_x = params.get('targetX', 0.0)
            target_y = params.get('targetY', 0.0)
            target_z = params.get('targetZ', 0.0)
            cruise_speed = params.get('cruiseSpeed', 10.0)
            enable = params.get('enable', 1)
            cmd_id = params.get('cmdId', 0)
            
            payload = encode_gcs_command(seq_id, target_x, target_y, target_z, cruise_speed, enable, cmd_id)
            packet = encode_command_packet(NCLINK_GCS_COMMAND, payload)
            logger.info(f"发送GCS航点: ({target_x}, {target_y}, {target_z}), 速度={cruise_speed}")
        
        elif command_type == 'waypoints_upload':
            waypoints = params.get('waypoints', [])
            cruise_speed = params.get('cruiseSpeed', 10.0)
            payload = encode_waypoints_upload(waypoints, cruise_speed)
            packet = encode_command_packet(NCLINK_GCS_COMMAND, payload)
            logger.info(f"上传航点: {len(waypoints)}个")
        
        else:
            return {
                "type": "command_response",
                "command": command_type,
                "status": "error",
                "message": f"未知指令: {command_type}",
                "timestamp": int(time.time() * 1000)
            }
        
        # 发送数据包
        if packet and udp_handler:
            # 根据指令类型选择目标端口
            # cmd_idx和cmd_mission发送到飞控指令端口(18504)
            # gcs_command和waypoints_upload发送到规划端口(18510)
            if command_type in ['cmd_idx', 'cmd_mission']:
                target_host = connection_config.remoteIp
                target_port = connection_config.commandRecvPort  # 飞控指令接收端口
            elif command_type in ['gcs_command', 'waypoints_upload']:
                target_host = connection_config.remoteIp
                target_port = connection_config.planningSendPort  # 规划指令端口
            else:
                # 其他指令也发送到飞控指令端口
                target_host = connection_config.remoteIp
                target_port = connection_config.commandRecvPort
            
            logger.info(f"发送目标: {target_host}:{target_port}")
            udp_handler.send_data(packet, target_host, target_port)
            
            return {
                "type": "command_response",
                "command": command_type,
                "status": "success",
                "message": "指令已发送",
                "timestamp": int(time.time() * 1000)
            }
        else:
            return {
                "type": "command_response",
                "command": command_type,
                "status": "error",
                "message": "UDP服务器未启动",
                "timestamp": int(time.time() * 1000)
            }
            
    except Exception as e:
        logger.error(f"发送指令失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def send_pid_params_to_drone(pids_data: dict) -> dict:
    """发送PID参数到飞控（处理set_pids指令）

Args:
    pids_data: dict, 包含26个PID参数的字典

Returns:
    dict: 响应结果
"""
    global cached_pid_params
    
    try:
        logger.info(f"收到set_pids指令，参数数量: {len(pids_data)}")
        
        # 更新全局PID参数缓存
        cached_pid_params.update(pids_data)
        logger.info(f"PID参数缓存已更新")
        
        # 编码payload（116字节），使用新函数
        payload = encode_extu_fcs_from_dict(
            cached_pid_params,
            cmd_idx=0,
            cmd_mission=0,
            cmd_mission_val=0.0
        )
        logger.info(f"PID参数编码完成: {len(payload)}字节")
        
        # 使用encode_command_packet创建完整的NCLink帧
        frame_packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
        
        # 发送到飞控
        target_host = connection_config.remoteIp
        target_port = connection_config.commandRecvPort
        
        if udp_handler:
            udp_handler.send_data(frame_packet, target_host, target_port)
            logger.info(f"PID参数已发送到 {target_host}:{target_port}")
            
            return {
                "type": "command_response",
                "command": "set_pids",
                "status": "success",
                "message": f"PID参数已发送（共26个参数）",
                "timestamp": int(time.time() * 1000)
            }
        else:
            return {
                "type": "command_response",
                "command": "set_pids",
                "status": "error",
                "message": "UDP服务器未启动",
                "timestamp": int(time.time() * 1000)
            }
            
    except Exception as e:
        logger.error(f"发送PID参数失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "type": "command_response",
            "command": "set_pids",
            "status": "error",
            "message": f"发送失败: {str(e)}",
            "timestamp": int(time.time() * 1000)
        }

async def handle_client_message(message: dict, websocket: WebSocket):
    """处理WebSocket客户端消息"""
    global recording_active, current_session_id, recorder, cached_pid_params, replayer, replay_active, current_replay_file, replay_df_cache
    
    msg_type = message.get('type')
    
    if msg_type == 'command':
        # 前端发送的格式：{"type":"command","command":"set_pids","params":{...}}
        # 所以处理方式：
        # 1. 前端发送set_pids指令 -> 后端调用send_pid_params_to_drone() -> 发送到飞控模拟器
        # 2. 前端发送cmd_idx/cmd_mission指令 -> 后端只返回确认不处理
        command = message.get('command')
        params = message.get('params', {})
        
        # 处理set_pids指令（通过WebSocket发送）
        if command == 'set_pids':
            # 更新全局PID参数缓存
            cached_pid_params.update(params)
            logger.info(f"PID参数已更新（通过WebSocket）: {len(params)}个")
            
            # 发送到飞控模拟器
            result = await send_pid_params_to_drone(params)
            await websocket.send_json(result)
        elif command:
            # 其他指令（cmd_idx、cmd_mission等）返回确认即可
            # 这些指令实际通过REST API的/api/command端点发送到飞控
            await websocket.send_json({
                "type": "command_response",
                "command": command,
                "status": "success",
                "message": "指令确认",
                "timestamp": int(time.time() * 1000)
            })

    elif msg_type == 'recording':
        # 处理录制控制消息 (Start/Stop)
        action = message.get('action')
        
        try:
            if action == 'start':
                if not recording_active:
                    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # 确定日志目录: Apollo-GCS-Web/Log/DSM
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    base_directory = os.path.join(project_root, 'Log', 'DSM')
                    
                    recorder = RawDataRecorder(session_id, base_directory)
                    recorder.start_recording()
                    
                    recording_active = True
                    current_session_id = session_id
                    
                    await manager.broadcast({
                        "type": "recording_status",
                        "is_active": True,
                        "session_id": current_session_id,
                        "timestamp": int(time.time() * 1000)
                    })
                    logger.info(f"WebSocket启动录制: {current_session_id}")
                    
            elif action == 'stop':
                if recording_active and recorder:
                    session_info = recorder.get_session_info()
                    recorder.stop_recording()
                    
                    last_session_id = current_session_id
                    recording_active = False
                    current_session_id = None
                    
                    await manager.broadcast({
                        "type": "recording_status",
                        "is_active": False,
                        "session_id": last_session_id,
                        "session_info": session_info,
                        "timestamp": int(time.time() * 1000)
                    })
                    logger.info(f"WebSocket停止录制: {last_session_id}")
            
        except Exception as e:
            logger.error(f"WebSocket录制控制失败: {e}")
    
    elif msg_type == 'get_config':
        config_type = message.get('data', {}).get('config_type', 'all')
        
        if config_type in ['connection', 'all']:
            await websocket.send_json({
                "type": "config_response",
                "config_type": "connection",
                "data": connection_config.dict(),
                "timestamp": int(time.time() * 1000)
            })
        
        if config_type in ['log', 'all']:
            await websocket.send_json({
                "type": "config_response",
                "config_type": "log",
                "data": log_config.dict(),
                "timestamp": int(time.time() * 1000)
            })


    elif msg_type == 'replay':
        # 处理回放控制消息
        action = message.get('action', '')
        params = message.get('params', {})
        
        global replayer, replay_active, current_replay_file, replay_df_cache
        
        try:
            if action == 'load':
                # 加载回放文件
                file_path = params.get('file_path')
                if replayer is None:
                    replayer = Replayer(manager.broadcast)
                
                total_time = replayer.load_file(file_path)
                current_replay_file = file_path
                replay_active = True
                
                # 缓存 DataFrame 供变量分析使用
                replay_df_cache = replayer.df
                
                # 发送系统模式切换通知
                await manager.broadcast({
                    "type": "system_mode_change",
                    "mode": "REPLAY",
                    "timestamp": int(time.time() * 1000)
                })
                
                await websocket.send_json({
                    "type": "replay_response",
                    "action": "load",
                    "status": "success",
                    "total_time": total_time,
                    "timestamp": int(time.time() * 1000)
                })
            
            elif action == 'play':
                # 开始播放
                if replayer:
                    replayer.play()
                    await replayer.start()
                    
                    await websocket.send_json({
                        "type": "replay_response",
                        "action": "play",
                        "status": "success",
                        "timestamp": int(time.time() * 1000)
                    })
            
            elif action == 'pause':
                # 暂停播放
                if replayer:
                    replayer.pause()
                    
                    await websocket.send_json({
                        "type": "replay_response",
                        "action": "pause",
                        "status": "success",
                        "timestamp": int(time.time() * 1000)
                    })
            
            elif action == 'seek':
                # 跳转
                progress_percent = params.get('progress_percent', 0)
                if replayer:
                    replayer.seek(progress_percent)
                    
                    await websocket.send_json({
                        "type": "replay_response",
                        "action": "seek",
                        "status": "success",
                        "progress": progress_percent,
                        "timestamp": int(time.time() * 1000)
                    })
            
            elif action == 'set_speed':
                # 设置播放速度
                speed = params.get('speed', 1.0)
                if replayer:
                    replayer.set_speed(speed)
                    
                    await websocket.send_json({
                        "type": "replay_response",
                        "action": "set_speed",
                        "status": "success",
                        "speed": speed,
                        "timestamp": int(time.time() * 1000)
                    })
            
            elif action == 'stop':
                # 停止回放
                if replayer:
                    await replayer.stop()
                    replay_active = False
                    current_replay_file = None
                    
                    # 发送系统模式切换通知
                    await manager.broadcast({
                        "type": "system_mode_change",
                        "mode": "REALTIME",
                        "timestamp": int(time.time() * 1000)
                    })
                    
                    await websocket.send_json({
                        "type": "replay_response",
                        "action": "stop",
                        "status": "success",
                        "timestamp": int(time.time() * 1000)
                    })
            
            else:
                await websocket.send_json({
                    "type": "replay_response",
                    "action": action,
                    "status": "error",
                    "message": f"未知回放操作: {action}",
                    "timestamp": int(time.time() * 1000)
                })
        
        except Exception as e:
            logger.error(f"处理回放请求失败: {e}")
            await websocket.send_json({
                "type": "replay_response",
                "action": action,
                "status": "error",
                "message": str(e),
                "timestamp": int(time.time() * 1000)
            })

# ================================================================
# 录制控制 API
# ================================================================

# ================================================================
# 回放控制 API
# ================================================================

@app.get("/api/replay/files")
async def get_replay_files():
    """获取所有可用的回放文件列表"""
    global replayer
    
    if replayer is None:
        replayer = Replayer(manager.broadcast)
    
    files = replayer.get_data_list()
    
    # 格式化文件信息
    file_list = []
    for file_info in files:
        file_list.append({
            "name": file_info['name'],
            "path": file_info['path'],
            "size": file_info['size'],
            "date": datetime.fromtimestamp(file_info['date']).strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return {
        "type": "replay_files",
        "files": file_list,
        "count": len(file_list),
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/replay/upload")
async def upload_replay_file(file: UploadFile = File(...)):
    """上传回放文件"""
    global replayer, replay_df_cache, replay_active, current_replay_file
    
    try:
        # 确保 Log 目录存在
        log_dir = 'Log'
        os.makedirs(log_dir, exist_ok=True)
        
        # 保存上传的文件
        file_path = os.path.join(log_dir, file.filename)
        
        # 写入文件
        with open(file_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"回放文件已上传: {file_path}")
        
        return {
            "status": "success",
            "message": "文件上传成功",
            "file_path": file_path,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"上传回放文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/replay/status")
async def get_replay_status():
    """获取当前回放状态"""
    global replayer, replay_active, current_replay_file
    
    if replayer:
        status = replayer.get_status()
        status['replay_active'] = replay_active
        status['current_file'] = current_replay_file
    else:
        status = {
            'is_loaded': False,
            'is_playing': False,
            'replay_active': False,
            'current_file': None,
            'current_idx': 0,
            'total_rows': 0,
            'total_time': 0.0,
            'speed': 1.0,
            'progress': 0.0,
            'current_time': 0.0
        }
    
    return {
        "type": "replay_status",
        "status": status,
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/replay/control")
async def replay_control(request: ReplayControlRequest):
    """回放控制接口"""
    global replayer, replay_df_cache, replay_active, current_replay_file
    
    try:
        action = request.action
        
        if action == 'load':
            # 加载回放文件
            if not request.file_path:
                raise HTTPException(status_code=400, detail="未指定文件路径")
            
            if replayer is None:
                replayer = Replayer(manager.broadcast)
            
            total_time = replayer.load_file(request.file_path)
            current_replay_file = request.file_path
            replay_active = True
            
            # 重要：缓存 DataFrame 供变量分析使用
            replay_df_cache = replayer.df
            logger.info(f"[REST API] 回放数据已缓存: {len(replayer.df)} 行数据")
            
            # 广播系统模式切换
            await manager.broadcast({
                "type": "system_mode_change",
                "mode": "REPLAY",
                "timestamp": int(time.time() * 1000)
            })
            
            return {
                "type": "replay_response",
                "action": "load",
                "status": "success",
                "total_time": total_time,
                "timestamp": int(time.time() * 1000)
            }
        
        elif action == 'play':
            # 开始播放
            if replayer:
                replayer.play()
                await replayer.start()
                
                return {
                    "type": "replay_response",
                    "action": "play",
                    "status": "success",
                    "timestamp": int(time.time() * 1000)
                }
        
        elif action == 'pause':
            # 暂停播放
            if replayer:
                replayer.pause()
                
                return {
                    "type": "replay_response",
                    "action": "pause",
                    "status": "success",
                    "timestamp": int(time.time() * 1000)
                }
        
        elif action == 'seek':
            # 跳转
            if request.progress_percent is None:
                raise HTTPException(status_code=400, detail="未指定进度百分比")
            
            if replayer:
                replayer.seek(request.progress_percent)
                
                return {
                    "type": "replay_response",
                    "action": "seek",
                    "status": "success",
                    "progress": request.progress_percent,
                    "timestamp": int(time.time() * 1000)
                }
        
        elif action == 'set_speed':
            # 设置播放速度
            if request.speed is None:
                raise HTTPException(status_code=400, detail="未指定播放速度")
            
            if replayer:
                replayer.set_speed(request.speed)
                
                return {
                    "type": "replay_response",
                    "action": "set_speed",
                    "status": "success",
                    "speed": request.speed,
                    "timestamp": int(time.time() * 1000)
                }
        
        elif action == 'stop':
            # 停止回放
            if replayer:
                await replayer.stop()
                replay_active = False
                current_replay_file = None
                
                # 广播系统模式切换
                await manager.broadcast({
                    "type": "system_mode_change",
                    "mode": "REALTIME",
                    "timestamp": int(time.time() * 1000)
                })
                
                return {
                    "type": "replay_response",
                    "action": "stop",
                    "status": "success",
                    "timestamp": int(time.time() * 1000)
                }
        
        else:
            raise HTTPException(status_code=400, detail=f"未知操作: {action}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"回放控制失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recording/status")
async def get_recording_status():
    """获取当前录制状态"""
    global recording_active, current_session_id, recorder
    
    session_info = None
    if recorder and recording_active:
        session_info = recorder.get_session_info()
    
    return {
        "type": "recording_status",
        "is_active": recording_active,
        "session_id": current_session_id,
        "session_info": session_info,
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/recording/start")
async def start_recording(config: RecordingConfig):
    """开始数据录制"""
    global recording_active, current_session_id, recorder
    
    if recording_active:
        logger.warning("录制已在进行中")
        return {
            "type": "recording_response",
            "status": "error",
            "message": "录制已在进行中",
            "timestamp": int(time.time() * 1000)
        }
    
    try:
        # 生成会话ID（如果未提供）
        if not config.session_id:
            config.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建录制器
        recorder = RawDataRecorder(config.session_id, config.base_directory)
        recorder.start_recording()
        
        recording_active = True
        current_session_id = config.session_id
        
        # 广播状态更新
        await manager.broadcast({
            "type": "recording_status",
            "is_active": True,
            "session_id": current_session_id,
            "timestamp": int(time.time() * 1000)
        })
        
        logger.info(f"开始录制: {current_session_id}")
        
        return {
            "type": "recording_response",
            "status": "success",
            "message": "录制已开始",
            "session_id": current_session_id,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"开始录制失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recording/stop")
async def stop_recording():
    """停止数据录制"""
    global recording_active, current_session_id, recorder
    
    if not recording_active:
        return {
            "type": "recording_response",
            "status": "error",
            "message": "录制未开始",
            "timestamp": int(time.time() * 1000)
        }
    
    try:
        if recorder:
            session_info = recorder.get_session_info()
            recorder.stop_recording()
        
        recording_active = False
        session_id = current_session_id
        current_session_id = None
        
        # 广播状态更新
        await manager.broadcast({
            "type": "recording_status",
            "is_active": False,
            "session_id": session_id,
            "session_info": session_info,
            "timestamp": int(time.time() * 1000)
        })
        
        logger.info(f"录制已停止: {session_id}")
        
        return {
            "type": "recording_response",
            "status": "success",
            "message": "录制已停止",
            "session_id": session_id,
            "session_info": session_info,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"停止录制失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recording/sessions")
async def list_sessions(base_directory: str = "data"):
    """列出所有录制会话"""
    try:
        if not os.path.exists(base_directory):
            return {
                "type": "sessions_list",
                "sessions": [],
                "timestamp": int(time.time() * 1000)
            }
        
        sessions = []
        for session_id in os.listdir(base_directory):
            session_path = os.path.join(base_directory, session_id)
            if os.path.isdir(session_path):
                # 统计文件数量和大小
                file_count = len([f for f in os.listdir(session_path) if os.path.isfile(os.path.join(session_path, f))])
                
                sessions.append({
                    "session_id": session_id,
                    "file_count": file_count,
                    "path": session_path
                })
        
        return {
            "type": "sessions_list",
            "sessions": sorted(sessions, key=lambda x: x['session_id'], reverse=True),
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"列出会话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# DSM报告生成 API
# ================================================================

@app.post("/api/dsm/generate")
async def generate_dsm_report(request: DSMReportRequest):
    """生成DSM分析报告"""
    try:
        logger.info(f"开始生成DSM报告: {request.session_id}")
        
        # 生成DSM报告
        report = dsm_generator.generate_dsm_report(
            session_id=request.session_id,
            base_directory=request.base_directory,
            start_time=request.start_time,
            end_time=request.end_time,
            output_format=request.output_format
        )
        
        # 广播通知
        await manager.broadcast({
            "type": "dsm_report_generated",
            "session_id": request.session_id,
            "output_path": report.get("output_path"),
            "timestamp": int(time.time() * 1000)
        })
        
        logger.info(f"DSM报告生成成功: {report.get('output_path')}")
        
        return {
            "type": "dsm_report_response",
            "status": "success",
            "message": "DSM报告生成成功",
            "report": report,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"生成DSM报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dsm/config")
async def get_dsm_config():
    """获取DSM映射配置"""
    return {
        "type": "dsm_config",
        "config": mapping_config.to_dict(),
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/dsm/config")
async def update_dsm_config(config_data: Dict[str, Any]):
    """更新DSM映射配置"""
    try:
        mapping_config.save_config(config_data)
        
        # 重新创建DSM生成器以应用新配置
        global dsm_generator
        dsm_generator = DSMGenerator(mapping_config)
        
        # 广播配置更新
        await manager.broadcast({
            "type": "dsm_config_updated",
            "config": mapping_config.to_dict(),
            "timestamp": int(time.time() * 1000)
        })
        
        logger.info("DSM映射配置已更新")
        
        return {
            "type": "dsm_config_response",
            "status": "success",
            "message": "DSM映射配置已更新",
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"更新DSM配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dsm/export/{session_id}")
async def download_dsm_report(session_id: str, format: str = "json"):
    """下载DSM报告文件"""
    try:
        base_dir = "data"
        session_dir = os.path.join(base_dir, session_id)
        
        if not os.path.exists(session_dir):
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 查找DSM报告文件
        report_files = [f for f in os.listdir(session_dir) if f.startswith("dsm_")]
        
        if not report_files:
            raise HTTPException(status_code=404, detail="未找到DSM报告文件")
        
        # 返回最新的报告文件
        report_file = sorted(report_files)[-1]
        file_path = os.path.join(session_dir, report_file)
        
        return FileResponse(
            path=file_path,
            filename=report_file,
            media_type='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"下载DSM报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================
# 回放变量分析 API
# ================================================================

@app.get("/api/replay/headers")
async def get_replay_headers():
    """获取回放数据的所有列名（变量列表）"""
    import pandas as pd
    global replay_df_cache, replay_active, current_replay_file
    
    if replay_df_cache is None:
        raise HTTPException(status_code=400, detail="未加载回放文件，先加载 CSV 文件")
    
    try:
        # 获取所有列名
        columns = list(replay_df_cache.columns)
        
        # 按照变量分类组织
        categorized_vars = {}
        for category, prefixes in VARIABLE_CATEGORIES.items():
            vars_in_category = []
            for prefix in prefixes:
                vars_in_category.extend([col for col in columns if col.startswith(prefix)])
            if vars_in_category:
                categorized_vars[category] = vars_in_category
        
        return {
            "status": "success",
            "file": current_replay_file,
            "total_variables": len(columns),
            "categories": categorized_vars,
            "all_variables": columns,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"获取回放变量列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/replay/series")
async def get_replay_series_data(request: dict):
    """获取选定变量的数据序列（用于图表绘制）"""
    import pandas as pd
    import numpy as np
    global replay_df_cache
    
    if replay_df_cache is None:
        raise HTTPException(status_code=400, detail="未加载回放文件")
    
    try:
        variables = request.get('variables', [])  # 选定的变量列表
        max_points = request.get('max_points', 2000)  # 最大数据点数（降采样）
        
        if not variables:
            raise HTTPException(status_code=400, detail="未选择任何变量")
        
        logger.info(f"请求变量数据: {len(variables)} 个变量，最大点数: {max_points}")
        
        # 获取时间轴
        if 'rel_time' in replay_df_cache.columns:
            time_axis = replay_df_cache['rel_time'].values.astype(float)
        elif 'timestamp' in replay_df_cache.columns:
            time_axis = replay_df_cache['timestamp'].values
        else:
            time_axis = np.arange(len(replay_df_cache))
        
        # 获取每个变量的数据
        series_data = {}
        for var in variables:
            if var in replay_df_cache.columns:
                # 处理 NaN 值
                data = replay_df_cache[var].values
                # 将 NaN 替换为 0
                data = np.nan_to_num(data, nan=0.0)
                series_data[var] = data.tolist()
        
        # 数据降采样（如果数据点太多）
        total_points = len(time_axis)
        if total_points > max_points:
            # 计算采样步长
            step = total_points // max_points
            indices = np.arange(0, total_points, step)
            
            # 降采样
            time_axis_sampled = time_axis[indices].tolist()
            
            for var in series_data:
                series_data[var] = [series_data[var][i] for i in indices]
        else:
            time_axis_sampled = time_axis.tolist()
        
        logger.info(f"返回数据: 时间轴 {len(time_axis_sampled)} 点, 变量 {len(variables)} 个")
        
        return {
            "status": "success",
            "time_axis": time_axis_sampled,
            "series_data": series_data,
            "total_points": total_points,
            "sampled_points": len(time_axis_sampled),
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"获取变量序列数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# 应用启动和关闭事件
# ================================================================

@app.on_event("startup")
async def startup_event():
    """应用启动"""
    global command_send_lock, udp_handler, udp_server_started
    
    logger.info("=" * 60)
    logger.info("Apollo GCS Web 后端启动")
    logger.info("=" * 60)
    
    # 初始化指令发送状态
    command_send_lock = asyncio.Lock()
    logger.info("指令发送锁已初始化（支持6次连续发送机制）")
    logger.info("=" * 60)
    
    # 自动启动UDP服务器
    try:
        logger.info("正在自动启动UDP服务器...")
        
        # 初始化UDP处理器（如果尚未初始化）
        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)
            logger.info("UDP处理器已初始化")
        
        # 启动UDP服务器，监听三个端口
        ports = [
            connection_config.hostPort,
            connection_config.lidarSendPort,
            connection_config.planningRecvPort
        ]
        
        await udp_handler.start_server(host=connection_config.listenAddress, ports=ports)
        udp_server_started = True
        
        logger.info("✓ UDP服务器已自动启动")
        logger.info(f"  监听地址: {connection_config.listenAddress}")
        logger.info(f"  监听端口: {ports}")
        logger.info(f"  发送目标: {connection_config.remoteIp}:{connection_config.commandRecvPort}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"✗ UDP服务器自动启动失败: {e}")
        logger.warning("UDP服务器未启动，请手动调用 POST /api/udp/start 启动")
        logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭"""
    global udp_server_started
    logger.info("Apollo GCS Web 后端关闭中...")
    
    # 关闭日志文件
    for file_handle in log_file_handles.values():
        try:
            file_handle.close()
        except Exception as e:
            logger.error(f"关闭日志文件失败: {e}")
    log_file_handles.clear()
    
    # 关闭UDP服务器
    if udp_handler:
        await udp_handler.stop_server()
        udp_server_started = False
    
    logger.info("GCS Web 后端已关闭")

# ================================================================
# 主程序入口
# ================================================================

if __name__ == '__main__':
    import uvicorn
    
    print("""
╔══════════════════════════════════════════════════╗
║          GCS Web Backend v1.0.0          ║
║    无人机地面站 - WebSocket + UDP 服务器        ║
╚══════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )