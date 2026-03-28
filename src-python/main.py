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
import csv
import logging
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional
import json
import time
import uuid
import re
from collections import defaultdict, deque

from protocol.protocol_parser import UDPHandler, NCLinkUDPServerProtocol
from protocol.nclink_protocol import (
    PortType,
    encode_gcs_command,
    encode_command_packet,
    encode_waypoints_upload,
    encode_extu_fcs_from_dict,
    NCLINK_SEND_EXTU_FCS,
    NCLINK_GCS_COMMAND
)
from config import config
from websocket.websocket_manager import WebSocketManager
from recorder import RawDataRecorder, build_event_stream_paths, normalize_session_meta_for_thesis
from recorder.data_recorder import EVENT_HEADERS
from export import SessionStandardizer
from analysis import SessionDsmWorker, SessionEvaluationWorker, SessionOptimizationWorker
from calculator import RealTimeCalculator
from config import MappingConfig
from experiment import (
    ExperimentCaseManager,
    FlightTaskTracker,
    ScenarioResolver,
    build_task_snapshot,
    choose_candidate,
    derive_figure_semantics,
)
from recorder.csv_helper_full import (
    get_full_header, get_data_for_type
)

# ================================================================
# 数据模型
# ================================================================

class ConnectionConfig(BaseModel):
    """UDP连接配置"""
    protocol: str = "udp"
    listenAddress: str = "192.168.16.13"  # 监听地址（地面站本地IP）
    hostPort: int = 30509
    remoteIp: str = "192.168.16.116"      # 目标地址（飞控IP）
    commandRecvPort: int = 18504
    sendOnlyPort: int = 18506
    lidarSendPort: int = 18507
    planningSendPort: int = 18510
    planningRecvPort: int = 18511


