"""
Apollo-GCS Web 后端主程序（核心通信版）
仅保留 UDP / WebSocket / 录制 / 指令 / 配置 功能。
"""

import asyncio
import ipaddress
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


def _configure_console_encoding() -> None:
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            try:
                reconfigure(encoding='utf-8', errors='backslashreplace')
            except Exception:
                pass


_configure_console_encoding()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_PYTHON_ROOT = os.getenv('APOLLO_GCS_PYTHON_ROOT') or SCRIPT_DIR
PROJECT_ROOT = os.getenv('APOLLO_GCS_PROJECT_ROOT') or os.path.dirname(RESOURCE_PYTHON_ROOT)
DATA_ROOT = os.getenv('APOLLO_GCS_DATA_ROOT') or PROJECT_ROOT

os.makedirs(DATA_ROOT, exist_ok=True)

for candidate_path in (SCRIPT_DIR, RESOURCE_PYTHON_ROOT):
    if candidate_path and candidate_path not in sys.path:
        sys.path.insert(0, candidate_path)

from config import config
from protocol.nclink_protocol import (
    NCLINK_GCS_COMMAND,
    NCLINK_SEND_EXTU_FCS,
    encode_command_packet,
    encode_extu_fcs_from_dict,
    encode_gcs_command,
    encode_waypoints_upload,
)
from protocol.protocol_parser import UDPHandler
from recorder import RawDataRecorder
from recorder.csv_helper_full import get_data_for_type, get_full_header
from websocket.websocket_manager import WebSocketManager


class ConnectionConfig(BaseModel):
    protocol: str = 'udp'
    listenAddress: str = '192.168.16.13'
    hostPort: int = 30509
    remoteIp: str = '192.168.16.116'
    commandRecvPort: int = 18504
    sendOnlyPort: int = 18506
    lidarSendPort: int = 18507
    planningSendPort: int = 18510
    planningRecvPort: int = 18511


class LogConfig(BaseModel):
    autoRecord: bool = False
    logFormat: str = 'csv'
    logLevel: str = '1'


class CommandRequest(BaseModel):
    type: str
    params: Dict[str, Any] = {}


class RecordingConfig(BaseModel):
    session_id: str = ''
    base_directory: str = ''
    case_id: str = ''


_HTTP_BIND_ALL = os.getenv('GCS_HTTP_BIND_ALL', '').strip() in ('1', 'true', 'yes')
_ENABLE_COMMAND_HEARTBEAT = False
BACKEND_HTTP_HOST = '0.0.0.0' if _HTTP_BIND_ALL else '127.0.0.1'
BACKEND_HTTP_PORT = 8000
FRONTEND_HTTP_PORT = 5173
BACKEND_HTTP_ACCESS_HOST = 'localhost'


def _build_fixed_connection_config() -> ConnectionConfig:
    udp_config = config.get_udp_config()
    return ConnectionConfig(
        protocol='udp',
        listenAddress=udp_config.listen_host,
        hostPort=udp_config.listen_port,
        remoteIp=udp_config.target_ip,
        commandRecvPort=udp_config.target_port,
        sendOnlyPort=18506,
        lidarSendPort=18507,
        planningSendPort=18510,
        planningRecvPort=18511,
    )


def _reset_connection_config() -> ConnectionConfig:
    global connection_config
    connection_config = _build_fixed_connection_config()
    return connection_config


connection_config = _build_fixed_connection_config()
log_config = LogConfig()
log_file_handles: Dict[str, Any] = {}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_ROOT, 'gcs_backend.log'), encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

config.print_config()

app = FastAPI(
    title='Apollo GCS Web API',
    description='无人机地面站后端 API',
    version='1.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'app://.',
        'file://',
        'null',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


manager = WebSocketManager()
udp_handler: Optional[UDPHandler] = None
udp_server_started = False
heartbeat_task: Optional[asyncio.Task] = None
recording_active = False
current_session_id: Optional[str] = None
recorder: Optional[RawDataRecorder] = None

HEARTBEAT_FUNC_CODE = 0x00
HEARTBEAT_INTERVAL_SEC = 10.0
COMMAND_SEND_MIN_INTERVAL_SEC = 0.5
CMD_IDX_REPEAT_COUNT = 6
CMD_IDX_RESET_TO_ZERO = True

command_send_lock: asyncio.Lock = asyncio.Lock()
command_last_send_at = {
    'flight_control': 0.0,
    'planning': 0.0,
}
command_channel_busy = {
    'flight_control': False,
    'planning': False,
}


def _build_command_log_params(command_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if command_type == 'cmd_idx':
        return {
            'cmdId': params.get('cmdId', 0),
        }
    if command_type == 'cmd_mission':
        return {
            'cmd_mission': params.get('cmd_mission', 0),
            'value': params.get('value', 0.0),
        }
    if command_type == 'set_pids':
        return {
            'param_count': len(params),
        }
    if command_type == 'gcs_command':
        return {
            'seqId': params.get('seqId', 0),
            'targetX': params.get('targetX', 0.0),
            'targetY': params.get('targetY', 0.0),
            'targetZ': params.get('targetZ', 0.0),
            'cruiseSpeed': params.get('cruiseSpeed', 10.0),
            'enable': params.get('enable', 1),
            'cmdId': params.get('cmdId', 0),
        }
    if command_type == 'waypoints_upload':
        return {
            'waypoint_count': len(params.get('waypoints', [])),
            'cruiseSpeed': params.get('cruiseSpeed', 10.0),
        }
    return params

cached_pid_params = {
    'fKaPHI': 0.8, 'fKaP': 0.3, 'fKaY': 0.3, 'fIaY': 0.005,
    'fKaVy': 2.0, 'fIaVy': 0.4, 'fKaAy': 0.28,
    'fKeTHETA': 0.8, 'fKeQ': 0.3, 'fKeX': 0.3, 'fIeX': 0.01,
    'fKeVx': 2.0, 'fIeVx': 0.4, 'fKeAx': 0.55,
    'fKrR': 1.0, 'fIrR': 0.4, 'fKrAy': 0.0, 'fKrPSI': 1.0,
    'fKcH': 0.36, 'fIcH': 0.015, 'fKcHdot': 0.5, 'fIcHdot': 0.05,
    'fKcAz': 0.5, 'fIgRPM': 0.0, 'fKgRPM': 0.0, 'fScale_factor': 0.3,
    'XaccLMT': 1.0, 'YaccLMT': 1.0, 'Hground': 0.4, 'AutoTakeoffHcmd': 10.0,
}

last_broadcast_times: Dict[str, float] = {}

BROADCAST_INTERVALS = {
    'fcs_states': 0.05,
    'fcs_pwms': 0.05,
    'fcs_datactrl': 0.05,
    'fcs_gncbus': 0.05,
    'fcs_esc': 0.10,
    'fcs_datagcs': 0.10,
    'fcs_param': 0.20,
    'fcs_line_aim2ab': 0.10,
    'fcs_line_ab': 0.10,
    'avoiflag': 0.10,
    'planning_telemetry': 0.10,
    'heartbeat_ack': 1.00,
}


def _normalize_listen_ports() -> list[int]:
    ports = [
        connection_config.hostPort,
        connection_config.planningRecvPort,
        connection_config.lidarSendPort,
        connection_config.sendOnlyPort,
    ]
    ordered = []
    seen = set()
    for port in ports:
        if port and port not in seen:
            seen.add(port)
            ordered.append(port)
    return ordered


def _build_ws_payload(
    message_type: str,
    data: Optional[dict] = None,
    session_id: Optional[str] = None,
    case_id: Optional[str] = None,
    timestamp: Optional[int] = None,
    extra: Optional[dict] = None,
) -> dict:
    payload = {
        'type': message_type,
        'timestamp': timestamp if timestamp is not None else int(time.time() * 1000),
        'session_id': session_id,
        'case_id': case_id,
        'source': 'apollo_backend',
        'schema_version': 'v1.0',
        'data': data or {},
    }
    if extra:
        payload.update(extra)
    return payload


def _build_recording_status_payload(is_active: bool, session_id: Optional[str], session_info: Optional[dict] = None) -> dict:
    session_info = session_info or {}
    duration_sec = 0.0
    if is_active and session_info.get('start_time'):
        duration_sec = max(0.0, time.time() - float(session_info.get('start_time')))
    elif session_info.get('duration') is not None:
        duration_sec = float(session_info.get('duration') or 0.0)

    return _build_ws_payload(
        'recording_status',
        session_id=session_id,
        case_id=session_info.get('case_id'),
        data={
            'recording': is_active,
            'duration_sec': round(duration_sec, 3),
            'output_dir': session_info.get('data_directory', ''),
            'bytes_written': session_info.get('total_bytes', 0),
        },
        extra={
            'is_active': is_active,
            'session_info': session_info,
        },
    )


def _build_udp_status_payload(is_connected: bool) -> dict:
    return {
        'type': 'udp_status_change',
        'status': 'connected' if is_connected else 'disconnected',
        'config': connection_config.dict(),
        'primary_receive_port': connection_config.hostPort,
        'flight_telemetry_primary_port': connection_config.hostPort,
        'flight_telemetry_fallback_port': connection_config.sendOnlyPort,
        'planning_telemetry_port': connection_config.planningRecvPort,
        'backend_http_url': f'http://{BACKEND_HTTP_ACCESS_HOST}:{BACKEND_HTTP_PORT}',
        'timestamp': int(time.time() * 1000),
    }


def _cache_ws_snapshot(payload: dict, cache_key: str) -> dict:
    manager.cache_message(payload, cache_key)
    return payload


def _should_broadcast_packet(msg_type: str, func_code: int, current_time: float) -> bool:
    key = msg_type or f'func_{func_code:02X}'
    interval = BROADCAST_INTERVALS.get(msg_type, 0.0)
    if interval <= 0:
        return True
    last_time = last_broadcast_times.get(key, 0.0)
    if current_time - last_time < interval:
        return False
    last_broadcast_times[key] = current_time
    return True


def save_data_to_log(category: str, message: dict) -> None:
    global log_file_handles

    if not log_config.autoRecord or 'telemetry' not in log_file_handles:
        return

    try:
        if log_config.logFormat == 'csv':
            csv_line = get_data_for_type(category, message)
            log_file_handles['telemetry'].write(csv_line + '\n')
            log_file_handles['telemetry'].flush()
        else:
            binary_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            log_file_handles['telemetry'].write(binary_data + b'\n')
            log_file_handles['telemetry'].flush()
    except Exception as exc:
        logger.error('保存日志失败 [%s]: %s', category, exc)


def _resolve_command_channel(command_type: str) -> Optional[str]:
    if command_type in {'cmd_idx', 'cmd_mission', 'set_pids'}:
        return 'flight_control'
    if command_type in {'gcs_command', 'waypoints_upload'}:
        return 'planning'
    return None


async def _check_command_send_rate(command_type: str) -> Optional[dict]:
    channel = _resolve_command_channel(command_type)
    if not channel:
        return None

    async with command_send_lock:
        if command_channel_busy.get(channel):
            return {
                'type': 'command_response',
                'command': command_type,
                'status': 'rate_limited',
                'message': '上一条同通道指令仍在发送，请稍后重试',
                'timestamp': int(time.time() * 1000),
            }

        now = time.monotonic()
        elapsed = now - command_last_send_at.get(channel, 0.0)
        if elapsed < COMMAND_SEND_MIN_INTERVAL_SEC:
            retry_after_ms = max(1, int((COMMAND_SEND_MIN_INTERVAL_SEC - elapsed) * 1000))
            return {
                'type': 'command_response',
                'command': command_type,
                'status': 'rate_limited',
                'message': f'发送过快，请至少间隔100ms，建议 {retry_after_ms}ms 后重试',
                'timestamp': int(time.time() * 1000),
            }

        command_channel_busy[channel] = True

    return None


async def _mark_command_sent(channel: Optional[str]) -> None:
    if not channel:
        return
    async with command_send_lock:
        command_last_send_at[channel] = time.monotonic()


async def _release_command_channel(channel: Optional[str]) -> None:
    if not channel:
        return
    async with command_send_lock:
        command_channel_busy[channel] = False


def _build_default_session_id() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


async def _heartbeat_loop() -> None:
    if not _ENABLE_COMMAND_HEARTBEAT:
        logger.info('飞控指令心跳已禁用，跳过心跳任务启动')
        return

    logger.info(
        '启动 UDP 心跳任务: 本地%s -> %s:%s interval=%.1fs',
        connection_config.sendOnlyPort,
        connection_config.remoteIp,
        connection_config.commandRecvPort,
        HEARTBEAT_INTERVAL_SEC,
    )
    try:
        while True:
            if udp_handler and udp_server_started and udp_handler.is_running():
                # 避免在飞控指令突发发送窗口中插入心跳，干扰机载端按既有节奏取样。
                if not command_channel_busy.get('flight_control'):
                    packet = encode_command_packet(HEARTBEAT_FUNC_CODE, b'')
                    udp_handler.send_data(packet, connection_config.remoteIp, connection_config.commandRecvPort)
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
    except asyncio.CancelledError:
        logger.info('UDP 心跳任务已停止')
        raise


def on_udp_message_received(message: dict) -> None:
    msg_type = message.get('type', 'unknown')
    func_code = int(message.get('func_code', 0) or 0)
    current_time = time.time()

    if recording_active and recorder:
        recorder.record_decoded_packet(message)

    if log_config.autoRecord:
        save_data_to_log(msg_type, message)

    if _should_broadcast_packet(msg_type, func_code, current_time):
        payload = _cache_ws_snapshot(
            _build_ws_payload(
                'udp_data',
                data=message,
                session_id=current_session_id,
                case_id=getattr(recorder, 'case_id', None) if recorder else None,
                timestamp=message.get('timestamp', int(current_time * 1000)),
            ),
            f'udp_data:{msg_type}'
        )
        asyncio.create_task(
            manager.broadcast(payload)
        )


async def send_pid_params_to_drone(pids_data: dict) -> dict:
    global cached_pid_params

    try:
        cached_pid_params.update(pids_data)
        payload = encode_extu_fcs_from_dict(
            cached_pid_params,
            cmd_idx=0,
            cmd_mission=0,
            cmd_mission_val=0.0,
        )
        packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)

        if not udp_handler:
            return {
                'type': 'command_response',
                'command': 'set_pids',
                'status': 'error',
                'message': 'UDP服务器未启动',
                'timestamp': int(time.time() * 1000),
            }

        udp_handler.send_data(packet, connection_config.remoteIp, connection_config.commandRecvPort)
        return {
            'type': 'command_response',
            'command': 'set_pids',
            'status': 'success',
            'message': 'PID参数已发送',
            'timestamp': int(time.time() * 1000),
        }
    except Exception as exc:
        logger.error('发送 PID 参数失败: %s', exc)
        return {
            'type': 'command_response',
            'command': 'set_pids',
            'status': 'error',
            'message': f'发送失败: {exc}',
            'timestamp': int(time.time() * 1000),
        }


async def handle_client_message(message: dict, websocket: WebSocket) -> None:
    global recording_active, current_session_id, recorder

    msg_type = message.get('type')

    if msg_type == 'ping':
        await websocket.send_json({
            'type': 'pong',
            'timestamp': int(time.time() * 1000),
            'source': 'apollo_backend',
        })
        return

    if msg_type == 'command':
        command = message.get('command')
        params = message.get('params', {})

        if command == 'set_pids':
            result = await send_pid_params_to_drone(params)
            await websocket.send_json(result)
            return

        await websocket.send_json({
            'type': 'command_response',
            'command': command,
            'status': 'success',
            'message': '指令确认',
            'timestamp': int(time.time() * 1000),
        })
        return

    if msg_type == 'recording':
        action = message.get('action')
        if action == 'start' and not recording_active:
            session_id = _build_default_session_id()
            base_directory = os.path.join(DATA_ROOT, 'Log', 'Records')
            recorder = RawDataRecorder(session_id, base_directory)
            recorder.enabled_ports = _normalize_listen_ports()
            recorder.start_recording()
            recording_active = True
            current_session_id = session_id
            await manager.broadcast(_cache_ws_snapshot(
                _build_recording_status_payload(True, session_id, recorder.get_session_info()),
                'recording_status'
            ))
            return

        if action == 'stop' and recording_active and recorder:
            session_info = recorder.get_session_info()
            recorder.stop_recording()
            last_session_id = current_session_id
            recording_active = False
            current_session_id = None
            await manager.broadcast(_cache_ws_snapshot(
                _build_recording_status_payload(False, last_session_id, session_info),
                'recording_status'
            ))
            return

    if msg_type == 'get_config':
        config_type = message.get('data', {}).get('config_type', 'all')
        if config_type in {'connection', 'all'}:
            await websocket.send_json({
                'type': 'config_response',
                'config_type': 'connection',
                'data': connection_config.dict(),
                'timestamp': int(time.time() * 1000),
            })
        if config_type in {'log', 'all'}:
            await websocket.send_json({
                'type': 'config_response',
                'config_type': 'log',
                'data': log_config.dict(),
                'timestamp': int(time.time() * 1000),
            })


@app.get('/')
async def root() -> dict:
    return {
        'name': 'GCS Web Backend',
        'version': '1.0.0',
        'status': 'running',
    }


@app.get('/health')
async def health_check() -> dict:
    return {
        'status': 'healthy',
        'websocket_connections': manager.get_connection_count(),
        'timestamp': int(time.time()),
    }


@app.websocket('/ws/drone')
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager.cache_message(
        _build_udp_status_payload(bool(udp_handler and udp_handler.is_running())),
        'udp_status_change'
    )
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_client_message(message, websocket)
            except json.JSONDecodeError as exc:
                logger.error('JSON解析失败: %s', exc)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error('WebSocket错误: %s', exc)
    finally:
        manager.disconnect(websocket)


@app.get('/api/config/connection')
async def get_connection_config() -> dict:
    active_config = _reset_connection_config()
    return {
        'type': 'connection_config',
        'data': {
            **active_config.dict(),
            'semantics': {
                'gcs_primary_receive_port': active_config.hostPort,
                'gcs_flight_telemetry_primary_port': active_config.hostPort,
                'gcs_flight_telemetry_fallback_port': active_config.sendOnlyPort,
                'gcs_planning_telemetry_port': active_config.planningRecvPort,
                'uav_command_receive_port': active_config.commandRecvPort,
                'backend_http_bind_url': f'http://{BACKEND_HTTP_HOST}:{BACKEND_HTTP_PORT}',
                'backend_http_url': f'http://{BACKEND_HTTP_ACCESS_HOST}:{BACKEND_HTTP_PORT}',
                'frontend_access_urls': [
                    f'http://localhost:{FRONTEND_HTTP_PORT}',
                    f'http://127.0.0.1:{FRONTEND_HTTP_PORT}',
                ],
            },
        },
        'timestamp': int(time.time() * 1000),
    }


@app.post('/api/config/connection')
async def update_connection_config(config_payload: ConnectionConfig) -> dict:
    del config_payload
    active_config = _reset_connection_config()
    await manager.broadcast(_cache_ws_snapshot({
        'type': 'config_update',
        'config_type': 'connection',
        'data': active_config.dict(),
        'timestamp': int(time.time() * 1000),
    }, 'config_update:connection'))
    return {
        'status': 'success',
        'message': '固定链路参数已生效',
        'data': active_config.dict(),
    }


@app.get('/api/config/log')
async def get_log_config() -> dict:
    return {
        'type': 'log_config',
        'data': log_config.dict(),
        'timestamp': int(time.time() * 1000),
    }


@app.post('/api/config/log')
async def update_log_config(config_payload: LogConfig) -> dict:
    global log_config, log_file_handles

    for file_handle in log_file_handles.values():
        try:
            file_handle.close()
        except Exception:
            pass
    log_file_handles.clear()

    log_config = config_payload

    if config_payload.autoRecord:
        log_dir = os.path.join(DATA_ROOT, 'Log')
        os.makedirs(log_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'drone_log_{timestamp_str}.{config_payload.logFormat}'
        log_path = os.path.join(log_dir, log_filename)

        if config_payload.logFormat == 'csv':
            handle = open(log_path, 'a', newline='', encoding='utf-8')
            if os.path.getsize(log_path) == 0:
                handle.write(get_full_header() + '\n')
        else:
            handle = open(log_path, 'ab')

        log_file_handles['telemetry'] = handle

    await manager.broadcast(_cache_ws_snapshot({
        'type': 'config_update',
        'config_type': 'log',
        'data': config_payload.dict(),
        'timestamp': int(time.time() * 1000),
    }, 'config_update:log'))
    return {'status': 'success', 'message': '日志配置已更新'}


@app.post('/api/log/save')
async def save_log_entry(data: dict) -> dict:
    if not log_config.autoRecord:
        return {'status': 'skipped', 'message': '自动记录未启用'}
    try:
        category = data.get('category', 'unknown')
        save_data_to_log(category, data.get('message', {}))
        return {'status': 'success', 'message': '日志已保存'}
    except Exception as exc:
        logger.error('保存日志失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/udp/start')
async def start_udp_server() -> dict:
    global udp_handler, udp_server_started, heartbeat_task

    try:
        if udp_server_started and udp_handler:
            await udp_handler.stop_server()
            udp_server_started = False

        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)

        active_config = _reset_connection_config()
        ports = _normalize_listen_ports()

        await udp_handler.start_server(
            host=active_config.listenAddress,
            ports=ports,
            target_host=active_config.remoteIp,
            target_port=active_config.commandRecvPort,
        )
        udp_server_started = True

        if _ENABLE_COMMAND_HEARTBEAT and (heartbeat_task is None or heartbeat_task.done()):
            heartbeat_task = asyncio.create_task(_heartbeat_loop())

        await manager.broadcast(_cache_ws_snapshot(_build_udp_status_payload(True), 'udp_status_change'))

        return {
            'status': 'success',
            'message': 'UDP服务器已启动',
            'data': {
                'ports': ports,
                'target': f'{active_config.remoteIp}:{active_config.commandRecvPort}',
            },
        }
    except Exception as exc:
        logger.error('启动UDP服务器失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/udp/stop')
async def stop_udp_server() -> dict:
    global udp_server_started, heartbeat_task

    try:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            heartbeat_task = None

        if udp_handler and udp_server_started:
            await udp_handler.stop_server()
            udp_server_started = False

        await manager.broadcast(_cache_ws_snapshot(_build_udp_status_payload(False), 'udp_status_change'))
        return {'status': 'success', 'message': 'UDP服务器已停止'}
    except Exception as exc:
        logger.error('停止UDP服务器失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/api/udp/status')
async def get_udp_status() -> dict:
    global udp_server_started

    is_actually_running = bool(udp_handler and udp_handler.is_running())
    udp_server_started = is_actually_running
    manager.cache_message(_build_udp_status_payload(is_actually_running), 'udp_status_change')
    return {
        'status': 'success',
        'data': {
            'connected': is_actually_running,
            'config': connection_config.dict(),
            'listen_host': connection_config.listenAddress,
            'listen_ports': _normalize_listen_ports(),
            'primary_receive_port': connection_config.hostPort,
            'flight_telemetry_primary_port': connection_config.hostPort,
            'flight_telemetry_fallback_port': connection_config.sendOnlyPort,
            'planning_telemetry_port': connection_config.planningRecvPort,
            'backend_http_bind_url': f'http://{BACKEND_HTTP_HOST}:{BACKEND_HTTP_PORT}',
            'backend_http_url': f'http://{BACKEND_HTTP_ACCESS_HOST}:{BACKEND_HTTP_PORT}',
            'frontend_access_urls': [
                f'http://localhost:{FRONTEND_HTTP_PORT}',
                f'http://127.0.0.1:{FRONTEND_HTTP_PORT}',
            ],
            'timestamp': int(time.time() * 1000),
        },
    }


@app.post('/api/command')
async def send_command_to_drone(request: CommandRequest) -> dict:
    try:
        command_type = request.type
        params = request.params
        packet = None
        channel = _resolve_command_channel(command_type)
        target_host = connection_config.remoteIp
        target_port = connection_config.commandRecvPort
        response_message = '指令已发送'

        if command_type == 'cmd_idx':
            payload = encode_extu_fcs_from_dict(
                cached_pid_params,
                cmd_idx=params.get('cmdId', 0),
                cmd_mission=0,
                cmd_mission_val=0.0,
            )
            packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
        elif command_type == 'cmd_mission':
            payload = encode_extu_fcs_from_dict(
                cached_pid_params,
                cmd_idx=0,
                cmd_mission=params.get('cmd_mission', 0),
                cmd_mission_val=params.get('value', 0.0),
            )
            packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
        elif command_type == 'set_pids':
            cached_pid_params.update(params)
            payload = encode_extu_fcs_from_dict(
                cached_pid_params,
                cmd_idx=0,
                cmd_mission=0,
                cmd_mission_val=0.0,
            )
            packet = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload)
        elif command_type == 'gcs_command':
            target_port = connection_config.planningSendPort
            payload = encode_gcs_command(
                params.get('seqId', 0),
                params.get('targetX', 0.0),
                params.get('targetY', 0.0),
                params.get('targetZ', 0.0),
                params.get('cruiseSpeed', 10.0),
                params.get('enable', 1),
                params.get('cmdId', 0),
            )
            packet = encode_command_packet(NCLINK_GCS_COMMAND, payload)
        elif command_type == 'waypoints_upload':
            target_port = connection_config.planningSendPort
            payload = encode_waypoints_upload(params.get('waypoints', []), params.get('cruiseSpeed', 10.0))
            packet = encode_command_packet(NCLINK_GCS_COMMAND, payload)
        else:
            return {
                'type': 'command_response',
                'command': command_type,
                'status': 'error',
                'message': f'未知指令: {command_type}',
                'timestamp': int(time.time() * 1000),
            }

        if not packet or not udp_handler:
            return {
                'type': 'command_response',
                'command': command_type,
                'status': 'error',
                'message': 'UDP服务器未启动',
                'timestamp': int(time.time() * 1000),
            }

        rate_limit_result = await _check_command_send_rate(command_type)
        if rate_limit_result is not None:
            return rate_limit_result

        try:
            logger.info(
                '准备发送指令: type=%s target=%s:%s bytes=%d params=%s',
                command_type,
                target_host,
                target_port,
                len(packet),
                json.dumps(_build_command_log_params(command_type, params), ensure_ascii=False),
            )

            if command_type == 'cmd_idx':
                cmd_id = params.get('cmdId', 0)
                if 1 <= cmd_id <= 25:
                    for repeat_index in range(CMD_IDX_REPEAT_COUNT):
                        udp_handler.send_data(packet, target_host, target_port)
                        await _mark_command_sent(channel)
                        if repeat_index < CMD_IDX_REPEAT_COUNT - 1:
                            await asyncio.sleep(COMMAND_SEND_MIN_INTERVAL_SEC)

                    if CMD_IDX_RESET_TO_ZERO:
                        payload_zero = encode_extu_fcs_from_dict(
                            cached_pid_params,
                            cmd_idx=0,
                            cmd_mission=0,
                            cmd_mission_val=0.0,
                        )
                        packet_zero = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload_zero)
                        udp_handler.send_data(packet_zero, target_host, target_port)
                        await _mark_command_sent(channel)
                        response_message = f'指令{cmd_id}已按100ms间隔连续发送{CMD_IDX_REPEAT_COUNT}次，末次已置0'
                    else:
                        response_message = f'指令{cmd_id}已按100ms间隔连续发送{CMD_IDX_REPEAT_COUNT}次'
                else:
                    udp_handler.send_data(packet, target_host, target_port)
                    await _mark_command_sent(channel)
                    response_message = f'指令{cmd_id}已发送'
            else:
                udp_handler.send_data(packet, target_host, target_port)
                await _mark_command_sent(channel)

            logger.info(
                '指令发送完成: type=%s target=%s:%s status=success',
                command_type,
                target_host,
                target_port,
            )

            return {
                'type': 'command_response',
                'command': command_type,
                'status': 'success',
                'message': response_message,
                'timestamp': int(time.time() * 1000),
            }
        finally:
            await _release_command_channel(channel)
    except Exception as exc:
        logger.error('发送指令失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/api/recording/status')
async def get_recording_status() -> dict:
    session_info = recorder.get_session_info() if recorder else None
    return _build_recording_status_payload(recording_active, current_session_id, session_info)


@app.post('/api/recording/start')
async def start_recording(config_payload: RecordingConfig) -> dict:
    global recording_active, current_session_id, recorder

    if recording_active:
        return {
            'type': 'recording_response',
            'status': 'error',
            'message': '录制已在进行中',
            'timestamp': int(time.time() * 1000),
        }

    try:
        session_id = config_payload.session_id.strip() or _build_default_session_id()
        if not config_payload.base_directory:
            base_directory = os.path.join(DATA_ROOT, 'Log', 'Records')
        elif os.path.isabs(config_payload.base_directory):
            base_directory = config_payload.base_directory
        else:
            base_directory = os.path.join(DATA_ROOT, config_payload.base_directory)

        recorder = RawDataRecorder(
            session_id,
            base_directory,
            case_id_override=config_payload.case_id or None,
        )
        recorder.enabled_ports = _normalize_listen_ports()
        recorder.start_recording()

        recording_active = True
        current_session_id = session_id
        payload = _cache_ws_snapshot(
            _build_recording_status_payload(True, current_session_id, recorder.get_session_info()),
            'recording_status'
        )
        await manager.broadcast(payload)

        return {
            'type': 'recording_response',
            'status': 'success',
            'message': '录制已开始',
            'session_id': current_session_id,
            'session_info': recorder.get_session_info(),
            'timestamp': int(time.time() * 1000),
        }
    except Exception as exc:
        logger.error('开始录制失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/api/recording/stop')
async def stop_recording() -> dict:
    global recording_active, current_session_id

    if not recording_active or not recorder:
        return {
            'type': 'recording_response',
            'status': 'error',
            'message': '录制未开始',
            'timestamp': int(time.time() * 1000),
        }

    try:
        session_info = recorder.get_session_info()
        recorder.stop_recording()
        session_id = current_session_id
        recording_active = False
        current_session_id = None

        payload = _cache_ws_snapshot(
            _build_recording_status_payload(False, session_id, session_info),
            'recording_status'
        )
        await manager.broadcast(payload)

        return {
            'type': 'recording_response',
            'status': 'success',
            'message': '录制已停止',
            'session_id': session_id,
            'session_info': session_info,
            'timestamp': int(time.time() * 1000),
        }
    except Exception as exc:
        logger.error('停止录制失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


manager.cache_message({
    'type': 'config_update',
    'config_type': 'connection',
    'data': connection_config.dict(),
    'timestamp': int(time.time() * 1000),
}, 'config_update:connection')

manager.cache_message({
    'type': 'config_update',
    'config_type': 'log',
    'data': log_config.dict(),
    'timestamp': int(time.time() * 1000),
}, 'config_update:log')

manager.cache_message(_build_udp_status_payload(False), 'udp_status_change')

manager.cache_message(
    _build_recording_status_payload(False, None, {}),
    'recording_status'
)


@app.get('/api/recording/sessions')
async def list_sessions(base_directory: str = 'data') -> dict:
    try:
        if not os.path.exists(base_directory):
            return {
                'type': 'sessions_list',
                'sessions': [],
                'timestamp': int(time.time() * 1000),
            }

        sessions = []
        for session_id in os.listdir(base_directory):
            session_path = os.path.join(base_directory, session_id)
            if not os.path.isdir(session_path):
                continue
            file_count = 0
            for _, _, files in os.walk(session_path):
                file_count += len(files)
            sessions.append({
                'session_id': session_id,
                'file_count': file_count,
                'path': session_path,
            })

        return {
            'type': 'sessions_list',
            'sessions': sorted(sessions, key=lambda item: item['session_id'], reverse=True),
            'timestamp': int(time.time() * 1000),
        }
    except Exception as exc:
        logger.error('列出会话失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.on_event('startup')
async def startup_event() -> None:
    global udp_handler, udp_server_started, heartbeat_task, command_send_lock

    logger.info('=' * 60)
    logger.info('Apollo GCS Web 后端启动（核心通信版）')
    logger.info('=' * 60)

    command_send_lock = asyncio.Lock()

    try:
        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)

        ports = _normalize_listen_ports()
        await udp_handler.start_server(host=connection_config.listenAddress, ports=ports)
        udp_server_started = True

        if _ENABLE_COMMAND_HEARTBEAT and (heartbeat_task is None or heartbeat_task.done()):
            heartbeat_task = asyncio.create_task(_heartbeat_loop())
        elif not _ENABLE_COMMAND_HEARTBEAT:
            logger.info('飞控指令心跳默认关闭，不在启动阶段创建心跳任务')
    except Exception as exc:
        logger.error('UDP服务器自动启动失败: %s', exc)


@app.on_event('shutdown')
async def shutdown_event() -> None:
    global udp_server_started, heartbeat_task

    if heartbeat_task is not None:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        heartbeat_task = None

    for file_handle in log_file_handles.values():
        try:
            file_handle.close()
        except Exception:
            pass
    log_file_handles.clear()

    if udp_handler:
        await udp_handler.stop_server()
        udp_server_started = False


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app,
        host=BACKEND_HTTP_HOST,
        port=BACKEND_HTTP_PORT,
        reload=False,
        log_level='info',
    )