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

from app_models import CommandRequest, ConnectionConfig, LogConfig, RecordingConfig
from config import config
from events import build_standard_event
from online_analysis_adapter import (
    build_online_analysis_ingest_envelope as _build_online_analysis_ingest_envelope,
    create_embedded_online_analysis_service as _create_embedded_online_analysis_service,
    get_online_analysis_routing_key as _get_online_analysis_routing_key,
    get_standard_event_from_envelope as _get_standard_event_from_envelope,
    ingest_online_analysis_sync as _ingest_online_analysis_sync,
    is_online_analysis_embedded as _is_online_analysis_embedded,
    is_online_analysis_sidecar as _is_online_analysis_sidecar,
    should_forward_to_online_analysis as _should_forward_to_online_analysis,
)
from payload_builders import (
    build_command_log_params as _build_command_log_params,
    build_empty_recent_traffic_snapshot as _build_empty_recent_traffic_snapshot,
    build_online_analysis_config_payload as _build_online_analysis_config_payload,
    build_recording_status_payload as _build_recording_status_payload,
    build_udp_status_payload as _build_udp_status_payload,
    build_ws_payload as _build_ws_payload,
    normalize_log_value as _normalize_log_value,
)
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
from routes import create_config_router, create_general_router, create_operations_router
from runtime_helpers import (
    build_default_session_id as _build_default_session_id,
    cache_ws_snapshot as _runtime_cache_ws_snapshot,
    get_pipeline_status as _runtime_get_pipeline_status,
    get_transport_runtime_stats as _runtime_get_transport_runtime_stats,
    resolve_command_channel as _runtime_resolve_command_channel,
)
from websocket.websocket_manager import WebSocketManager


_HTTP_BIND_ALL = os.getenv('GCS_HTTP_BIND_ALL', '').strip() in ('1', 'true', 'yes')
_ENABLE_COMMAND_HEARTBEAT = False
BACKEND_HTTP_HOST = '0.0.0.0' if _HTTP_BIND_ALL else '127.0.0.1'
BACKEND_HTTP_PORT = 8000
FRONTEND_HTTP_PORT = 5173
BACKEND_HTTP_ACCESS_HOST = 'localhost'
ONLINE_ANALYSIS_ENABLED = os.getenv('ONLINE_ANALYSIS_ENABLED', '1').strip().lower() in ('1', 'true', 'yes')
ONLINE_ANALYSIS_MODE = (os.getenv('ONLINE_ANALYSIS_MODE', 'embedded') or 'embedded').strip().lower()
ONLINE_ANALYSIS_PROJECT_ROOT = os.path.abspath(
    os.getenv('ONLINE_ANALYSIS_PROJECT_ROOT')
    or os.path.join(PROJECT_ROOT, '..', 'OnlineAnalysis')
)
ONLINE_ANALYSIS_BASE_URL = os.getenv('ONLINE_ANALYSIS_BASE_URL', 'http://127.0.0.1:8010').rstrip('/')
ONLINE_ANALYSIS_TIMEOUT_MS = max(int(os.getenv('ONLINE_ANALYSIS_TIMEOUT_MS', '250') or 250), 50)
ONLINE_ANALYSIS_FORWARD_TYPES = {
    'fcs_states',
    'fcs_pwms',
    'fcs_datactrl',
    'fcs_gncbus',
    'fcs_datagcs',
    'planning_telemetry',
    'lidar_obstacles',
    'lidar_performance',
    'lidar_status',
    'avoiflag',
}


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
log_write_counters: Dict[str, int] = {}

LEGACY_LOG_FLUSH_INTERVAL = 20

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

online_analysis_service = None


online_analysis_service = _create_embedded_online_analysis_service(
    enabled=ONLINE_ANALYSIS_ENABLED,
    mode=ONLINE_ANALYSIS_MODE,
    project_root=ONLINE_ANALYSIS_PROJECT_ROOT,
    logger=logger,
)

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
packet_processing_queue: Optional[asyncio.Queue] = None
packet_processing_task: Optional[asyncio.Task] = None
recording_queue: Optional[asyncio.Queue] = None
recording_task: Optional[asyncio.Task] = None
online_analysis_queue: Optional[asyncio.Queue] = None
online_analysis_task: Optional[asyncio.Task] = None
recording_active = False
current_session_id: Optional[str] = None
recorder: Optional[RawDataRecorder] = None
pending_latest_packets: Dict[str, dict] = {}
pending_online_analysis_packets: Dict[str, dict] = {}
packet_drop_counters: Dict[str, int] = {
    'processing_queue_full': 0,
    'processing_queue_coalesced': 0,
    'recording_queue_full': 0,
    'online_analysis_queue_full': 0,
    'online_analysis_queue_coalesced': 0,
}

HEARTBEAT_FUNC_CODE = 0x00
HEARTBEAT_INTERVAL_SEC = 10.0
COMMAND_SEND_MIN_INTERVAL_SEC = 0.5
CMD_IDX_REPEAT_COUNT = 6
CMD_IDX_RESET_TO_ZERO = True
PLANNING_COMMAND_REPEAT_COUNT = 3
PLANNING_COMMAND_REPEAT_INTERVAL_SEC = 0.5

command_send_lock: asyncio.Lock = asyncio.Lock()
command_last_send_at = {
    'flight_control': 0.0,
    'planning': 0.0,
}
command_channel_busy = {
    'flight_control': False,
    'planning': False,
}
online_analysis_runtime: Dict[str, Any] = {
    'enabled': ONLINE_ANALYSIS_ENABLED,
    'mode': ONLINE_ANALYSIS_MODE,
    'base_url': ONLINE_ANALYSIS_BASE_URL,
    'project_root': ONLINE_ANALYSIS_PROJECT_ROOT,
    'timeout_ms': ONLINE_ANALYSIS_TIMEOUT_MS,
    'last_forward_ok_at': None,
    'last_error': '',
    'last_snapshot': None,
}

if ONLINE_ANALYSIS_ENABLED and _is_online_analysis_embedded(ONLINE_ANALYSIS_ENABLED, ONLINE_ANALYSIS_MODE) and online_analysis_service is None:
    online_analysis_runtime['last_error'] = 'embedded service unavailable'

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

PACKET_PROCESSING_QUEUE_MAXSIZE = 2048
RECORDING_QUEUE_MAXSIZE = 8192
PACKET_PROCESSING_BATCH_SIZE = 64
RECORDING_BATCH_SIZE = 32
ONLINE_ANALYSIS_QUEUE_MAXSIZE = 256
ONLINE_ANALYSIS_BATCH_SIZE = 8
HIGH_FREQUENCY_PACKET_TYPES = {
    msg_type for msg_type, interval in BROADCAST_INTERVALS.items()
    if 0 < interval <= 0.10 and msg_type != 'heartbeat_ack'
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


async def _forward_to_online_analysis(envelope: dict[str, Any]) -> None:
    routing_key = _get_online_analysis_routing_key(envelope)
    if not _should_forward_to_online_analysis(ONLINE_ANALYSIS_ENABLED, routing_key, ONLINE_ANALYSIS_FORWARD_TYPES):
        return

    try:
        result = await asyncio.to_thread(
            _ingest_online_analysis_sync,
            envelope=envelope,
            enabled=ONLINE_ANALYSIS_ENABLED,
            mode=ONLINE_ANALYSIS_MODE,
            base_url=ONLINE_ANALYSIS_BASE_URL,
            timeout_ms=ONLINE_ANALYSIS_TIMEOUT_MS,
            service=online_analysis_service,
        )
        online_analysis_runtime['last_forward_ok_at'] = int(time.time() * 1000)
        online_analysis_runtime['last_error'] = ''

        snapshot = result.get('snapshot') if isinstance(result, dict) else None
        if isinstance(snapshot, dict) and snapshot:
            online_analysis_runtime['last_snapshot'] = snapshot
            payload = _cache_ws_snapshot(snapshot, 'online_analysis_status')
            await manager.broadcast(payload)
    except Exception as exc:
        if online_analysis_runtime.get('last_error') != str(exc):
            logger.warning('OnlineAnalysis 转发失败: %s', exc)
        online_analysis_runtime['last_error'] = str(exc)


def _build_pipeline_control_message(control_type: str) -> dict[str, Any]:
    return {
        '__pipeline_control__': control_type,
        'future': asyncio.get_running_loop().create_future(),
    }


def _is_pipeline_control_message(message: Any) -> bool:
    return isinstance(message, dict) and '__pipeline_control__' in message


async def _await_queue_barrier(queue: Optional[asyncio.Queue]) -> None:
    if queue is None:
        return

    barrier_message = _build_pipeline_control_message('barrier')
    future = barrier_message['future']
    await queue.put(barrier_message)
    await future


def _flush_pending_online_analysis_packets_to_queue() -> None:
    if online_analysis_queue is None or online_analysis_queue.full() or not pending_online_analysis_packets:
        return

    for msg_type in list(pending_online_analysis_packets.keys()):
        if online_analysis_queue.full():
            break
        online_analysis_queue.put_nowait(pending_online_analysis_packets.pop(msg_type))


def _enqueue_online_analysis_message(payload: dict[str, Any]) -> None:
    if online_analysis_queue is None:
        asyncio.create_task(_forward_to_online_analysis(payload))
        return

    msg_type = _get_online_analysis_routing_key(payload) or 'unknown'
    try:
        online_analysis_queue.put_nowait(payload)
    except asyncio.QueueFull:
        if _is_high_frequency_packet(msg_type):
            pending_online_analysis_packets[msg_type] = payload
            packet_drop_counters['online_analysis_queue_coalesced'] += 1
            if packet_drop_counters['online_analysis_queue_coalesced'] % 200 == 0:
                logger.warning(
                    'OnlineAnalysis 高频消息正在合并以限制积压: coalesced=%d queue=%d pending=%d',
                    packet_drop_counters['online_analysis_queue_coalesced'],
                    online_analysis_queue.qsize(),
                    len(pending_online_analysis_packets),
                )
            return

        packet_drop_counters['online_analysis_queue_full'] += 1
        if packet_drop_counters['online_analysis_queue_full'] % 50 == 0:
            logger.warning(
                'OnlineAnalysis 队列已满，丢弃消息: dropped=%d type=%s queue=%d',
                packet_drop_counters['online_analysis_queue_full'],
                msg_type,
                online_analysis_queue.qsize(),
            )


def _is_high_frequency_packet(msg_type: str) -> bool:
    return msg_type in HIGH_FREQUENCY_PACKET_TYPES


def _cache_ws_snapshot(payload: dict, cache_key: str) -> dict:
    return _runtime_cache_ws_snapshot(manager, payload, cache_key)


def _get_pipeline_status() -> dict:
    return _runtime_get_pipeline_status(
        packet_processing_queue,
        recording_queue,
        online_analysis_queue,
        pending_latest_packets,
        pending_online_analysis_packets,
        packet_drop_counters,
    )


def _get_transport_runtime_stats() -> dict:
    return _runtime_get_transport_runtime_stats(udp_handler, _build_empty_recent_traffic_snapshot())


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
    global log_file_handles, log_write_counters

    if not log_config.autoRecord or 'telemetry' not in log_file_handles:
        return

    try:
        if log_config.logFormat == 'csv':
            csv_line = get_data_for_type(category, message)
            log_file_handles['telemetry'].write(csv_line + '\n')
        else:
            binary_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            log_file_handles['telemetry'].write(binary_data + b'\n')

        log_write_counters['telemetry'] = log_write_counters.get('telemetry', 0) + 1
        if log_write_counters['telemetry'] % LEGACY_LOG_FLUSH_INTERVAL == 0:
            log_file_handles['telemetry'].flush()
    except Exception as exc:
        logger.error('保存日志失败 [%s]: %s', category, exc)


def _append_session_communication_log(event: str, **fields: Any) -> None:
    if not recording_active or not recorder:
        return
    payload = {'event': event}
    payload.update(fields)
    recorder.append_backend_communication_log(
        'apollo.communication',
        'INFO',
        json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
    )


async def _check_command_send_rate(command_type: str) -> Optional[dict]:
    channel = _runtime_resolve_command_channel(command_type)
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
                'message': f'发送过快，请至少间隔{int(COMMAND_SEND_MIN_INTERVAL_SEC * 1000)}ms，建议 {retry_after_ms}ms 后重试',
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
                    _append_session_communication_log(
                        'uplink_heartbeat_sent',
                        func_code=f'0x{HEARTBEAT_FUNC_CODE:02X}',
                        target=f'{connection_config.remoteIp}:{connection_config.commandRecvPort}',
                        bytes=len(packet),
                    )
                    udp_handler.send_data(packet, connection_config.remoteIp, connection_config.commandRecvPort)
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
    except asyncio.CancelledError:
        logger.info('UDP 心跳任务已停止')
        raise


def _prepare_udp_message_result(message: dict) -> dict:
    msg_type = message.get('type', 'unknown')
    func_code = int(message.get('func_code', 0) or 0)
    current_time = time.time()
    standard_event = build_standard_event(message)

    should_broadcast = _should_broadcast_packet(msg_type, func_code, current_time)
    payload = None
    cache_key = None
    if should_broadcast:
        payload = _build_ws_payload(
            'udp_data',
            data=message,
            session_id=current_session_id,
            case_id=getattr(recorder, 'case_id', None) if recorder else None,
            timestamp=message.get('timestamp', int(current_time * 1000)),
            extra={'standard_event': standard_event},
        )
        cache_key = f'udp_data:{msg_type}'

    return {
        'msg_type': msg_type,
        'payload': payload,
        'cache_key': cache_key,
        'standard_event': standard_event,
        'should_forward': bool(
            payload and _should_forward_to_online_analysis(ONLINE_ANALYSIS_ENABLED, msg_type, ONLINE_ANALYSIS_FORWARD_TYPES)
        ),
    }


def _record_udp_message_sync(message: dict) -> None:
    msg_type = message.get('type', 'unknown')

    if recording_active and recorder:
        recorder.record_decoded_packet(message)

    if log_config.autoRecord:
        save_data_to_log(msg_type, message)


def _record_udp_message_batch_sync(messages: list[dict]) -> None:
    for message in messages:
        _record_udp_message_sync(message)


def _flush_pending_latest_packets_to_processing_queue() -> None:
    if packet_processing_queue is None or packet_processing_queue.full() or not pending_latest_packets:
        return

    for msg_type in list(pending_latest_packets.keys()):
        if packet_processing_queue.full():
            break
        packet_processing_queue.put_nowait(pending_latest_packets.pop(msg_type))


def _enqueue_processing_message(message: dict) -> None:
    if packet_processing_queue is None:
        result = _prepare_udp_message_result(message)
        payload = result.get('payload')
        cache_key = result.get('cache_key')
        if payload and cache_key:
            _cache_ws_snapshot(payload, cache_key)
            manager.schedule_latest_broadcast(payload, cache_key)
            if result.get('should_forward'):
                _enqueue_online_analysis_message(payload)
        if recording_active or log_config.autoRecord:
            _record_udp_message_sync(message)
        return

    try:
        packet_processing_queue.put_nowait(message)
    except asyncio.QueueFull:
        msg_type = str(message.get('type') or 'unknown')
        if _is_high_frequency_packet(msg_type):
            pending_latest_packets[msg_type] = message
            packet_drop_counters['processing_queue_coalesced'] += 1
            if packet_drop_counters['processing_queue_coalesced'] % 500 == 0:
                logger.warning(
                    '高频UDP消息正在合并以限制积压: coalesced=%d queue=%d pending=%d',
                    packet_drop_counters['processing_queue_coalesced'],
                    packet_processing_queue.qsize(),
                    len(pending_latest_packets),
                )
            return

        packet_drop_counters['processing_queue_full'] += 1
        logger.warning('UDP处理队列已满，丢弃低频消息: type=%s queue=%d', msg_type, packet_processing_queue.qsize())


def _enqueue_recording_message(message: dict) -> None:
    if recording_queue is None:
        _record_udp_message_sync(message)
        return

    try:
        recording_queue.put_nowait(message)
    except asyncio.QueueFull:
        packet_drop_counters['recording_queue_full'] += 1
        msg_type = str(message.get('type') or 'unknown')
        if packet_drop_counters['recording_queue_full'] % 100 == 0:
            logger.warning(
                '录制队列已满，开始丢弃消息: dropped=%d type=%s queue=%d',
                packet_drop_counters['recording_queue_full'],
                msg_type,
                recording_queue.qsize(),
            )


async def _packet_processing_loop() -> None:
    while True:
        message = await packet_processing_queue.get()
        batch = [message]
        try:
            while len(batch) < PACKET_PROCESSING_BATCH_SIZE:
                try:
                    batch.append(packet_processing_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            for item in batch:
                if _is_pipeline_control_message(item):
                    item['future'].set_result(True)
                    continue

                result = _prepare_udp_message_result(item)
                payload = result.get('payload')
                cache_key = result.get('cache_key')
                if payload and cache_key:
                    _cache_ws_snapshot(payload, cache_key)
                    manager.schedule_latest_broadcast(payload, cache_key)
                    if result.get('should_forward'):
                        _enqueue_online_analysis_message(payload)

                if recording_active or log_config.autoRecord:
                    _enqueue_recording_message(item)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('后台处理UDP消息失败: %s', exc)
        finally:
            for _ in batch:
                packet_processing_queue.task_done()
            _flush_pending_latest_packets_to_processing_queue()


async def _recording_loop() -> None:
    while True:
        message = await recording_queue.get()
        batch = [message]
        try:
            while len(batch) < RECORDING_BATCH_SIZE:
                try:
                    batch.append(recording_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            record_batch = []
            for item in batch:
                if _is_pipeline_control_message(item):
                    item['future'].set_result(True)
                    continue
                record_batch.append(item)

            if record_batch:
                await asyncio.to_thread(_record_udp_message_batch_sync, record_batch)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('后台录制UDP消息失败: %s', exc)
        finally:
            for _ in batch:
                recording_queue.task_done()


async def _online_analysis_loop() -> None:
    while True:
        message = await online_analysis_queue.get()
        batch = [message]
        try:
            while len(batch) < ONLINE_ANALYSIS_BATCH_SIZE:
                try:
                    batch.append(online_analysis_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            for item in batch:
                if _is_pipeline_control_message(item):
                    item['future'].set_result(True)
                    continue
                await _forward_to_online_analysis(item)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('后台转发 OnlineAnalysis 失败: %s', exc)
        finally:
            for _ in batch:
                online_analysis_queue.task_done()
            _flush_pending_online_analysis_packets_to_queue()


async def _ensure_packet_processing_pipeline() -> None:
    global packet_processing_queue, packet_processing_task, recording_queue, recording_task
    global online_analysis_queue, online_analysis_task

    if packet_processing_queue is None:
        packet_processing_queue = asyncio.Queue(maxsize=PACKET_PROCESSING_QUEUE_MAXSIZE)

    if recording_queue is None:
        recording_queue = asyncio.Queue(maxsize=RECORDING_QUEUE_MAXSIZE)

    if online_analysis_queue is None:
        online_analysis_queue = asyncio.Queue(maxsize=ONLINE_ANALYSIS_QUEUE_MAXSIZE)

    if packet_processing_task is None or packet_processing_task.done():
        packet_processing_task = asyncio.create_task(_packet_processing_loop())

    if recording_task is None or recording_task.done():
        recording_task = asyncio.create_task(_recording_loop())

    if online_analysis_task is None or online_analysis_task.done():
        online_analysis_task = asyncio.create_task(_online_analysis_loop())


async def _stop_packet_processing_pipeline() -> None:
    global packet_processing_task, recording_task, online_analysis_task

    if packet_processing_queue is not None:
        try:
            await asyncio.wait_for(packet_processing_queue.join(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning('UDP消息后台队列在关闭时仍有积压，继续执行停机')

    if recording_queue is not None:
        try:
            await asyncio.wait_for(recording_queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning('录制后台队列在关闭时仍有积压，继续执行停机')

    if online_analysis_queue is not None:
        try:
            await asyncio.wait_for(online_analysis_queue.join(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning('OnlineAnalysis 后台队列在关闭时仍有积压，继续执行停机')

    if packet_processing_task is not None:
        packet_processing_task.cancel()
        try:
            await packet_processing_task
        except asyncio.CancelledError:
            pass
        packet_processing_task = None

    if recording_task is not None:
        recording_task.cancel()
        try:
            await recording_task
        except asyncio.CancelledError:
            pass
        recording_task = None

    if online_analysis_task is not None:
        online_analysis_task.cancel()
        try:
            await online_analysis_task
        except asyncio.CancelledError:
            pass
        online_analysis_task = None


async def _drain_recording_pipeline() -> None:
    await _await_queue_barrier(packet_processing_queue)
    await _await_queue_barrier(recording_queue)


async def _stop_active_recording() -> tuple[Optional[str], Optional[dict]]:
    global recording_active, current_session_id

    if not recording_active or not recorder:
        return None, None

    session_id = current_session_id
    try:
        await _drain_recording_pipeline()
    except Exception as exc:
        logger.warning('停止录制前排空后台队列失败，将继续执行收尾: %s', exc)

    session_info = recorder.get_session_info()
    await asyncio.to_thread(recorder.stop_recording)
    recording_active = False
    current_session_id = None
    return session_id, session_info


def on_udp_message_received(message: dict) -> None:
    _enqueue_processing_message(message)


async def send_pid_params_to_drone(pids_data: dict) -> dict:
    return await send_command_to_drone(CommandRequest(type='set_pids', params=pids_data))


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

        supported_commands = {
            'cmd_idx',
            'cmd_mission',
            'set_pids',
            'gcs_command',
            'waypoints_upload',
        }

        if command in supported_commands:
            result = await send_command_to_drone(CommandRequest(type=command, params=params))
            await websocket.send_json(result)
            return

        await websocket.send_json({
            'type': 'command_response',
            'command': command,
            'status': 'error',
            'message': f'WebSocket 指令未接入后端发送链路: {command}',
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
            await asyncio.to_thread(recorder.start_recording)
            recording_active = True
            current_session_id = session_id
            _append_session_communication_log(
                'recording_started',
                session_id=session_id,
                listen_ports=recorder.enabled_ports,
            )
            await manager.broadcast(_cache_ws_snapshot(
                _build_recording_status_payload(True, session_id, recorder.get_session_info()),
                'recording_status'
            ))
            return

        if action == 'stop' and recording_active and recorder:
            _append_session_communication_log(
                'recording_stopping',
                session_id=current_session_id,
            )
            last_session_id, session_info = await _stop_active_recording()
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


async def root() -> dict:
    return {
        'name': 'GCS Web Backend',
        'version': '1.0.0',
        'status': 'running',
    }


async def health_check() -> dict:
    return {
        'status': 'healthy',
        'websocket_connections': manager.get_connection_count(),
        'pipeline': _get_pipeline_status(),
        'traffic': _get_transport_runtime_stats(),
        'online_analysis': {
            'enabled': ONLINE_ANALYSIS_ENABLED,
            'mode': ONLINE_ANALYSIS_MODE,
            'base_url': ONLINE_ANALYSIS_BASE_URL,
            'project_root': ONLINE_ANALYSIS_PROJECT_ROOT,
            'last_forward_ok_at': online_analysis_runtime.get('last_forward_ok_at'),
            'last_error': online_analysis_runtime.get('last_error', ''),
        },
        'timestamp': int(time.time()),
    }


async def get_traffic_stats() -> dict:
    return {
        'type': 'traffic_stats',
        'data': _get_transport_runtime_stats(),
        'pipeline': _get_pipeline_status(),
        'timestamp': int(time.time() * 1000),
    }


async def websocket_endpoint(websocket: WebSocket) -> None:
    manager.cache_message(
        _build_udp_status_payload(
            bool(udp_handler and udp_handler.is_running()),
            connection_config,
            BACKEND_HTTP_ACCESS_HOST,
            BACKEND_HTTP_PORT,
        ),
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


async def get_log_config() -> dict:
    return {
        'type': 'log_config',
        'data': log_config.dict(),
        'timestamp': int(time.time() * 1000),
    }


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


async def start_udp_server() -> dict:
    global udp_handler, udp_server_started, heartbeat_task

    try:
        await _ensure_packet_processing_pipeline()

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

        await manager.broadcast(_cache_ws_snapshot(
            _build_udp_status_payload(True, connection_config, BACKEND_HTTP_ACCESS_HOST, BACKEND_HTTP_PORT),
            'udp_status_change',
        ))

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

        await manager.broadcast(_cache_ws_snapshot(
            _build_udp_status_payload(False, connection_config, BACKEND_HTTP_ACCESS_HOST, BACKEND_HTTP_PORT),
            'udp_status_change',
        ))
        return {'status': 'success', 'message': 'UDP服务器已停止'}
    except Exception as exc:
        logger.error('停止UDP服务器失败: %s', exc)
        raise HTTPException(status_code=500, detail=str(exc))


async def get_udp_status() -> dict:
    global udp_server_started

    is_actually_running = bool(udp_handler and udp_handler.is_running())
    udp_server_started = is_actually_running
    manager.cache_message(
        _build_udp_status_payload(is_actually_running, connection_config, BACKEND_HTTP_ACCESS_HOST, BACKEND_HTTP_PORT),
        'udp_status_change',
    )
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
            'pipeline': _get_pipeline_status(),
        },
    }

async def get_online_analysis_status() -> dict:
    return {
        'status': 'success',
        'data': {
            'enabled': ONLINE_ANALYSIS_ENABLED,
            'mode': ONLINE_ANALYSIS_MODE,
            'base_url': ONLINE_ANALYSIS_BASE_URL,
            'project_root': ONLINE_ANALYSIS_PROJECT_ROOT,
            'timeout_ms': ONLINE_ANALYSIS_TIMEOUT_MS,
            'last_forward_ok_at': online_analysis_runtime.get('last_forward_ok_at'),
            'last_error': online_analysis_runtime.get('last_error', ''),
            'last_snapshot': online_analysis_runtime.get('last_snapshot'),
        },
        'timestamp': int(time.time() * 1000),
    }


async def send_command_to_drone(request: CommandRequest) -> dict:
    try:
        command_type = request.type
        params = request.params
        packet = None
        channel = _runtime_resolve_command_channel(command_type)
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
                        response_message = (
                            f'指令{cmd_id}已按{int(COMMAND_SEND_MIN_INTERVAL_SEC * 1000)}ms间隔'
                            f'连续发送{CMD_IDX_REPEAT_COUNT}次，末次已置0'
                        )
                    else:
                        response_message = (
                            f'指令{cmd_id}已按{int(COMMAND_SEND_MIN_INTERVAL_SEC * 1000)}ms间隔'
                            f'连续发送{CMD_IDX_REPEAT_COUNT}次'
                        )
                else:
                    udp_handler.send_data(packet, target_host, target_port)
                    await _mark_command_sent(channel)
                    response_message = f'指令{cmd_id}已发送'
            elif command_type == 'gcs_command':
                for repeat_index in range(PLANNING_COMMAND_REPEAT_COUNT):
                    udp_handler.send_data(packet, target_host, target_port)
                    await _mark_command_sent(channel)
                    if repeat_index < PLANNING_COMMAND_REPEAT_COUNT - 1:
                        await asyncio.sleep(PLANNING_COMMAND_REPEAT_INTERVAL_SEC)

                response_message = (
                    f'规划任务已按{int(PLANNING_COMMAND_REPEAT_INTERVAL_SEC * 1000)}ms间隔'
                    f'连续发送{PLANNING_COMMAND_REPEAT_COUNT}次'
                )
            else:
                udp_handler.send_data(packet, target_host, target_port)
                await _mark_command_sent(channel)

            _append_session_communication_log(
                'uplink_command_sent',
                command_type=command_type,
                func_code=f'0x{(NCLINK_GCS_COMMAND if target_port == connection_config.planningSendPort else NCLINK_SEND_EXTU_FCS):02X}',
                target=f'{target_host}:{target_port}',
                bytes=len(packet),
                repeat_count=(
                    CMD_IDX_REPEAT_COUNT if command_type == 'cmd_idx' and 1 <= params.get('cmdId', 0) <= 25
                    else PLANNING_COMMAND_REPEAT_COUNT if command_type == 'gcs_command'
                    else 1
                ),
                reset_to_zero=bool(command_type == 'cmd_idx' and 1 <= params.get('cmdId', 0) <= 25 and CMD_IDX_RESET_TO_ZERO),
                params=_build_command_log_params(command_type, params),
            )

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


async def get_recording_status() -> dict:
    session_info = recorder.get_session_info() if recorder else None
    return _build_recording_status_payload(recording_active, current_session_id, session_info)


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
        await asyncio.to_thread(recorder.start_recording)
        recording_active = True
        current_session_id = session_id
        _append_session_communication_log(
            'recording_started',
            session_id=session_id,
            listen_ports=recorder.enabled_ports,
        )
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
        _append_session_communication_log(
            'recording_stopping',
            session_id=current_session_id,
        )
        session_id, session_info = await _stop_active_recording()

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


app.include_router(create_general_router(
    root_handler=root,
    health_handler=health_check,
    traffic_stats_handler=get_traffic_stats,
    websocket_handler=websocket_endpoint,
))

app.include_router(create_config_router(
    get_connection_config_handler=get_connection_config,
    update_connection_config_handler=update_connection_config,
    get_log_config_handler=get_log_config,
    update_log_config_handler=update_log_config,
    save_log_entry_handler=save_log_entry,
))

app.include_router(create_operations_router(
    start_udp_server_handler=start_udp_server,
    stop_udp_server_handler=stop_udp_server,
    get_udp_status_handler=get_udp_status,
    get_online_analysis_status_handler=get_online_analysis_status,
    send_command_handler=send_command_to_drone,
    get_recording_status_handler=get_recording_status,
    start_recording_handler=start_recording,
    stop_recording_handler=stop_recording,
))

manager.cache_message({
    'type': 'config_update',
    'config_type': 'connection',
    'data': connection_config.dict(),
    'timestamp': int(time.time() * 1000),
}, 'config_update:connection')

manager.cache_message(
    _build_online_analysis_config_payload(
        ONLINE_ANALYSIS_ENABLED,
        ONLINE_ANALYSIS_MODE,
        ONLINE_ANALYSIS_BASE_URL,
        ONLINE_ANALYSIS_PROJECT_ROOT,
        ONLINE_ANALYSIS_TIMEOUT_MS,
    ),
    'online_analysis_config'
)

manager.cache_message({
    'type': 'config_update',
    'config_type': 'log',
    'data': log_config.dict(),
    'timestamp': int(time.time() * 1000),
}, 'config_update:log')

manager.cache_message(
    _build_udp_status_payload(False, connection_config, BACKEND_HTTP_ACCESS_HOST, BACKEND_HTTP_PORT),
    'udp_status_change',
)

manager.cache_message(
    _build_recording_status_payload(False, None, {}),
    'recording_status'
)


@app.on_event('startup')
async def startup_event() -> None:
    global udp_handler, udp_server_started, heartbeat_task, command_send_lock

    logger.info('=' * 60)
    logger.info('Apollo GCS Web 后端启动（核心通信版）')
    logger.info('=' * 60)

    command_send_lock = asyncio.Lock()
    await _ensure_packet_processing_pipeline()

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
    global udp_server_started, heartbeat_task, recording_active, current_session_id

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

    if recorder and recording_active:
        try:
            await _stop_active_recording()
        except Exception as exc:
            logger.error('应用关闭时停止录制失败: %s', exc)

    await _stop_packet_processing_pipeline()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app,
        host=BACKEND_HTTP_HOST,
        port=BACKEND_HTTP_PORT,
        reload=False,
        log_level='info',
    )