def _build_fixed_connection_config() -> ConnectionConfig:
    """Return the only supported deployment topology for the current GCS setup."""
    udp_config = config.get_udp_config()
    return ConnectionConfig(
        protocol="udp",
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
    """Keep runtime state aligned with the fixed deployment topology."""
    global connection_config
    connection_config = _build_fixed_connection_config()
    return connection_config

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
    base_directory: str = ""
    case_id: str = ""
    plan_case_id: str = ""
    repeat_index: Optional[int] = None
    scenario_id: str = ""
    notes: str = ""
    figure_run_id: str = ""
    figure_batch_id: str = ""
    figure_batch_group: str = ""
    experiment_type: str = ""
    chapter_target: str = ""
    law_validation_scope: str = ""


class ExperimentCaseSelection(BaseModel):
    """实验 case 选择配置"""
    case_id: str = ""


class DsmAnalysisRequest(BaseModel):
    """DSM 分析请求"""
    session_id: str = ""
    session_dir: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class EvaluationAnalysisRequest(BaseModel):
    """架构评估请求"""
    session_id: str = ""
    session_dir: str = ""
    baseline_profile_id: str = ""
    candidate_profile_id: str = ""


class OptimizationAnalysisRequest(BaseModel):
    """架构优化请求"""
    session_id: str = ""
    session_dir: str = ""
    baseline_profile_id: str = ""
    current_profile_id: str = ""
    pop_size: int = 40
    n_gen: int = 40
    seed: int = 42


# ================================================================
# 全局配置和日志管理
# ================================================================

# 全局连接配置
connection_config = _build_fixed_connection_config()

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
command_send_lock = None
COMMAND_SEND_MIN_INTERVAL_SEC = 0.5
CMD_IDX_REPEAT_COUNT = 3
CMD_IDX_RESET_TO_ZERO = True
command_last_send_at = {
    'flight_control': 0.0,
    'planning': 0.0,
}
command_channel_busy = {
    'flight_control': False,
    'planning': False,
}

# PID参数缓存（用于cmd_idx指令，保持PID参数不变）
cached_pid_params = {
    'fKaPHI': 0.8, 'fKaP': 0.3, 'fKaY': 0.3, 'fIaY': 0.005,
    'fKaVy': 2.0, 'fIaVy': 0.4, 'fKaAy': 0.28,
    'fKeTHETA': 0.8, 'fKeQ': 0.3, 'fKeX': 0.3, 'fIeX': 0.01,
    'fKeVx': 2.0, 'fIeVx': 0.4, 'fKeAx': 0.55,
    'fKrR': 1.0, 'fIrR': 0.4, 'fKrAy': 0.0, 'fKrPSI': 1.0,
    'fKcH': 0.36, 'fIcH': 0.015, 'fKcHdot': 0.5, 'fIcHdot': 0.05,
    'fKcAz': 0.5, 'fIgRPM': 0.0, 'fKgRPM': 0.0, 'fScale_factor': 0.3,
    'XaccLMT': 1.0, 'YaccLMT': 1.0, 'Hground': 0.4, 'AutoTakeoffHcmd': 10.0
}

# 数据处理模块
recorder = None  # RawDataRecorder实例
calculator = RealTimeCalculator()  # 实时计算引擎
mapping_config = MappingConfig()  # 映射配置
dsm_worker = SessionDsmWorker(mapping_config=mapping_config)
evaluation_worker = SessionEvaluationWorker()
optimization_worker = SessionOptimizationWorker()

# 初始化指令发送锁
command_send_lock = asyncio.Lock()


def _resolve_command_channel(command_type: str) -> Optional[str]:
    """Map command types to the outbound hardware channel that needs throttling."""
    if command_type in {'cmd_idx', 'cmd_mission'}:
        return 'flight_control'
    if command_type in {'gcs_command', 'waypoints_upload'}:
        return 'planning'
    return None


async def _check_command_send_rate(command_type: str) -> Optional[dict]:
    """Reserve the outbound channel and reject overlapping or too-fast requests."""
    channel = _resolve_command_channel(command_type)
    if not channel:
        return None

    async with command_send_lock:
        if command_channel_busy.get(channel):
            logger.warning(f"发送通道忙，已拦截 {command_type} -> {channel}")
            return {
                "type": "command_response",
                "command": command_type,
                "status": "rate_limited",
                "message": "上一条同通道指令仍在发送，请等待当前发送窗口结束后重试",
                "timestamp": int(time.time() * 1000)
            }

        now = time.monotonic()
        last_sent = command_last_send_at.get(channel, 0.0)
        elapsed = now - last_sent

        if elapsed < COMMAND_SEND_MIN_INTERVAL_SEC:
            retry_after_ms = max(1, int((COMMAND_SEND_MIN_INTERVAL_SEC - elapsed) * 1000))
            logger.warning(
                f"发送过快，已拦截 {command_type} -> {channel}，"
                f"距上次发送仅 {elapsed * 1000:.0f}ms，需至少间隔 500ms"
            )
            return {
                "type": "command_response",
                "command": command_type,
                "status": "rate_limited",
                "message": f"发送过快，请至少间隔500ms，建议 {retry_after_ms}ms 后重试",
                "timestamp": int(time.time() * 1000)
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

# 录制状态
recording_active = False
current_session_id = None
THESIS_PRIMARY_PLAN_FILENAMES = (
    'generated_research_logic_plan_20260323.csv',
    'generated_research_logic_plan.csv',
    'thesis_research_logic_plan.csv',
)
DEFAULT_THESIS_PRIMARY_PLAN_FILENAME = THESIS_PRIMARY_PLAN_FILENAMES[0]
SESSION_ID_SCHEMA = 'YYYYMMDD_HHMMSS_CASE_XXX_APOLLO_RXX'
SESSION_ID_PATTERN = re.compile(
    r'^(?P<timestamp>\d{8}_\d{6})_(?P<plan_case_id>CASE_[A-Z0-9_]+)_APOLLO_R(?P<repeat_index>\d{2})$'
)
experiment_plan_path = os.path.join(current_dir, 'experiment', DEFAULT_THESIS_PRIMARY_PLAN_FILENAME)
experiment_plan_source_kind = 'missing'
architecture_config_dir = os.path.join(current_dir, 'experiment', 'architecture_configs')
experiment_plan_cases = []
experiment_case_lookup = {}
selected_plan_case_id = None
current_experiment_runtime = {}
last_standardization_result = None
last_dsm_result = None
last_evaluation_result = None
last_optimization_result = None
task_tracker = FlightTaskTracker(confirm_threshold=3)
scenario_resolver = ScenarioResolver()
experiment_case_manager = ExperimentCaseManager(experiment_plan_path, architecture_config_dir)


def _resolve_experiment_plan_source() -> tuple[str, str]:
    experiment_dir = os.path.join(current_dir, 'experiment')
    env_plan_path = str(os.getenv('APOLLO_THESIS_PLAN_PATH', '') or '').strip()
    candidate_paths = []

    if env_plan_path:
        candidate_paths.append((env_plan_path, 'thesis_primary'))

    for filename in THESIS_PRIMARY_PLAN_FILENAMES:
        candidate_paths.append((os.path.join(experiment_dir, filename), 'thesis_primary'))

    for candidate_path, source_kind in candidate_paths:
        if os.path.exists(candidate_path):
            return candidate_path, source_kind

    return os.path.join(experiment_dir, DEFAULT_THESIS_PRIMARY_PLAN_FILENAME), 'missing'


def _load_bundled_experiment_plan():
    global experiment_plan_cases, experiment_case_lookup, experiment_plan_path, experiment_plan_source_kind
    experiment_plan_path, experiment_plan_source_kind = _resolve_experiment_plan_source()
    experiment_case_manager.plan_path = experiment_plan_path
    if not os.path.exists(experiment_plan_path):
        logger.warning(
            "未找到 thesis 主实验方案文件，请将正式方案放入固定路径: %s",
            experiment_plan_path,
        )
        experiment_plan_cases = []
        experiment_case_lookup = {}
        return
    try:
        experiment_case_manager.reload()
        experiment_plan_cases = experiment_case_manager.cases
        experiment_case_lookup = experiment_case_manager.case_lookup
        logger.info(
            "已加载 thesis 主实验方案: %s cases, source=%s",
            len(experiment_plan_cases),
            experiment_plan_path,
        )
        logger.info(
            "已加载架构配置包: logical_functions=%s hardware=%s profiles=%s",
            len(experiment_case_manager.architecture_bundle.logical_functions) if experiment_case_manager.architecture_bundle else 0,
            len(experiment_case_manager.architecture_bundle.hardware_resources) if experiment_case_manager.architecture_bundle else 0,
            len(experiment_case_manager.architecture_bundle.allocation_profiles) if experiment_case_manager.architecture_bundle else 0,
        )
    except Exception as exc:
        logger.error(f"加载在线实验方案失败: {exc}")
        experiment_plan_cases = []
        experiment_case_lookup = {}


def _find_experiment_case(case_id: Optional[str] = None):
    experiment_case_manager.selected_case_id = selected_plan_case_id
    return experiment_case_manager.find_case(case_id)


def _serialize_experiment_case(planned_case) -> dict:
    return experiment_case_manager.serialize_case(planned_case)


def _build_recording_meta_patch(
    planned_case = None,
    case_id: Optional[str] = None,
    repeat_index: Optional[int] = None,
    scenario_id: Optional[str] = None,
    notes: str = '',
    *,
    experiment_type: Optional[str] = None,
    figure_run_id: Optional[str] = None,
    figure_batch_id: Optional[str] = None,
    figure_batch_group: Optional[str] = None,
    chapter_target: Optional[str] = None,
    law_validation_scope: Optional[str] = None,
    analysis_run_id: Optional[str] = None,
) -> dict:
    patch = experiment_case_manager.build_recording_meta_patch(
        planned_case,
        case_id=case_id,
        repeat_index=repeat_index,
        scenario_id=scenario_id,
        notes=notes,
        experiment_type=experiment_type,
        figure_run_id=figure_run_id,
        figure_batch_id=figure_batch_id,
        figure_batch_group=figure_batch_group,
        chapter_target=chapter_target,
        law_validation_scope=law_validation_scope,
        analysis_run_id=analysis_run_id,
    )
    patch['experiment_plan_source'] = experiment_plan_source_kind
    patch['experiment_plan_path'] = experiment_plan_path
    patch['session_id_schema'] = SESSION_ID_SCHEMA
    return patch


def _sanitize_session_id_token(value: Optional[object], fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    sanitized = ''.join(ch if ch.isalnum() else '_' for ch in text)
    sanitized = sanitized.strip('_')
    return sanitized or fallback


def _normalize_plan_case_id(value: Optional[object]) -> str:
    token = _sanitize_session_id_token(value, 'CASE_ADHOC').upper()
    if not token.startswith('CASE_'):
        token = f'CASE_{token}'
    return token


def _normalize_repeat_index(value: Optional[object]) -> int:
    try:
        if value is None or value == '':
            return 0
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _parse_session_id(session_id: str) -> Optional[dict]:
    match = SESSION_ID_PATTERN.match(str(session_id or '').strip())
    if not match:
        return None
    return {
        'timestamp': match.group('timestamp'),
        'plan_case_id': match.group('plan_case_id'),
        'repeat_index': int(match.group('repeat_index')),
    }


def _validate_session_id_contract(
    session_id: str,
    *,
    plan_case_id: Optional[str] = None,
    repeat_index: Optional[int] = None,
) -> dict:
    parsed = _parse_session_id(session_id)
    if parsed is None:
        raise ValueError(f'session_id 必须符合 {SESSION_ID_SCHEMA}')

    expected_plan_case_id = _normalize_plan_case_id(plan_case_id) if plan_case_id else None
    if expected_plan_case_id and parsed['plan_case_id'] != expected_plan_case_id:
        raise ValueError(
            f"session_id 中的 case 段为 {parsed['plan_case_id']}，但 plan_case_id 为 {expected_plan_case_id}"
        )

    if repeat_index is not None:
        expected_repeat_index = _normalize_repeat_index(repeat_index)
        if parsed['repeat_index'] != expected_repeat_index:
            raise ValueError(
                f"session_id 中的 repeat 段为 R{parsed['repeat_index']:02d}，但 repeat_index 为 R{expected_repeat_index:02d}"
            )

    return parsed


def _build_session_id(
    planned_case = None,
    *,
    case_id: Optional[str] = None,
    repeat_index: Optional[int] = None,
    is_auto: bool = False,
) -> str:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    del is_auto
    case_token = _normalize_plan_case_id(getattr(planned_case, 'case_id', None) or case_id or selected_plan_case_id)
    resolved_repeat_index = _normalize_repeat_index(
        getattr(planned_case, 'repeat_index', None) if planned_case is not None else repeat_index
    )
    return f'{timestamp}_{case_token}_APOLLO_R{resolved_repeat_index:02d}'


def _build_contract_event(
    *,
    session_id: Optional[str],
    case_id: Optional[str],
    event_type: str,
    event_source: str,
    event_level: str = 'info',
    event_value: object = '',
    event_detail: str = '',
    mission_phase: str = '',
    scenario_id: str = '',
    architecture_id: str = '',
    effective_task: str = '',
    scenario_evidence_tags = None,
) -> dict:
    return {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
        'session_id': session_id or '',
        'case_id': case_id or '',
        'mission_phase': mission_phase,
        'scenario_id': scenario_id,
        'architecture_id': architecture_id,
        'effective_task': effective_task,
        'scenario_evidence_tags': list(scenario_evidence_tags or []),
        'event_type': event_type,
        'event_source': event_source,
        'event_level': event_level,
        'event_value': event_value,
        'event_detail': event_detail,
    }


def _append_session_event(session_info: Optional[dict], event: dict) -> None:
    session_dir = (session_info or {}).get('data_directory')
    if not session_dir:
        return
    event_paths = build_event_stream_paths(session_dir)
    event_row = [
        event.get('timestamp', ''),
        event.get('session_id', ''),
        event.get('case_id', ''),
        event.get('event_type', ''),
        event.get('event_source', ''),
        event.get('event_level', 'info'),
        event.get('event_value', ''),
        event.get('event_detail', ''),
        event.get('mission_phase', ''),
        event.get('scenario_id', ''),
        event.get('architecture_id', ''),
        event.get('effective_task', ''),
        '|'.join(event.get('scenario_evidence_tags', [])),
    ]
    for event_path in dict.fromkeys(event_paths.values()):
        os.makedirs(os.path.dirname(event_path), exist_ok=True)
        write_header = not os.path.exists(event_path) or os.path.getsize(event_path) == 0
        with open(event_path, 'a', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            if write_header:
                writer.writerow(EVENT_HEADERS)
            writer.writerow(event_row)


def _record_session_event(session_info: Optional[dict], event: dict) -> None:
    if recorder and getattr(recorder, 'is_recording', False):
        recorder.record_event(event)
        return
    _append_session_event(session_info, event)


def _build_runtime_event_defaults(session_info: Optional[dict] = None) -> dict:
    runtime_context = {}
    if recorder and isinstance(getattr(recorder, 'runtime_context', None), dict):
        runtime_context = recorder.runtime_context
    elif session_info and isinstance(session_info.get('runtime_context'), dict):
        runtime_context = session_info.get('runtime_context', {})

    task_context = runtime_context.get('task', {}) if isinstance(runtime_context, dict) else {}
    scenario_context = runtime_context.get('scenario', {}) if isinstance(runtime_context, dict) else {}
    architecture_context = runtime_context.get('architecture', {}) if isinstance(runtime_context, dict) else {}

    return {
        'mission_phase': task_context.get('phase', ''),
        'scenario_id': scenario_context.get('scenario_id', 'scenario_default'),
        'architecture_id': architecture_context.get('architecture_id', ''),
        'effective_task': task_context.get('task_name', ''),
        'scenario_evidence_tags': scenario_context.get('heuristic_tags', []),
    }


def _record_pipeline_stage_event(session_info: Optional[dict], stage_name: str, stage_result: Optional[dict]) -> None:
    runtime_defaults = _build_runtime_event_defaults(session_info)
    status = _map_pipeline_stage_status((stage_result or {}).get('status', 'waiting')) if isinstance(stage_result, dict) else 'waiting'
    detail_parts = []
    if isinstance(stage_result, dict):
        error_message = stage_result.get('error') or stage_result.get('error_message')
        if error_message:
            detail_parts.append(str(error_message))
        summary = stage_result.get('summary') or {}
        if isinstance(summary, dict) and summary:
            detail_parts.append(json.dumps(summary, ensure_ascii=False, separators=(',', ':')))

    event_level = 'info'
    if status == 'blocked':
        event_level = 'warning'
    elif status == 'failed':
        event_level = 'error'

    _record_session_event(
        session_info,
        _build_contract_event(
            session_id=(session_info or {}).get('session_id'),
            case_id=(session_info or {}).get('case_id'),
            event_type='pipeline_status_change',
            event_source=stage_name,
            event_level=event_level,
            event_value=status,
            event_detail=' | '.join(detail_parts) if detail_parts else f'{stage_name} -> {status}',
            **runtime_defaults,
        ),
    )


def _build_ad_hoc_runtime_payload(task_snapshot, scenario_context, session_meta: Optional[dict] = None, case_id: Optional[str] = None):
    candidate = choose_candidate(task_snapshot, scenario_context, None)
    session_meta = dict(session_meta or {})
    figure_semantics = derive_figure_semantics(
        None,
        case_id=case_id or session_meta.get('plan_case_id') or session_meta.get('case_id'),
        experiment_type=session_meta.get('experiment_type'),
        figure_run_id=session_meta.get('figure_run_id'),
        figure_batch_id=session_meta.get('figure_batch_id'),
        figure_batch_group=session_meta.get('figure_batch_group'),
        chapter_target=session_meta.get('chapter_target'),
        law_validation_scope=session_meta.get('law_validation_scope'),
    )
    return {
        'case': {
            'case_id': session_meta.get('plan_case_id') or selected_plan_case_id or '',
            'repeat_index': session_meta.get('repeat_index'),
            'duration_sec': None,
            'evaluation_window_sec': None,
            'recording_case_id': getattr(recorder, 'case_id', None) if recorder else None,
            **figure_semantics,
        },
        'task': {
            'planned_cmd_idx': task_snapshot.desired_cmd_id,
            'effective_cmd_idx': task_snapshot.effective_cmd_id,
            'mission_id': task_snapshot.mission_id,
            'task_name': task_snapshot.display_name,
            'task_group': task_snapshot.task_group,
            'phase': task_snapshot.mission_phase,
            'source': task_snapshot.source,
        },
        'scenario': {
            'scenario_id': scenario_context.scenario_id,
            'display_name': scenario_context.display_name,
            'source': scenario_context.source,
            'confidence': scenario_context.confidence,
            'environment_class': scenario_context.environment_class,
            'disturbance_tags': list(scenario_context.disturbance_tags),
            'heuristic_tags': list(scenario_context.heuristic_tags),
        },
        'architecture': {
            'architecture_id': candidate.architecture_id,
            'display_name': candidate.display_name,
            'mapping_profile': candidate.mapping_profile,
            'adaptation_mode': candidate.adaptation_mode,
            'focus': candidate.focus,
        },
        'figure_semantics': figure_semantics,
        'architecture_profiles': experiment_case_manager.list_architecture_profiles(),
        'trigger_policy': '',
    }


def _refresh_experiment_runtime(message: Optional[dict] = None, latest_metrics: Optional[dict] = None, planned_case = None) -> dict:
    global current_experiment_runtime

    if message and isinstance(message, dict):
        task_snapshot = build_task_snapshot(message.get('type', ''), message.get('data', {}) or {}, task_tracker)
    else:
        task_snapshot = task_tracker.update()

    active_case = planned_case or _find_experiment_case(getattr(recorder, 'plan_case_id', None) if recorder else None)
    session_meta = getattr(recorder, 'session_meta_patch', {}) if recorder else {}
    scenario_context = scenario_resolver.resolve(
        case_row=_serialize_experiment_case(active_case) if active_case is not None else None,
        session_meta=session_meta,
        latest_metrics=latest_metrics or {},
    )

    if active_case is not None:
        runtime_payload = experiment_case_manager.build_runtime_payload(
            active_case,
            task_snapshot,
            scenario_context,
            recording_case_id=getattr(recorder, 'case_id', None) if recorder else None,
        )
    else:
        runtime_payload = _build_ad_hoc_runtime_payload(
            task_snapshot,
            scenario_context,
            session_meta=session_meta,
            case_id=getattr(recorder, 'case_id', None) if recorder else None,
        )

    current_experiment_runtime = runtime_payload
    if recorder:
        recorder.set_runtime_context(runtime_payload)
    return runtime_payload


_load_bundled_experiment_plan()

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
}

VIEW_INTERVALS = {
    'flight_state_update': 0.10,
    'planning_state_update': 0.10,
    'system_performance_update': 0.50,
    'experiment_context_update': 0.50,
    'capture_overview_update': 1.00,
    'data_quality_update': 1.00,
    'window_metrics_record': 1.00,
}

WS_SOURCE = 'apollo_backend'
WS_SCHEMA_VERSION = 'v1.0'

capture_stats = {
    'recent_packets': defaultdict(lambda: deque(maxlen=120)),
    'family_last_ts': {},
    'family_packet_counts': defaultdict(int),
    'parse_error_count': 0,
    'window_missing_count': 0,
    'last_packet_ts': None,
    'last_error': ''
}

REQUIRED_STANDARD_FILES = ['fcs_telemetry', 'planning_telemetry', 'radar_data', 'bus_traffic']
OPTIONAL_STANDARD_FILES = ['camera_data']
ALL_STANDARD_FILES = REQUIRED_STANDARD_FILES + OPTIONAL_STANDARD_FILES


def _normalize_listen_ports() -> list:
    """构建实际监听端口列表，优先覆盖协议定义端口，保留历史联调端口。"""
    ports = [
        connection_config.sendOnlyPort,
        connection_config.lidarSendPort,
        connection_config.planningRecvPort,
    ]

    if connection_config.hostPort not in ports:
        ports.append(connection_config.hostPort)

    seen = set()
    ordered_ports = []
    for port in ports:
        if port and port not in seen:
            seen.add(port)
            ordered_ports.append(port)
    return ordered_ports


def _should_broadcast_packet(msg_type: str, func_code: int, current_time: float) -> bool:
    """按协议包类型控制广播频率，保证监控流畅且不过载。"""
    key = msg_type or f'func_{func_code:02X}'
    interval = BROADCAST_INTERVALS.get(msg_type)

    if interval is None and func_code:
        if 0x41 <= func_code <= 0x44:
            interval = 0.05
        elif 0x45 <= func_code <= 0x4B:
            interval = 0.10
        elif 0x50 <= func_code <= 0x53:
            interval = 0.10
        else:
            interval = 0.0

    if interval is None:
        interval = 0.0

    if interval <= 0:
        return True

    last_time = last_broadcast_times.get(key, 0)
    if current_time - last_time < interval:
        return False

    last_broadcast_times[key] = current_time
    return True


def _should_emit_named_update(update_type: str, current_time: float) -> bool:
    interval = VIEW_INTERVALS.get(update_type, 0.0)
    if interval <= 0:
        return True
    last_time = last_broadcast_times.get(update_type, 0.0)
    if current_time - last_time < interval:
        return False
    last_broadcast_times[update_type] = current_time
    return True


def _build_recording_status_payload(is_active: bool, session_id: Optional[str], session_info: Optional[dict] = None) -> dict:
    timestamp = int(time.time() * 1000)
    case_id = (session_info or {}).get('case_id')
    duration_sec = 0.0
    if is_active and session_info and session_info.get('start_time'):
        duration_sec = max(0.0, time.time() - float(session_info.get('start_time')))
    elif session_info:
        duration_sec = float(session_info.get('duration') or 0.0)

    return _build_ws_payload(
        'recording_status',
        session_id=session_id,
        case_id=case_id,
        timestamp=timestamp,
        data={
            'recording': is_active,
            'duration_sec': round(duration_sec, 3),
            'output_dir': (session_info or {}).get('data_directory', ''),
            'bytes_written': (session_info or {}).get('total_bytes', 0),
            'last_error': capture_stats.get('last_error', '')
        },
        extra={
            'is_active': is_active,
            'session_info': session_info,
            'experiment_context': current_experiment_runtime,
            'pipeline_status': _build_pipeline_status_data(is_active, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result),
        }
    )


def _worker_status(result, default: str = 'waiting') -> str:
    if isinstance(result, dict):
        return result.get('status') or result.get('worker_status') or default
    return default


def _worker_error_code(result) -> str:
    if isinstance(result, dict):
        return result.get('error_code', '') or ''
    return ''


def _worker_error_message(result) -> str:
    if isinstance(result, dict):
        return result.get('error', '') or result.get('error_message', '') or ''
    return ''


def _map_pipeline_stage_status(value: Optional[str]) -> str:
    normalized = str(value or '').strip().lower()
    if normalized in {'running', 'ready', 'failed', 'blocked', 'waiting'}:
        return normalized
    if normalized in {'pending', 'planned'}:
        return 'waiting'
    return 'waiting'


def _persist_pipeline_status(session_info: Optional[dict], pipeline_status: dict) -> None:
    session_dir = (session_info or {}).get('data_directory')
    if not session_dir:
        return
    analysis_dir = os.path.join(session_dir, 'analysis')
    os.makedirs(analysis_dir, exist_ok=True)
    with open(os.path.join(analysis_dir, 'pipeline_status.json'), 'w', encoding='utf-8') as handle:
        json.dump(pipeline_status, handle, ensure_ascii=False, indent=2)
    _persist_figure_batch_manifest(session_info, pipeline_status)


def _collect_figure_context(session_info: Optional[dict], session_meta: Optional[dict] = None) -> dict:
    session_info = dict(session_info or {})
    session_meta = dict(session_meta or {})

    runtime_context = {}
    if isinstance(session_meta.get('runtime_context'), dict):
        runtime_context = session_meta.get('runtime_context', {})
    elif isinstance(session_info.get('runtime_context'), dict):
        runtime_context = session_info.get('runtime_context', {})

    case_context = runtime_context.get('case', {}) if isinstance(runtime_context, dict) else {}
    figure_context = runtime_context.get('figure_semantics', {}) if isinstance(runtime_context, dict) else {}
    if not figure_context and isinstance(case_context, dict):
        figure_context = {
            'figure_run_id': case_context.get('figure_run_id'),
            'figure_batch_id': case_context.get('figure_batch_id'),
            'figure_batch_group': case_context.get('figure_batch_group'),
            'figure_ledger_range': case_context.get('figure_ledger_range'),
            'experiment_type': case_context.get('experiment_type'),
            'chapter_target': case_context.get('chapter_target'),
            'law_validation_scope': case_context.get('law_validation_scope'),
        }

    return {
        'figure_run_id': session_meta.get('figure_run_id') or figure_context.get('figure_run_id') or session_info.get('figure_run_id') or '',
        'figure_batch_id': session_meta.get('figure_batch_id') or figure_context.get('figure_batch_id') or session_info.get('figure_batch_id') or '',
        'figure_batch_group': session_meta.get('figure_batch_group') or figure_context.get('figure_batch_group') or session_info.get('figure_batch_group') or '',
        'figure_ledger_range': session_meta.get('figure_ledger_range') or figure_context.get('figure_ledger_range') or session_info.get('figure_ledger_range') or '',
        'experiment_type': session_meta.get('experiment_type') or figure_context.get('experiment_type') or session_info.get('experiment_type') or '',
        'chapter_target': session_meta.get('chapter_target') or figure_context.get('chapter_target') or session_info.get('chapter_target') or '',
        'law_validation_scope': session_meta.get('law_validation_scope') or figure_context.get('law_validation_scope') or session_info.get('law_validation_scope') or '',
        'analysis_run_id': session_meta.get('analysis_run_id') or session_info.get('analysis_run_id') or session_info.get('session_id') or '',
    }


def _build_figure_batch_manifest(session_info: Optional[dict], pipeline_status: Optional[dict] = None) -> Optional[dict]:
    session_dir = (session_info or {}).get('data_directory')
    if not session_dir:
        return None

    meta_path = os.path.join(session_dir, 'session_meta.json')
    session_meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as handle:
                session_meta = json.load(handle)
        except Exception:
            session_meta = {}

    merged_figure_context = _collect_figure_context(session_info, session_meta)

    analysis_dir = os.path.join(session_dir, 'analysis')
    artifact_paths = {
        'pipeline_status': os.path.join(analysis_dir, 'pipeline_status.json'),
        'dsm_report': os.path.join(analysis_dir, 'dsm_report.json'),
        'evaluation_result': os.path.join(analysis_dir, 'evaluation_result.json'),
        'optimization_result': os.path.join(analysis_dir, 'optimization_result.json'),
        'optimization_comparison': os.path.join(analysis_dir, 'optimization_comparison.json'),
        'pareto_front': os.path.join(analysis_dir, 'pareto_front.csv'),
    }
    existing_artifact_paths = {
        key: path for key, path in artifact_paths.items() if os.path.exists(path)
    }

    effective_pipeline_status = pipeline_status or {}
    figure_asset_status = str(effective_pipeline_status.get('figure_asset_status') or '').strip().lower()
    if not figure_asset_status:
        figure_asset_status = 'ready' if (
            effective_pipeline_status.get('standard_files_status') == 'ready'
            and effective_pipeline_status.get('evaluation_status') == 'ready'
            and effective_pipeline_status.get('optimization_status') == 'ready'
        ) else 'blocked'
    figure_asset_ready = figure_asset_status == 'ready'

    return {
        'session_id': (session_info or {}).get('session_id') or session_meta.get('session_id') or os.path.basename(session_dir),
        'case_id': (session_info or {}).get('case_id') or session_meta.get('case_id') or '',
        'plan_case_id': (session_info or {}).get('plan_case_id') or session_meta.get('plan_case_id') or '',
        **merged_figure_context,
        'figure_asset_status': figure_asset_status,
        'figure_asset_ready': figure_asset_ready,
        'pipeline_status': effective_pipeline_status,
        'artifact_paths': existing_artifact_paths,
        'generated_at': int(time.time() * 1000),
    }


def _persist_figure_batch_manifest(session_info: Optional[dict], pipeline_status: Optional[dict] = None) -> None:
    session_dir = (session_info or {}).get('data_directory')
    if not session_dir:
        return

    manifest = _build_figure_batch_manifest(session_info, pipeline_status)
    if manifest is None:
        return

    analysis_dir = os.path.join(session_dir, 'analysis')
    os.makedirs(analysis_dir, exist_ok=True)
    manifest_path = os.path.join(analysis_dir, 'figure_batch_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)


def _update_session_meta_status(
    session_info: Optional[dict],
    *,
    standardization_result = None,
    dsm_result = None,
    evaluation_result = None,
    optimization_result = None,
) -> None:
    session_dir = (session_info or {}).get('data_directory')
    if not session_dir:
        return
    meta_path = os.path.join(session_dir, 'session_meta.json')
    if not os.path.exists(meta_path):
        return
    try:
        with open(meta_path, 'r', encoding='utf-8') as handle:
            meta = json.load(handle)
    except Exception:
        meta = {}

    pipeline = _build_pipeline_status_data(
        False,
        session_info,
        standardization_result,
        dsm_result,
        evaluation_result,
        optimization_result,
    )
    meta.update({
        'contract_version': pipeline.get('contract_version', 'v1.0'),
        'platform_type': meta.get('platform_type') or 'apollo_online',
        'record_start_ts': meta.get('record_start_ts', meta.get('start_ts')),
        'record_stop_ts': meta.get('record_stop_ts', meta.get('end_ts')),
        'standardization_status': pipeline.get('standardization', 'waiting'),
        'dsm_status': pipeline.get('dsm', 'waiting'),
        'evaluation_status': pipeline.get('evaluation', 'waiting'),
        'optimization_status': pipeline.get('optimization', 'waiting'),
        'figure_asset_status': pipeline.get('figure_asset_status', 'blocked'),
        'figure_asset_ready': pipeline.get('figure_asset_ready', False),
        'figure_batch_manifest_path': os.path.join(session_dir, 'analysis', 'figure_batch_manifest.json'),
    })
    if isinstance(evaluation_result, dict):
        meta['baseline_allocation_id'] = evaluation_result.get('baseline_allocation_id', meta.get('baseline_allocation_id', ''))
        meta['candidate_allocation_id'] = evaluation_result.get('candidate_allocation_id', meta.get('candidate_allocation_id', ''))
    if isinstance(optimization_result, dict):
        meta['baseline_allocation_id'] = optimization_result.get('baseline_allocation_id', meta.get('baseline_allocation_id', ''))
        meta['current_allocation_id'] = optimization_result.get('current_allocation_id', meta.get('current_allocation_id', ''))
        meta['recommended_allocation_id'] = optimization_result.get('recommended_allocation_id', meta.get('recommended_allocation_id', ''))
    meta['session_directory'] = session_dir
    meta = normalize_session_meta_for_thesis(meta)
    with open(meta_path, 'w', encoding='utf-8') as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)


def _build_pipeline_status_data(is_active: bool, session_info: Optional[dict], standardization_result = None, dsm_result = None, evaluation_result = None, optimization_result = None) -> dict:
    file_status = {}
    required_files = list(REQUIRED_STANDARD_FILES)
    optional_files = list(OPTIONAL_STANDARD_FILES)
    effective_input_weights = {}
    if isinstance(standardization_result, dict):
        file_status = standardization_result.get('file_status', {})
        required_files = list(standardization_result.get('required_files') or required_files)
        optional_files = list(standardization_result.get('optional_files') or optional_files)
        effective_input_weights = dict(standardization_result.get('effective_input_weights') or {})
    elif standardization_result is not None:
        file_status = getattr(standardization_result, 'file_status', {}) or {}
        required_files = list(getattr(standardization_result, 'required_files', required_files) or required_files)
        optional_files = list(getattr(standardization_result, 'optional_files', optional_files) or optional_files)
        effective_input_weights = dict(getattr(standardization_result, 'effective_input_weights', {}) or {})

    standard_files_ready = all(
        file_status.get(key) == 'ready'
        for key in required_files
    ) if file_status else False
    real_input_files_ready = any(
        file_status.get(key) == 'ready'
        for key in [*required_files, *optional_files]
    ) if file_status else False
    standard_files_empty = any(
        file_status.get(key) == 'empty'
        for key in ALL_STANDARD_FILES
    ) if file_status else False
    optional_files_empty = any(
        file_status.get(key) == 'empty'
        for key in optional_files
    ) if file_status else False

    standardization_success = True
    if isinstance(standardization_result, dict):
        standardization_success = bool(standardization_result.get('success', True))
    standardization_failed = any(value == 'failed' for value in file_status.values()) if file_status else False

    standardization_stage = 'waiting'
    if isinstance(standardization_result, dict):
        if standardization_failed or not standardization_success:
            standardization_stage = 'failed'
        elif real_input_files_ready:
            standardization_stage = 'ready'
        else:
            standardization_stage = 'waiting'
    elif is_active:
        standardization_stage = 'waiting'
    elif session_info:
        standardization_stage = 'waiting'

    def _map_status(value: Optional[str]) -> str:
        if value == 'ready':
            return 'ready'
        if value == 'empty':
            return 'empty'
        if value == 'failed':
            return 'failed'
        return 'missing'

    dsm_status = 'waiting'
    if isinstance(dsm_result, dict):
        dsm_status = _map_pipeline_stage_status(dsm_result.get('status', dsm_status))
    elif is_active:
        dsm_status = 'waiting'
    elif session_info and not real_input_files_ready:
        dsm_status = 'blocked'

    evaluation_status = 'waiting'
    if isinstance(evaluation_result, dict):
        evaluation_status = _map_pipeline_stage_status(evaluation_result.get('status', evaluation_status))
    elif dsm_status in {'failed', 'blocked'}:
        evaluation_status = 'blocked'

    optimization_status = 'waiting'
    if isinstance(optimization_result, dict):
        optimization_status = _map_pipeline_stage_status(optimization_result.get('status', optimization_status))
    elif evaluation_status in {'failed', 'blocked'}:
        optimization_status = 'blocked'

    if real_input_files_ready and standardization_success and evaluation_status == 'ready' and optimization_status == 'ready':
        figure_asset_status = 'ready'
    elif any(status == 'failed' for status in [dsm_status, evaluation_status, optimization_status]) or standardization_failed:
        figure_asset_status = 'failed'
    elif any(status == 'blocked' for status in [dsm_status, evaluation_status, optimization_status]) or (session_info and not real_input_files_ready):
        figure_asset_status = 'blocked'
    else:
        figure_asset_status = 'waiting'

    payload = {
        'contract_version': 'v1.0',
        'raw_recording': 'running' if is_active else ('ready' if session_info else 'waiting'),
        'standardization': standardization_stage,
        'dsm': dsm_status,
        'evaluation': evaluation_status,
        'optimization': optimization_status,
        'archive': 'waiting',
        'last_error_code': _worker_error_code(optimization_result) or _worker_error_code(evaluation_result) or _worker_error_code(dsm_result),
        'last_error_message': _worker_error_message(optimization_result) or _worker_error_message(evaluation_result) or _worker_error_message(dsm_result),
        'expected_standard_files': list(ALL_STANDARD_FILES),
        'required_standard_files': list(required_files),
        'optional_standard_files': list(optional_files),
        'real_input_files_ready': sorted([key for key, value in file_status.items() if value == 'ready']),
        'ready_standard_files': sorted([key for key, value in file_status.items() if value == 'ready']),
        'empty_standard_files': sorted([key for key, value in file_status.items() if value == 'empty']),
        'optional_empty_standard_files': sorted([key for key in optional_files if file_status.get(key) == 'empty']),
        'failed_standard_files': sorted([key for key, value in file_status.items() if value == 'failed']),
        'effective_input_weights': effective_input_weights,
    }

    payload.update({
        'raw_recording_status': 'running' if is_active else ('ready' if session_info else 'waiting'),
        'standard_files_status': (
            'ready'
            if real_input_files_ready and standardization_success
            else ('empty' if standard_files_empty else ('missing' if session_info else 'waiting'))
        ),
        'standard_files_completeness': (
            'complete'
            if standard_files_ready
            else ('partial' if real_input_files_ready else ('empty' if standard_files_empty else ('missing' if session_info else 'waiting')))
        ),
        'optional_inputs_status': 'empty' if optional_files_empty else 'ready',
        'dsm_status': dsm_status,
        'evaluation_status': evaluation_status,
        'optimization_status': optimization_status,
        'archive_status': payload['archive'],
        'figure_asset_status': figure_asset_status,
        'figure_asset_ready': (
            figure_asset_status == 'ready'
        ),
        'figure_batch_manifest_path': (
            os.path.join((session_info or {}).get('data_directory', ''), 'analysis', 'figure_batch_manifest.json')
            if session_info and session_info.get('data_directory') else ''
        ),
        'standard_files': {
            'fcsTelemetry': _map_status(file_status.get('fcs_telemetry')),
            'planningTelemetry': _map_status(file_status.get('planning_telemetry')),
            'radarData': _map_status(file_status.get('radar_data')),
            'busTraffic': _map_status(file_status.get('bus_traffic')),
            'cameraData': _map_status(file_status.get('camera_data')),
        },
    })
    return payload


def _build_pipeline_status_payload(is_active: bool, session_id: Optional[str], session_info: Optional[dict], standardization_result = None, dsm_result = None, evaluation_result = None, optimization_result = None) -> dict:
    return _build_ws_payload(
        'pipeline_status_update',
        session_id=session_id,
        case_id=(session_info or {}).get('case_id') if session_info else None,
        data=_build_pipeline_status_data(is_active, session_info, standardization_result, dsm_result, evaluation_result, optimization_result),
    )


def _run_session_standardization(session_info: Optional[dict]) -> Optional[dict]:
    if not session_info or not session_info.get('data_directory'):
        return None

    result = SessionStandardizer(session_info['data_directory']).export()
    return {
        'session_dir': result.session_dir,
        'success': result.success,
        'standard_files': result.standard_files,
        'file_status': result.file_status,
        'generated_files': result.generated_files,
        'missing_inputs': result.missing_inputs,
        'notes': result.notes,
        'required_files': result.required_files,
        'optional_files': result.optional_files,
        'configured_input_weights': result.configured_input_weights,
        'effective_input_weights': result.effective_input_weights,
    }


def _standard_files_exist(session_dir: str) -> bool:
    expected_files = {
        'fcs_telemetry.csv': [
            os.path.join(session_dir, 'records', 'fcs', 'fcs_telemetry.csv'),
            os.path.join(session_dir, 'fcs_telemetry.csv'),
            os.path.join(session_dir, 'analysis', 'standardized', 'fcs_telemetry.csv'),
        ],
        'planning_telemetry.csv': [
            os.path.join(session_dir, 'records', 'planning', 'planning_telemetry.csv'),
            os.path.join(session_dir, 'planning_telemetry.csv'),
            os.path.join(session_dir, 'analysis', 'standardized', 'planning_telemetry.csv'),
        ],
        'radar_data.csv': [
            os.path.join(session_dir, 'records', 'lidar', 'radar_data.csv'),
            os.path.join(session_dir, 'radar_data.csv'),
            os.path.join(session_dir, 'analysis', 'standardized', 'radar_data.csv'),
        ],
        'bus_traffic.csv': [
            os.path.join(session_dir, 'records', 'bus', 'bus_traffic.csv'),
            os.path.join(session_dir, 'bus_traffic.csv'),
            os.path.join(session_dir, 'analysis', 'standardized', 'bus_traffic.csv'),
        ],
    }
    for candidates in expected_files.values():
        file_path = next((candidate for candidate in candidates if os.path.exists(candidate)), None)
        if not file_path:
            continue
        with open(file_path, 'r', encoding='utf-8', newline='') as csv_file:
            next(csv_file, None)
            if next(csv_file, None) is not None:
                return True
    return False


def _run_session_dsm(session_info: Optional[dict], standardization_result = None, start_time: Optional[float] = None, end_time: Optional[float] = None) -> Optional[dict]:
    if not session_info or not session_info.get('data_directory'):
        return None

    session_dir = session_info['data_directory']
    dsm_input_ready = False
    if isinstance(standardization_result, dict):
        file_status = standardization_result.get('file_status', {}) or {}
        monitored_files = [
            *(standardization_result.get('required_files') or REQUIRED_STANDARD_FILES),
            *(standardization_result.get('optional_files') or OPTIONAL_STANDARD_FILES),
        ]
        dsm_input_ready = any(file_status.get(key) == 'ready' for key in monitored_files)
    else:
        dsm_input_ready = _standard_files_exist(session_dir)

    if not dsm_input_ready:
        return {
            'success': False,
            'status': 'blocked',
            'session_dir': session_dir,
            'output_path': '',
            'canonical_report_path': os.path.join(session_dir, 'analysis', 'dsm_report.json'),
            'summary': {},
            'error': '未检测到任何真实记录数据，DSM 未触发',
            'start_time': start_time,
            'end_time': end_time,
        }

    return dsm_worker.run_for_session(
        session_dir,
        start_time=start_time,
        end_time=end_time,
    ).as_dict()


def _run_session_evaluation(session_info: Optional[dict], dsm_result = None, baseline_profile_id: Optional[str] = None, candidate_profile_id: Optional[str] = None) -> Optional[dict]:
    if not session_info or not session_info.get('data_directory'):
        return None

    session_dir = session_info['data_directory']
    if not isinstance(dsm_result, dict) or _map_pipeline_stage_status(dsm_result.get('status')) != 'ready':
        return {
            'success': False,
            'status': 'blocked',
            'session_dir': session_dir,
            'output_path': '',
            'canonical_report_path': os.path.join(session_dir, 'analysis', 'evaluation_result.json'),
            'summary': {},
            'error': 'DSM 未准备完成，Evaluation 未触发',
            'error_code': 'EVAL_DSM_NOT_READY',
            'request_id': str(uuid.uuid4()),
            'session_id': (session_info or {}).get('session_id', os.path.basename(session_dir)),
            'worker_name': 'evaluation_worker',
            'worker_status': 'blocked',
            'artifact_paths': {'evaluation_result': os.path.join(session_dir, 'analysis', 'evaluation_result.json')},
            'summary_payload_type': 'evaluation_summary_update',
            'summary_payload_path': os.path.join(session_dir, 'analysis', 'evaluation_result.json'),
            'baseline_allocation_id': baseline_profile_id or '',
            'candidate_allocation_id': candidate_profile_id or '',
        }

    session_meta = {}
    meta_path = os.path.join(session_dir, 'session_meta.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as handle:
            session_meta = json.load(handle)

    return evaluation_worker.run_for_session(
        session_dir,
        experiment_case_manager.architecture_bundle,
        session_meta=session_meta,
        baseline_profile_id=baseline_profile_id,
        candidate_profile_id=candidate_profile_id,
    ).as_dict()


def _run_session_optimization(
    session_info: Optional[dict],
    evaluation_result = None,
    baseline_profile_id: Optional[str] = None,
    current_profile_id: Optional[str] = None,
    pop_size: int = 40,
    n_gen: int = 40,
    seed: int = 42,
) -> Optional[dict]:
    if not session_info or not session_info.get('data_directory'):
        return None

    session_dir = session_info['data_directory']
    if not isinstance(evaluation_result, dict) or _map_pipeline_stage_status(evaluation_result.get('status')) != 'ready':
        return {
            'success': False,
            'status': 'blocked',
            'session_dir': session_dir,
            'output_path': '',
            'canonical_report_path': os.path.join(session_dir, 'analysis', 'optimization_result.json'),
            'summary': {},
            'error': 'Evaluation 未准备完成，Optimization 未触发',
            'error_code': 'OPT_EVAL_NOT_READY',
            'request_id': str(uuid.uuid4()),
            'session_id': (session_info or {}).get('session_id', os.path.basename(session_dir)),
            'worker_name': 'optimization_worker',
            'worker_status': 'blocked',
            'artifact_paths': {'optimization_result': os.path.join(session_dir, 'analysis', 'optimization_result.json')},
            'summary_payload_type': 'architecture_recommendation_update',
            'summary_payload_path': os.path.join(session_dir, 'analysis', 'optimization_result.json'),
            'baseline_allocation_id': baseline_profile_id or '',
            'current_allocation_id': current_profile_id or '',
            'recommended_allocation_id': '',
        }

    session_meta = {}
    meta_path = os.path.join(session_dir, 'session_meta.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as handle:
            session_meta = json.load(handle)

    return optimization_worker.run_for_session(
        session_dir,
        experiment_case_manager.architecture_bundle,
        session_meta=session_meta,
        baseline_profile_id=baseline_profile_id,
        current_profile_id=current_profile_id,
        pop_size=pop_size,
        n_gen=n_gen,
        seed=seed,
    ).as_dict()


def _build_dsm_summary_payload(session_id: Optional[str], session_info: Optional[dict], dsm_result: Optional[dict]) -> Optional[dict]:
    if not dsm_result:
        return None

    summary = dsm_result.get('summary') or {}
    figure_context = _collect_figure_context(session_info)
    return _build_ws_payload(
        'dsm_summary_update',
        session_id=session_id,
        case_id=(session_info or {}).get('case_id') if session_info else None,
        data={
            'node_count': summary.get('node_count'),
            'edge_count': summary.get('edge_count'),
            'cross_module_interactions': summary.get('cross_module_interactions'),
            'total_bus_bytes': summary.get('total_bus_bytes'),
            'avg_cross_latency': summary.get('avg_cross_latency'),
            'global_stats_ready': summary.get('global_stats_ready', False),
            'status': dsm_result.get('status', 'waiting'),
            'output_path': dsm_result.get('output_path', ''),
            'canonical_report_path': dsm_result.get('canonical_report_path', ''),
            'error': dsm_result.get('error', ''),
            **figure_context,
        }
    )


def _build_evaluation_summary_payload(session_id: Optional[str], session_info: Optional[dict], evaluation_result: Optional[dict]) -> Optional[dict]:
    if not evaluation_result:
        return None

    summary = evaluation_result.get('summary') or {}
    figure_context = _collect_figure_context(session_info)
    return _build_ws_payload(
        'evaluation_summary_update',
        session_id=session_id,
        case_id=(session_info or {}).get('case_id') if session_info else None,
        data={
            'session_id': summary.get('session_id', session_id),
            'baseline_allocation_id': summary.get('baseline_allocation_id', evaluation_result.get('baseline_allocation_id', '')),
            'candidate_allocation_id': summary.get('candidate_allocation_id', evaluation_result.get('candidate_allocation_id', '')),
            'final_composite_score': summary.get('final_composite_score'),
            'constraint_violation_count': summary.get('constraint_violation_count'),
            'domain_scores': summary.get('domain_scores', {}),
            'baseline_delta': summary.get('baseline_delta', {}),
            'evaluation_ready': summary.get('evaluation_ready', False),
            'status': evaluation_result.get('status', 'waiting'),
            'output_path': evaluation_result.get('output_path', ''),
            'canonical_report_path': evaluation_result.get('canonical_report_path', ''),
            'error': evaluation_result.get('error', ''),
            'error_code': evaluation_result.get('error_code', ''),
            'figure_batch_manifest_path': os.path.join((session_info or {}).get('data_directory', ''), 'analysis', 'figure_batch_manifest.json') if session_info else '',
            **figure_context,
        }
    )


def _build_architecture_recommendation_payload(session_id: Optional[str], session_info: Optional[dict], optimization_result: Optional[dict]) -> Optional[dict]:
    if not optimization_result:
        return None

    summary = optimization_result.get('summary') or {}
    figure_context = _collect_figure_context(session_info)
    return _build_ws_payload(
        'architecture_recommendation_update',
        session_id=session_id,
        case_id=(session_info or {}).get('case_id') if session_info else None,
        data={
            'session_id': summary.get('session_id', session_id),
            'current_architecture': summary.get('current_architecture', {}),
            'recommended_architecture': summary.get('recommended_architecture', {}),
            'all_candidate_summaries': summary.get('all_candidate_summaries', []),
            'predicted_score_delta': summary.get('predicted_score_delta'),
            'predicted_cross_count_delta': summary.get('predicted_cross_count_delta'),
            'predicted_power_delta': summary.get('predicted_power_delta'),
            'constraint_pass': summary.get('constraint_pass', False),
            'optimization_ready': summary.get('optimization_ready', False),
            'status': optimization_result.get('status', 'waiting'),
            'output_path': optimization_result.get('output_path', ''),
            'canonical_report_path': optimization_result.get('canonical_report_path', ''),
            'error': optimization_result.get('error', ''),
            'error_code': optimization_result.get('error_code', ''),
            'figure_batch_manifest_path': os.path.join((session_info or {}).get('data_directory', ''), 'analysis', 'figure_batch_manifest.json') if session_info else '',
            **figure_context,
        }
    )


def _build_figure_asset_status_payload(session_id: Optional[str], session_info: Optional[dict], pipeline_status: Optional[dict]) -> Optional[dict]:
    if not session_info:
        return None

    manifest = _build_figure_batch_manifest(session_info, pipeline_status)
    if manifest is None:
        return None

    return _build_ws_payload(
        'figure_asset_status_update',
        session_id=session_id,
        case_id=(session_info or {}).get('case_id') if session_info else None,
        data=manifest,
    )


def _build_ws_payload(message_type: str, data: Optional[dict] = None, session_id: Optional[str] = None,
                      case_id: Optional[str] = None, timestamp: Optional[int] = None,
                      extra: Optional[dict] = None) -> dict:
    payload = {
        'type': message_type,
        'timestamp': timestamp if timestamp is not None else int(time.time() * 1000),
        'session_id': session_id,
        'case_id': case_id,
        'source': WS_SOURCE,
        'schema_version': WS_SCHEMA_VERSION,
        'data': data or {}
    }
    if extra:
        payload.update(extra)
    return payload


def _infer_capture_family(msg_type: str) -> str:
    if msg_type == 'planning_telemetry':
        return 'planning_raw'
    if msg_type.startswith('camera_') or msg_type.startswith('perception_'):
        return 'perception_raw'
    return 'flight_control_raw'


def _update_capture_stats(message: dict, current_time: float):
    msg_type = message.get('type', 'unknown')
    family = _infer_capture_family(msg_type)
    message_timestamp = int(message.get('timestamp', int(current_time * 1000)))
    recent_packets = capture_stats['recent_packets'][family]
    recent_packets.append(current_time)
    while recent_packets and current_time - recent_packets[0] > 2.0:
        recent_packets.popleft()

    capture_stats['family_last_ts'][family] = message_timestamp
    capture_stats['family_packet_counts'][family] += 1
    capture_stats['last_packet_ts'] = message_timestamp

    if msg_type == 'planning_telemetry':
        radar_packets = capture_stats['recent_packets']['radar_raw']
        radar_packets.append(current_time)
        while radar_packets and current_time - radar_packets[0] > 2.0:
            radar_packets.popleft()
        capture_stats['family_last_ts']['radar_raw'] = message_timestamp
        capture_stats['family_packet_counts']['radar_raw'] += 1

    if msg_type == 'unknown':
        capture_stats['parse_error_count'] += 1
        capture_stats['last_error'] = f"unknown func=0x{message.get('func_code', 0):02X}"


def _get_capture_rate_hz(family: str, current_time: float) -> float:
    recent_packets = capture_stats['recent_packets'][family]
    while recent_packets and current_time - recent_packets[0] > 2.0:
        recent_packets.popleft()
    if not recent_packets:
        return 0.0
    window_span = max(current_time - recent_packets[0], 1.0)
    return round(len(recent_packets) / window_span, 2)


def _build_capture_overview_payload(current_time: float) -> dict:
    session_info = recorder.get_session_info() if recorder else None
    return _build_ws_payload(
        'capture_overview_update',
        session_id=current_session_id,
        case_id=getattr(recorder, 'case_id', None) if recorder else None,
        data={
            'recording': recording_active,
            'enabled_ports': _normalize_listen_ports(),
            'flight_control_rate_hz': _get_capture_rate_hz('flight_control_raw', current_time),
            'planning_rate_hz': _get_capture_rate_hz('planning_raw', current_time),
            'radar_rate_hz': _get_capture_rate_hz('radar_raw', current_time),
            'perception_rate_hz': _get_capture_rate_hz('perception_raw', current_time),
            'packet_counts': dict(capture_stats['family_packet_counts']),
            'parse_error_count': capture_stats.get('parse_error_count', 0),
            'last_packet_ts': capture_stats.get('last_packet_ts'),
            'last_error': capture_stats.get('last_error', ''),
            'output_dir': (session_info or {}).get('data_directory', ''),
            'bytes_written': (session_info or {}).get('total_bytes', 0)
        }
    )


def _build_data_quality_payload(current_time: float) -> dict:
    current_time_ms = int(current_time * 1000)
    flight_control_gap_ms = None
    planning_gap_ms = None
    radar_gap_ms = None

    if capture_stats['family_last_ts'].get('flight_control_raw'):
        flight_control_gap_ms = max(0, current_time_ms - capture_stats['family_last_ts']['flight_control_raw'])
    if capture_stats['family_last_ts'].get('planning_raw'):
        planning_gap_ms = max(0, current_time_ms - capture_stats['family_last_ts']['planning_raw'])
    if capture_stats['family_last_ts'].get('radar_raw'):
        radar_gap_ms = max(0, current_time_ms - capture_stats['family_last_ts']['radar_raw'])

    radar_missing = _get_capture_rate_hz('radar_raw', current_time) <= 0
    health_level = 'ok'
    health_text = 'capture healthy'
    if (flight_control_gap_ms and flight_control_gap_ms > 1000) or (planning_gap_ms and planning_gap_ms > 2000):
        health_level = 'warning'
        health_text = 'flight or planning stream gap detected'
    elif radar_missing:
        health_level = 'warning'
        health_text = 'radar stream not connected'

    return _build_ws_payload(
        'data_quality_update',
        session_id=current_session_id,
        case_id=getattr(recorder, 'case_id', None) if recorder else None,
        data={
            'parse_error_count': capture_stats.get('parse_error_count', 0),
            'window_missing_count': capture_stats.get('window_missing_count', 0),
            'planning_gap_ms': planning_gap_ms,
            'flight_control_gap_ms': flight_control_gap_ms,
            'radar_gap_ms': radar_gap_ms,
            'radar_missing': radar_missing,
            'health_level': health_level,
            'health_text': health_text
        }
    )


def _extract_realtime_events(message: dict, views: dict) -> list:
    events = []
    msg_type = message.get('type', 'unknown')
    payload = message.get('data', {}) or {}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    if msg_type == 'avoiflag' and payload.get('AvoiFlag_AvoidanceFlag'):
        events.append({
            'timestamp': timestamp,
            'event_type': 'avoidance_triggered',
            'event_source': 'runtime_monitor',
            'event_level': 'warning',
            'event_value': 1,
            'event_detail': '避障标志触发'
        })

    if msg_type == 'unknown':
        events.append({
            'timestamp': timestamp,
            'event_type': 'protocol_error',
            'event_source': 'protocol_parser',
            'event_level': 'warning',
            'event_value': message.get('func_code_hex', 'unknown'),
            'event_detail': '收到未知功能字数据包'
        })

    return events


# ================================================================
# UDP数据处理回调
# ================================================================

# 记录上次广播时间，用于节流
# Limit update rate to avoid overwhelming the frontend
last_broadcast_times = {} 

def on_udp_message_received(message: dict):
    """
    UDP数据包接收回调
    1. 将接收到的数据通过WebSocket广播到前端
    2. 实时计算KPI指标
    3. 录制数据到CSV文件（如果启用）
    4. 记录UDP接收日志
    """
    global recorder, recording_active, last_broadcast_times, current_session_id
    
    msg_type = message.get('type', 'unknown')
    func_code = message.get('func_code', 0)
    
    # -------------------------------------------------------------------------
    # 1. 日志输出优化 (针对0x40-0x4B高频FCS数据进行节流)
    # -------------------------------------------------------------------------
    current_time = time.time()
    is_fcs_high_freq = 0x40 <= func_code <= 0x4B
    
    if is_fcs_high_freq:
        # 对于高频FCS数据，大幅降低日志频率 (每2秒一次)
        last_log_time = last_broadcast_times.get(f"log_fcs_{func_code}", 0)
        if current_time - last_log_time >= 2.0:
            # 只输出关键信息：类型和功能码，不通过日志打印详细内容
            logger.info(f"[FCS-UDP] 接收高频数据(节流2s): type='{msg_type}', func=0x{func_code:02X}")
            last_broadcast_times[f"log_fcs_{func_code}"] = current_time
    else:
        # 对于规划遥测(0x71)、雷达、指令回执等，保留详细流水日志
        logger.info(f"[调试] 收到UDP消息: type='{msg_type}', func_code={func_code}")

    _update_capture_stats(message, current_time)

    if msg_type == 'heartbeat_ack':
        logger.info("[UDP] 收到飞控回执/心跳包 func=0x00")
        if _should_broadcast_packet(msg_type, func_code, current_time):
            asyncio.create_task(manager.broadcast(_build_ws_payload(
                'udp_data',
                data=message,
                session_id=current_session_id,
                case_id=getattr(recorder, 'case_id', None) if recorder else None,
                timestamp=message.get('timestamp', int(time.time() * 1000))
            )))
        return

    if recording_active and recorder:
        recorder.record_decoded_packet(message)
    
    # 分支1: 实时计算KPI
    kpi_result = calculator.process_packet(message)
    views = kpi_result.get('views', {})
    window_metrics = kpi_result.get('window_metrics', {})
    case_id = getattr(recorder, 'case_id', None) if recorder else None
    runtime_payload = _refresh_experiment_runtime(message, window_metrics)
    
    # 广播KPI结果到前端 (Limit to 5Hz to reduce load)
    current_time = time.time()
    last_kpi_time = last_broadcast_times.get('kpi', 0)
    
    if current_time - last_kpi_time >= 0.2:  # 5Hz (200ms)
        kpi_message = _build_ws_payload(
            'kpi_update',
            data=kpi_result,
            session_id=current_session_id,
            case_id=case_id,
            timestamp=message.get('timestamp', int(time.time() * 1000))
        )
        asyncio.create_task(manager.broadcast(kpi_message))
        last_broadcast_times['kpi'] = current_time
    
    # 分支2: 录制数据（冷流）- 统一使用RawDataRecorder
    # 检查全局录制状态
    # global recorder, recording_active # Already declared
    
    # 支持左侧面板"配置自动录制" -> 如果启用，尝试确保recorder已启动
    if log_config.autoRecord:
         # 如果尚未激活录制，且没有手动录制正在进行
         if not recording_active and recorder is None:
             # 初始化自动录制会话
             planned_case = _find_experiment_case()
             auto_session_id = _build_session_id(planned_case, is_auto=True)
             project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
             base_directory = os.path.join(project_root, 'Log', 'AutoDSM')
             
             try:
                 recorder = RawDataRecorder(
                     auto_session_id,
                     base_directory,
                     plan_case_id=getattr(planned_case, 'case_id', None),
                     session_meta_patch=_build_recording_meta_patch(
                         planned_case,
                         case_id=getattr(planned_case, 'case_id', None),
                         repeat_index=getattr(planned_case, 'repeat_index', None),
                         analysis_run_id=auto_session_id,
                     ),
                 )
                 recorder.enabled_ports = _normalize_listen_ports()
                 recorder.set_runtime_context(_refresh_experiment_runtime(latest_metrics={}, planned_case=planned_case))
                 recorder.start_recording()
                 recording_active = True
                 current_session_id = auto_session_id
                 logger.info(f"自动录制已启动: {auto_session_id}")
                 
                 # 广播状态
                 asyncio.create_task(manager.broadcast(_build_recording_status_payload(True, current_session_id, recorder.get_session_info())))
             except Exception as e:
                 logger.error(f"无法启动自动录制: {e}")

    # 只要recorder处于活动状态，就记录窗口指标和事件
    if recording_active and recorder:
        if _should_emit_named_update('window_metrics_record', current_time):
            recorder.record_window_metrics(window_metrics)
        for event in _extract_realtime_events(message, views):
            event['scenario_id'] = runtime_payload.get('scenario', {}).get('scenario_id', 'scenario_default')
            recorder.record_event(event)
    
    # 分支3: 广播原始数据到前端（需节流）
    # 对于planning_telemetry类型，会在下面单独处理并广播包含轨迹的数据
    ws_message = _build_ws_payload(
        'udp_data',
        data=message,
        session_id=current_session_id,
        case_id=case_id,
        timestamp=message.get('timestamp', int(time.time() * 1000))
    )
    
    # Identify message type and apply logging
    # 分支4: 根据消息类型处理
    if msg_type == 'fcs_states':
        data = message.get('data', {})
        logger.debug(f"[UDP] 飞行状态: 位置({data.get('latitude', 0):.6f}, {data.get('longitude', 0):.6f}), 高度{data.get('altitude', 0):.1f}m")
    elif msg_type == 'planning_telemetry':
        data = message.get('data', {})
        logger.info(f"[UDP] ===== 规划遥测(0x71) =====")
        # ... existing logging ...
        
        # 检查是否包含真实轨迹数据
        global_path_data = data.get('global_path', [])
        local_traj_data = data.get('local_path', [])
        
        # Sampling logic for logging/display
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
            'local_path': sampled_local_traj,
            'local_traj': sampled_local_traj
        }
        
        logger.info(f"[WebSocket] 准备发送规划遥测，包含global_path: {len(sampled_global_path)}点, local_traj: {len(sampled_local_traj)}点")
    elif msg_type == 'fcs_pwms':
        logger.debug(f"[UDP] PWM数据: 功能码0x{func_code:02X}")
    elif msg_type == 'fcs_datactrl':
        logger.debug(f"[UDP] 控制循环数据")
    elif msg_type == 'fcs_gncbus':
        logger.debug(f"[UDP] GN&C总线数据")
    elif msg_type == 'avoiflag':
        data = message.get('data', {})
        logger.debug(f"[UDP] 避障标志: 雷达={data.get('laser_radar_enabled', False)}, 避障={data.get('avoidance_flag', False)}")
    elif msg_type == 'fcs_esc':
        logger.debug(f"[UDP] 电机ESC数据")
    elif msg_type == 'fcs_param':
        logger.info(f"[UDP] 飞控参数: 功能码0x{func_code:02X}")
    elif msg_type == 'unknown':
        logger.warning(f"[UDP] 未知数据包: 功能码=0x{func_code:02X}")
    else:
        logger.debug(f"[UDP] {msg_type} (功能码: 0x{func_code:02X})")

    if msg_type in ['fcs_states', 'fcs_gncbus', 'fcs_datagcs', 'fcs_esc', 'avoiflag']:
        if _should_emit_named_update('flight_state_update', current_time):
            asyncio.create_task(manager.broadcast(_build_ws_payload(
                'flight_state_update',
                data=views.get('flight_state', {}),
                session_id=current_session_id,
                case_id=case_id,
                timestamp=message.get('timestamp', int(time.time() * 1000))
            )))

    if msg_type in ['planning_telemetry', 'fcs_datagcs', 'fcs_line_aim2ab', 'fcs_line_ab', 'avoiflag']:
        if _should_emit_named_update('planning_state_update', current_time):
            asyncio.create_task(manager.broadcast(_build_ws_payload(
                'planning_state_update',
                data=views.get('planning_state', {}),
                session_id=current_session_id,
                case_id=case_id,
                timestamp=message.get('timestamp', int(time.time() * 1000))
            )))

    if _should_emit_named_update('system_performance_update', current_time):
        asyncio.create_task(manager.broadcast(_build_ws_payload(
            'system_performance_update',
            data=views.get('system_performance', {}),
            session_id=current_session_id,
            case_id=case_id,
            timestamp=message.get('timestamp', int(time.time() * 1000))
        )))

    if _should_emit_named_update('experiment_context_update', current_time):
        asyncio.create_task(manager.broadcast(_build_ws_payload(
            'experiment_context_update',
            data=runtime_payload,
            session_id=current_session_id,
            case_id=case_id,
            timestamp=message.get('timestamp', int(time.time() * 1000))
        )))

    if _should_emit_named_update('capture_overview_update', current_time):
        asyncio.create_task(manager.broadcast(_build_capture_overview_payload(current_time)))

    if _should_emit_named_update('data_quality_update', current_time):
        asyncio.create_task(manager.broadcast(_build_data_quality_payload(current_time)))
    
    if _should_broadcast_packet(msg_type, func_code, current_time):
        asyncio.create_task(manager.broadcast(ws_message))
    



# ================================================================
# FastAPI 路由
# ================================================================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "GCS Web Backend",
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
    active_config = _reset_connection_config()
    return {
        "type": "connection_config",
        "data": active_config.dict(),
        "timestamp": int(time.time() * 1000)
    }

@app.post("/api/config/connection")
async def update_connection_config(config: ConnectionConfig):
    """固定部署口径下忽略运行时改写，仅返回当前固定配置。"""
    active_config = _reset_connection_config()
    logger.info(
        "忽略运行时连接配置修改请求，继续使用固定链路: "
        f"{active_config.listenAddress}:{active_config.hostPort} -> "
        f"{active_config.remoteIp}:{active_config.commandRecvPort}"
    )

    await manager.broadcast({
        "type": "config_update",
        "config_type": "connection",
        "data": active_config.dict(),
        "timestamp": int(time.time() * 1000)
    })

    return {"status": "success", "message": "固定链路参数已生效", "data": active_config.dict()}

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
        
        active_config = _reset_connection_config()

        # 启动UDP服务器
        ports = _normalize_listen_ports()
        
        await udp_handler.start_server(
            host=active_config.listenAddress,
            ports=ports,
            target_host=active_config.remoteIp,
            target_port=active_config.commandRecvPort,
        )
        udp_server_started = True
        
        logger.info(f"UDP服务器已启动: {ports}")
        logger.info(f"发送目标: {active_config.remoteIp}:{active_config.commandRecvPort}")
        
        await manager.broadcast({
            "type": "udp_status_change",
            "status": "connected",
            "config": active_config.dict(),
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
    """发送指令到飞控或规划模块，并保证上行最小间隔为500ms。"""
    try:
        command_type = request.type
        params = request.params
        
        logger.info(f"收到指令: {command_type}, 参数: {params}")
        
        packet = None
        target_host = None
        target_port = None
        response_message = "指令已发送"
        channel = _resolve_command_channel(command_type)
        
        if command_type == 'cmd_idx':
            cmd_id = params.get('cmdId', 0)

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
            rate_limit_result = await _check_command_send_rate(command_type)
            if rate_limit_result is not None:
                return rate_limit_result

            try:
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

                if command_type == 'cmd_idx':
                    cmd_id = params.get('cmdId', 0)
                    for repeat_index in range(CMD_IDX_REPEAT_COUNT):
                        udp_handler.send_data(packet, target_host, target_port)
                        await _mark_command_sent(channel)

                        if repeat_index < CMD_IDX_REPEAT_COUNT - 1:
                            await asyncio.sleep(COMMAND_SEND_MIN_INTERVAL_SEC)

                    if CMD_IDX_RESET_TO_ZERO:
                        await asyncio.sleep(COMMAND_SEND_MIN_INTERVAL_SEC)
                        payload_zero = encode_extu_fcs_from_dict(
                            cached_pid_params,
                            cmd_idx=0,
                            cmd_mission=0,
                            cmd_mission_val=0.0
                        )
                        packet_zero = encode_command_packet(NCLINK_SEND_EXTU_FCS, payload_zero)
                        udp_handler.send_data(packet_zero, target_host, target_port)
                        await _mark_command_sent(channel)
                        response_message = (
                            f"指令{cmd_id}已按500ms间隔连续发送{CMD_IDX_REPEAT_COUNT}次，"
                            "末次已置0"
                        )
                    else:
                        response_message = f"指令{cmd_id}已按500ms间隔连续发送{CMD_IDX_REPEAT_COUNT}次"
                else:
                    udp_handler.send_data(packet, target_host, target_port)
                    await _mark_command_sent(channel)

                return {
                    "type": "command_response",
                    "command": command_type,
                    "status": "success",
                    "message": response_message,
                    "timestamp": int(time.time() * 1000)
                }
            finally:
                await _release_command_channel(channel)
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
    global recording_active, current_session_id, recorder, cached_pid_params
    
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
                    planned_case = _find_experiment_case()
                    session_id = _build_session_id(planned_case)
                    
                    # 确定日志目录: Apollo-GCS-Web/Log/DSM
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    base_directory = os.path.join(project_root, 'Log', 'DSM')

                    recorder = RawDataRecorder(
                        session_id,
                        base_directory,
                        plan_case_id=getattr(planned_case, 'case_id', None),
                        session_meta_patch=_build_recording_meta_patch(
                            planned_case,
                            case_id=getattr(planned_case, 'case_id', None),
                            repeat_index=getattr(planned_case, 'repeat_index', None),
                            analysis_run_id=session_id,
                        ),
                    )
                    recorder.enabled_ports = _normalize_listen_ports()
                    recorder.set_runtime_context(_refresh_experiment_runtime(latest_metrics={}, planned_case=planned_case))
                    recorder.start_recording()
                    
                    recording_active = True
                    current_session_id = session_id
                    
                    await manager.broadcast({
                        **_build_recording_status_payload(True, current_session_id, recorder.get_session_info())
                    })
                    logger.info(f"WebSocket启动录制: {current_session_id}")

                    runtime_defaults = _build_runtime_event_defaults(recorder.get_session_info())
                    _record_session_event(
                        recorder.get_session_info(),
                        _build_contract_event(
                            session_id=current_session_id,
                            case_id=recorder.get_session_info().get('case_id'),
                            event_type='operator_action',
                            event_source='websocket',
                            event_level='info',
                            event_value='start_recording',
                            event_detail='通过WebSocket开始录制',
                            **runtime_defaults,
                        ),
                    )
                    _record_session_event(
                        recorder.get_session_info(),
                        _build_contract_event(
                            session_id=current_session_id,
                            case_id=recorder.get_session_info().get('case_id'),
                            event_type='record_start',
                            event_source='websocket',
                            event_level='info',
                            event_value=current_session_id,
                            event_detail='通过WebSocket开始录制',
                            **runtime_defaults,
                        ),
                    )
                    
            elif action == 'stop':
                if recording_active and recorder:
                    session_info = recorder.get_session_info()
                    runtime_defaults = _build_runtime_event_defaults(recorder.get_session_info())
                    _record_session_event(
                        recorder.get_session_info(),
                        _build_contract_event(
                            session_id=current_session_id,
                            case_id=recorder.get_session_info().get('case_id'),
                            event_type='operator_action',
                            event_source='websocket',
                            event_level='info',
                            event_value='stop_recording',
                            event_detail='通过WebSocket停止录制',
                            **runtime_defaults,
                        ),
                    )
                    _record_session_event(
                        recorder.get_session_info(),
                        _build_contract_event(
                            session_id=current_session_id,
                            case_id=recorder.get_session_info().get('case_id'),
                            event_type='record_stop',
                            event_source='websocket',
                            event_level='info',
                            event_value=current_session_id,
                            event_detail='通过WebSocket停止录制',
                            **runtime_defaults,
                        ),
                    )
                    recorder.stop_recording()
                    
                    last_session_id = current_session_id
                    recording_active = False
                    current_session_id = None
                    
                    await manager.broadcast({
                        **_build_recording_status_payload(False, last_session_id, session_info)
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

@app.get("/api/recording/status")
async def get_recording_status():
    """获取当前录制状态"""
    global recording_active, current_session_id, recorder, last_standardization_result, last_evaluation_result, last_optimization_result
    
    session_info = None
    if recorder:
        session_info = recorder.get_session_info()
    
    return {
        **_build_recording_status_payload(recording_active, current_session_id, session_info)
    }

@app.post("/api/recording/start")
async def start_recording(config: RecordingConfig):
    """开始数据录制"""
    global recording_active, current_session_id, recorder, selected_plan_case_id, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result
    
    if recording_active:
        logger.warning("录制已在进行中")
        return {
            "type": "recording_response",
            "status": "error",
            "message": "录制已在进行中",
            "timestamp": int(time.time() * 1000)
        }
    
    try:
        planned_case = _find_experiment_case(config.plan_case_id)
        if planned_case is not None:
            selected_plan_case_id = experiment_case_manager.select_case(planned_case.case_id).case_id
        elif config.plan_case_id:
            selected_plan_case_id = str(config.plan_case_id).strip().upper()
            experiment_case_manager.selected_case_id = selected_plan_case_id

        resolved_plan_case_id = getattr(planned_case, 'case_id', None) or selected_plan_case_id or None
        resolved_repeat_index = getattr(planned_case, 'repeat_index', None)
        if resolved_repeat_index is None and config.repeat_index is not None:
            resolved_repeat_index = config.repeat_index

        # 生成会话ID（如果未提供）
        if not config.session_id:
            config.session_id = _build_session_id(
                planned_case,
                case_id=resolved_plan_case_id,
                repeat_index=resolved_repeat_index,
            )
        else:
            try:
                _validate_session_id_contract(
                    config.session_id,
                    plan_case_id=resolved_plan_case_id,
                    repeat_index=resolved_repeat_index,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not config.base_directory:
            base_directory = os.path.join(project_root, 'Log', 'Records')
        elif os.path.isabs(config.base_directory):
            base_directory = config.base_directory
        else:
            base_directory = os.path.join(project_root, config.base_directory)
        
        # 创建录制器
        recorder = RawDataRecorder(
            config.session_id,
            base_directory,
            case_id_override=config.case_id or None,
            plan_case_id=selected_plan_case_id,
            session_meta_patch=_build_recording_meta_patch(
                planned_case,
                case_id=resolved_plan_case_id,
                repeat_index=resolved_repeat_index,
                scenario_id=config.scenario_id or None,
                notes=config.notes or '',
                experiment_type=config.experiment_type or None,
                figure_run_id=config.figure_run_id or None,
                figure_batch_id=config.figure_batch_id or None,
                figure_batch_group=config.figure_batch_group or None,
                chapter_target=config.chapter_target or None,
                law_validation_scope=config.law_validation_scope or None,
                analysis_run_id=config.session_id,
            ),
        )
        recorder.enabled_ports = _normalize_listen_ports()
        recorder.set_runtime_context(_refresh_experiment_runtime(latest_metrics={}, planned_case=planned_case))
        recorder.start_recording()
        runtime_defaults = _build_runtime_event_defaults(recorder.get_session_info())
        _record_session_event(
            recorder.get_session_info(),
            _build_contract_event(
                session_id=config.session_id,
                case_id=recorder.get_session_info().get('case_id'),
                event_type='operator_action',
                event_source='rest_api',
                event_level='info',
                event_value='start_recording',
                event_detail='通过REST开始录制',
                **runtime_defaults,
            ),
        )
        _record_session_event(
            recorder.get_session_info(),
            _build_contract_event(
                session_id=config.session_id,
                case_id=recorder.get_session_info().get('case_id'),
                event_type='record_start',
                event_source='rest_api',
                event_level='info',
                event_value=config.session_id,
                event_detail='通过REST开始录制',
                **runtime_defaults,
            ),
        )
        _record_session_event(
            recorder.get_session_info(),
            _build_contract_event(
                session_id=config.session_id,
                case_id=recorder.get_session_info().get('case_id'),
                event_type='task_change',
                event_source='experiment_context',
                event_level='info',
                event_value=current_experiment_runtime.get('task', {}).get('task_name', ''),
                event_detail='录制启动时绑定当前任务上下文',
                **runtime_defaults,
            ),
        )
        _record_session_event(
            recorder.get_session_info(),
            _build_contract_event(
                session_id=config.session_id,
                case_id=recorder.get_session_info().get('case_id'),
                event_type='scenario_tag',
                event_source='experiment_context',
                event_level='info',
                event_value=current_experiment_runtime.get('scenario', {}).get('scenario_id', 'scenario_default'),
                event_detail='录制启动时绑定当前场景标签',
                **runtime_defaults,
            ),
        )
        
        recording_active = True
        current_session_id = config.session_id
        last_standardization_result = None
        last_dsm_result = None
        last_evaluation_result = None
        last_optimization_result = None
        
        # 广播状态更新
        await manager.broadcast(_build_recording_status_payload(True, current_session_id, recorder.get_session_info()))
        await manager.broadcast(_build_pipeline_status_payload(True, current_session_id, recorder.get_session_info(), None, None, None, None))
        
        logger.info(f"开始录制: {current_session_id}")
        
        return {
            "type": "recording_response",
            "status": "success",
            "message": "录制已开始",
            "session_id": current_session_id,
            "session_info": recorder.get_session_info(),
            "experiment_context": current_experiment_runtime,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"开始录制失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recording/stop")
async def stop_recording():
    """停止数据录制"""
    global recording_active, current_session_id, recorder, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result
    
    if not recording_active:
        return {
            "type": "recording_response",
            "status": "error",
            "message": "录制未开始",
            "timestamp": int(time.time() * 1000)
        }
    
    try:
        session_info = None
        if recorder:
            runtime_defaults = _build_runtime_event_defaults(recorder.get_session_info())
            _record_session_event(
                recorder.get_session_info(),
                _build_contract_event(
                    session_id=current_session_id,
                    case_id=recorder.get_session_info().get('case_id'),
                    event_type='operator_action',
                    event_source='rest_api',
                    event_level='info',
                    event_value='stop_recording',
                    event_detail='通过REST停止录制',
                    **runtime_defaults,
                ),
            )
            _record_session_event(
                recorder.get_session_info(),
                _build_contract_event(
                    session_id=current_session_id,
                    case_id=recorder.get_session_info().get('case_id'),
                    event_type='record_stop',
                    event_source='rest_api',
                    event_level='info',
                    event_value=current_session_id,
                    event_detail='通过REST停止录制',
                    **runtime_defaults,
                ),
            )
            recorder.stop_recording()
            session_info = recorder.get_session_info()
            last_standardization_result = _run_session_standardization(session_info)
            if last_standardization_result is not None:
                session_info['standardization'] = last_standardization_result
                _record_pipeline_stage_event(session_info, 'standardization', last_standardization_result)
            last_dsm_result = _run_session_dsm(session_info, last_standardization_result)
            if last_dsm_result is not None:
                session_info['dsm'] = last_dsm_result
                _record_pipeline_stage_event(session_info, 'dsm', last_dsm_result)
            last_evaluation_result = _run_session_evaluation(session_info, last_dsm_result)
            if last_evaluation_result is not None:
                session_info['evaluation'] = last_evaluation_result
                _record_pipeline_stage_event(session_info, 'evaluation', last_evaluation_result)
            last_optimization_result = _run_session_optimization(session_info, last_evaluation_result)
            if last_optimization_result is not None:
                session_info['optimization'] = last_optimization_result
                _record_pipeline_stage_event(session_info, 'optimization', last_optimization_result)
            _update_session_meta_status(
                session_info,
                standardization_result=last_standardization_result,
                dsm_result=last_dsm_result,
                evaluation_result=last_evaluation_result,
                optimization_result=last_optimization_result,
            )
            _persist_pipeline_status(
                session_info,
                _build_pipeline_status_data(False, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result),
            )
        
        recording_active = False
        session_id = current_session_id
        current_session_id = None
        
        # 广播状态更新
        await manager.broadcast(_build_recording_status_payload(False, session_id, session_info))
        await manager.broadcast(_build_pipeline_status_payload(False, session_id, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result))
        figure_asset_status_payload = _build_figure_asset_status_payload(
            session_id,
            session_info,
            _build_pipeline_status_data(False, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result),
        )
        if figure_asset_status_payload is not None:
            await manager.broadcast(figure_asset_status_payload)
        dsm_summary_payload = _build_dsm_summary_payload(session_id, session_info, last_dsm_result)
        if dsm_summary_payload is not None:
            await manager.broadcast(dsm_summary_payload)
        evaluation_summary_payload = _build_evaluation_summary_payload(session_id, session_info, last_evaluation_result)
        if evaluation_summary_payload is not None:
            await manager.broadcast(evaluation_summary_payload)
        architecture_recommendation_payload = _build_architecture_recommendation_payload(session_id, session_info, last_optimization_result)
        if architecture_recommendation_payload is not None:
            await manager.broadcast(architecture_recommendation_payload)
        
        logger.info(f"录制已停止: {session_id}")
        
        return {
            "type": "recording_response",
            "status": "success",
            "message": "录制已停止",
            "session_id": session_id,
            "session_info": session_info,
            "standardization": last_standardization_result,
            "dsm": last_dsm_result,
            "evaluation": last_evaluation_result,
            "optimization": last_optimization_result,
            "experiment_context": current_experiment_runtime,
            "timestamp": int(time.time() * 1000)
        }
    except Exception as e:
        logger.error(f"停止录制失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/experiment/plan")
async def get_experiment_plan():
    return {
        'type': 'experiment_plan',
        'selected_case_id': selected_plan_case_id,
        'cases': [_serialize_experiment_case(case) for case in experiment_plan_cases],
        'architecture_profiles': experiment_case_manager.list_architecture_profiles(),
        'timestamp': int(time.time() * 1000)
    }


@app.get("/api/experiment/runtime")
async def get_experiment_runtime():
    runtime_payload = _refresh_experiment_runtime(latest_metrics={})
    return {
        'type': 'experiment_runtime',
        'runtime': runtime_payload,
        'selected_case_id': selected_plan_case_id,
        'timestamp': int(time.time() * 1000)
    }


@app.post("/api/experiment/select-case")
async def select_experiment_case(selection: ExperimentCaseSelection):
    global selected_plan_case_id

    planned_case = _find_experiment_case(selection.case_id)
    if planned_case is None:
        raise HTTPException(status_code=404, detail=f"未知实验 case: {selection.case_id}")

    selected_plan_case_id = experiment_case_manager.select_case(planned_case.case_id).case_id
    runtime_payload = _refresh_experiment_runtime(latest_metrics={}, planned_case=planned_case)
    if recorder:
        recorder.apply_session_meta_patch(_build_recording_meta_patch(planned_case))
        recorder.set_runtime_context(runtime_payload)
        recorder._write_session_meta()
        runtime_defaults = _build_runtime_event_defaults(recorder.get_session_info())
        _record_session_event(
            recorder.get_session_info(),
            _build_contract_event(
                session_id=current_session_id,
                case_id=recorder.get_session_info().get('case_id'),
                event_type='task_change',
                event_source='experiment_context',
                event_level='info',
                event_value=runtime_payload.get('task', {}).get('task_name', ''),
                event_detail='切换实验 case 后更新任务上下文',
                **runtime_defaults,
            ),
        )
        _record_session_event(
            recorder.get_session_info(),
            _build_contract_event(
                session_id=current_session_id,
                case_id=recorder.get_session_info().get('case_id'),
                event_type='scenario_tag',
                event_source='experiment_context',
                event_level='info',
                event_value=runtime_payload.get('scenario', {}).get('scenario_id', 'scenario_default'),
                event_detail='切换实验 case 后更新场景标签',
                **runtime_defaults,
            ),
        )

    await manager.broadcast(_build_ws_payload(
        'experiment_context_update',
        data=runtime_payload,
        session_id=current_session_id,
        case_id=getattr(recorder, 'case_id', None) if recorder else None,
    ))

    return {
        'type': 'experiment_case_selected',
        'selected_case_id': selected_plan_case_id,
        'runtime': runtime_payload,
        'timestamp': int(time.time() * 1000)
    }


@app.post('/api/analysis/dsm')
async def run_dsm_analysis(request: DsmAnalysisRequest):
    global last_dsm_result, last_evaluation_result, last_optimization_result

    session_dir = request.session_dir.strip()
    if not session_dir and request.session_id:
        session_dir = os.path.join(os.path.dirname(current_dir), 'Log', 'Records', request.session_id)

    if not session_dir:
        raise HTTPException(status_code=400, detail='缺少 session_dir 或 session_id')

    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail=f'会话目录不存在: {session_dir}')

    session_info = {
        'data_directory': session_dir,
        'session_id': request.session_id or os.path.basename(session_dir),
        'case_id': os.path.basename(session_dir),
    }
    last_dsm_result = _run_session_dsm(session_info, None, request.start_time, request.end_time)
    if last_dsm_result is None:
        raise HTTPException(status_code=500, detail='DSM 分析未产生结果')
    last_evaluation_result = _run_session_evaluation(session_info, last_dsm_result)
    last_optimization_result = _run_session_optimization(session_info, last_evaluation_result)
    _update_session_meta_status(
        session_info,
        standardization_result=last_standardization_result,
        dsm_result=last_dsm_result,
        evaluation_result=last_evaluation_result,
        optimization_result=last_optimization_result,
    )
    _persist_pipeline_status(
        session_info,
        _build_pipeline_status_data(False, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result),
    )

    session_id = request.session_id or os.path.basename(session_dir)
    await manager.broadcast(_build_pipeline_status_payload(False, session_id, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result))
    figure_asset_status_payload = _build_figure_asset_status_payload(
        session_id,
        session_info,
        _build_pipeline_status_data(False, session_info, last_standardization_result, last_dsm_result, last_evaluation_result, last_optimization_result),
    )
    if figure_asset_status_payload is not None:
        await manager.broadcast(figure_asset_status_payload)
    dsm_summary_payload = _build_dsm_summary_payload(session_id, session_info, last_dsm_result)
    if dsm_summary_payload is not None:
        await manager.broadcast(dsm_summary_payload)
    evaluation_summary_payload = _build_evaluation_summary_payload(session_id, session_info, last_evaluation_result)
    if evaluation_summary_payload is not None:
        await manager.broadcast(evaluation_summary_payload)
    architecture_recommendation_payload = _build_architecture_recommendation_payload(session_id, session_info, last_optimization_result)
    if architecture_recommendation_payload is not None:
        await manager.broadcast(architecture_recommendation_payload)

    return {
        'type': 'dsm_analysis_response',
        'status': 'success' if last_dsm_result.get('success') else 'failed',
        'result': last_dsm_result,
        'evaluation': last_evaluation_result,
        'optimization': last_optimization_result,
        'timestamp': int(time.time() * 1000)
    }


@app.post('/api/analysis/evaluation')
async def run_evaluation_analysis(request: EvaluationAnalysisRequest):
    global last_evaluation_result, last_optimization_result

    session_dir = request.session_dir.strip()
    if not session_dir and request.session_id:
        session_dir = os.path.join(os.path.dirname(current_dir), 'Log', 'Records', request.session_id)

    if not session_dir:
        raise HTTPException(status_code=400, detail='缺少 session_dir 或 session_id')

    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail=f'会话目录不存在: {session_dir}')

    session_info = {
        'data_directory': session_dir,
        'session_id': request.session_id or os.path.basename(session_dir),
        'case_id': os.path.basename(session_dir),
    }
    dsm_result = {
        'status': 'ready' if os.path.exists(os.path.join(session_dir, 'analysis', 'dsm_report.json')) else 'blocked'
    }
    last_evaluation_result = _run_session_evaluation(
        session_info,
        dsm_result,
        baseline_profile_id=request.baseline_profile_id or None,
        candidate_profile_id=request.candidate_profile_id or None,
    )
    if last_evaluation_result is None:
        raise HTTPException(status_code=500, detail='Evaluation 分析未产生结果')
    last_optimization_result = _run_session_optimization(
        session_info,
        last_evaluation_result,
        baseline_profile_id=request.baseline_profile_id or None,
        current_profile_id=request.candidate_profile_id or None,
    )

    _update_session_meta_status(
        session_info,
        standardization_result=last_standardization_result,
        dsm_result=dsm_result,
        evaluation_result=last_evaluation_result,
        optimization_result=last_optimization_result,
    )
    _persist_pipeline_status(
        session_info,
        _build_pipeline_status_data(False, session_info, last_standardization_result, dsm_result, last_evaluation_result, last_optimization_result),
    )

    session_id = request.session_id or os.path.basename(session_dir)
    await manager.broadcast(_build_pipeline_status_payload(False, session_id, session_info, last_standardization_result, dsm_result, last_evaluation_result, last_optimization_result))
    figure_asset_status_payload = _build_figure_asset_status_payload(
        session_id,
        session_info,
        _build_pipeline_status_data(False, session_info, last_standardization_result, dsm_result, last_evaluation_result, last_optimization_result),
    )
    if figure_asset_status_payload is not None:
        await manager.broadcast(figure_asset_status_payload)
    evaluation_summary_payload = _build_evaluation_summary_payload(session_id, session_info, last_evaluation_result)
    if evaluation_summary_payload is not None:
        await manager.broadcast(evaluation_summary_payload)
    architecture_recommendation_payload = _build_architecture_recommendation_payload(session_id, session_info, last_optimization_result)
    if architecture_recommendation_payload is not None:
        await manager.broadcast(architecture_recommendation_payload)

    return {
        'type': 'evaluation_analysis_response',
        'status': 'success' if last_evaluation_result.get('success') else 'failed',
        'result': last_evaluation_result,
        'optimization': last_optimization_result,
        'timestamp': int(time.time() * 1000)
    }


@app.post('/api/analysis/optimization')
async def run_optimization_analysis(request: OptimizationAnalysisRequest):
    global last_optimization_result

    session_dir = request.session_dir.strip()
    if not session_dir and request.session_id:
        session_dir = os.path.join(os.path.dirname(current_dir), 'Log', 'Records', request.session_id)

    if not session_dir:
        raise HTTPException(status_code=400, detail='缺少 session_dir 或 session_id')

    if not os.path.isdir(session_dir):
        raise HTTPException(status_code=404, detail=f'会话目录不存在: {session_dir}')

    session_info = {
        'data_directory': session_dir,
        'session_id': request.session_id or os.path.basename(session_dir),
        'case_id': os.path.basename(session_dir),
    }
    evaluation_result = {
        'status': 'ready' if os.path.exists(os.path.join(session_dir, 'analysis', 'evaluation_result.json')) else 'blocked'
    }
    last_optimization_result = _run_session_optimization(
        session_info,
        evaluation_result,
        baseline_profile_id=request.baseline_profile_id or None,
        current_profile_id=request.current_profile_id or None,
        pop_size=request.pop_size,
        n_gen=request.n_gen,
        seed=request.seed,
    )
    if last_optimization_result is None:
        raise HTTPException(status_code=500, detail='Optimization 分析未产生结果')

    _update_session_meta_status(
        session_info,
        standardization_result=last_standardization_result,
        dsm_result=last_dsm_result,
        evaluation_result=evaluation_result,
        optimization_result=last_optimization_result,
    )
    _persist_pipeline_status(
        session_info,
        _build_pipeline_status_data(False, session_info, last_standardization_result, last_dsm_result, evaluation_result, last_optimization_result),
    )

    session_id = request.session_id or os.path.basename(session_dir)
    await manager.broadcast(_build_pipeline_status_payload(False, session_id, session_info, last_standardization_result, last_dsm_result, evaluation_result, last_optimization_result))
    figure_asset_status_payload = _build_figure_asset_status_payload(
        session_id,
        session_info,
        _build_pipeline_status_data(False, session_info, last_standardization_result, last_dsm_result, evaluation_result, last_optimization_result),
    )
    if figure_asset_status_payload is not None:
        await manager.broadcast(figure_asset_status_payload)
    architecture_recommendation_payload = _build_architecture_recommendation_payload(session_id, session_info, last_optimization_result)
    if architecture_recommendation_payload is not None:
        await manager.broadcast(architecture_recommendation_payload)

    return {
        'type': 'optimization_analysis_response',
        'status': 'success' if last_optimization_result.get('success') else 'failed',
        'result': last_optimization_result,
        'timestamp': int(time.time() * 1000)
    }

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
                file_count = 0
                for _, _, files in os.walk(session_path):
                    file_count += len(files)
                
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
# 应用启动和关闭事件
# ================================================================

@app.on_event("startup")
async def startup_event():
    """应用启动"""
    global command_send_lock, command_last_send_at, command_channel_busy, udp_handler, udp_server_started
    
    logger.info("=" * 60)
    logger.info("Apollo GCS Web 后端启动")
    logger.info("=" * 60)
    
    # 初始化指令发送状态
    command_send_lock = asyncio.Lock()
    command_last_send_at = {
        'flight_control': 0.0,
        'planning': 0.0,
    }
    command_channel_busy = {
        'flight_control': False,
        'planning': False,
    }
    logger.info(
        f"指令发送节流已初始化（飞控/规划最小间隔 500ms，cmd_idx 连发 {CMD_IDX_REPEAT_COUNT} 次，末次置0={CMD_IDX_RESET_TO_ZERO}）"
    )
    logger.info("=" * 60)
    
    # 自动启动UDP服务器
    try:
        logger.info("正在自动启动UDP服务器...")
        
        # 初始化UDP处理器（如果尚未初始化）
        if udp_handler is None:
            udp_handler = UDPHandler(on_udp_message_received)
            logger.info("UDP处理器已初始化")
        
        # 启动UDP服务器，监听协议定义端口，并兼容历史联调端口
        ports = _normalize_listen_ports()
        
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
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )