"""
"""

import os
import csv
import json
import time
import re
import math
from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional
import struct
import logging
import recorder.csv_helper_full as csv_helper

logger = logging.getLogger(__name__)


RAW_METADATA_HEADERS = [
    'arrival_ts', 'record_id', 'session_id', 'case_id',
    'source_module', 'source_family', 'func_code', 'interface_name',
    'port_type', 'payload_size_bytes', 'parse_status', 'seq_id',
    'device_ts', 'mission_phase', 'normalized_refs',
    'relative_ts_ms', 'cycle_id', 'cycle_anchor_ts', 'cycle_offset_ms', 'cycle_packet_index'
]


WINDOW_METRICS_HEADERS = [
    'timestamp', 'case_id', 'mission_phase',
    'control_jitter_ms', 'attitude_peak_phi_deg',
    'planning_time_ms', 'planner_cycle_hz', 'tracking_rmse',
    'avoid_trigger_count', 'mission_switch_count', 'next_waypoint',
    'radar_fps', 'perception_latency_ms', 'obstacle_count', 'esc_power_pct_avg'
]

EVENT_HEADERS = [
    'timestamp', 'session_id', 'case_id', 'event_type', 'event_source', 'event_level', 'event_value', 'event_detail',
    'mission_phase', 'scenario_id', 'architecture_id', 'effective_task', 'scenario_evidence_tags'
]

FLIGHT_CONTROL_RAW_HEADERS = RAW_METADATA_HEADERS + csv_helper.get_full_header().split(',') + ['payload_json']

PLANNING_RAW_HEADERS = RAW_METADATA_HEADERS + [
    'timestamp_remote', 'current_pos_x', 'current_pos_y', 'current_pos_z',
    'current_vel', 'update_flags', 'status', 'global_path_count',
    'local_traj_count', 'obstacle_count', 'global_path_json',
    'local_path_json', 'obstacles_json', 'payload_json'
]

RADAR_RAW_HEADERS = RAW_METADATA_HEADERS + [
    'msg_type', 'obstacle_count', 'frame_id', 'timestamp_sec',
    'processing_time_ms', 'frame_rate', 'input_points', 'filtered_points',
    'is_running', 'obstacle_input_connected', 'error_code', 'payload_json'
]

PERCEPTION_RAW_HEADERS = RAW_METADATA_HEADERS + ['msg_type', 'payload_json']

RAW_STREAM_FILENAMES = {
    'flight_control_raw': 'flight_control_raw.jsonl',
    'planning_raw': 'planning_raw.jsonl',
    'radar_raw': 'radar_raw.jsonl',
    'perception_raw': 'perception_raw.jsonl',
}

RAW_STREAM_TABLE_FILENAMES = {
    'flight_control_raw': 'flight_control_raw.csv',
    'planning_raw': 'planning_raw.csv',
    'radar_raw': 'radar_raw.csv',
    'perception_raw': 'perception_raw.csv',
}

RAW_STREAM_TABLE_HEADERS = {
    'flight_control_raw': FLIGHT_CONTROL_RAW_HEADERS,
    'planning_raw': PLANNING_RAW_HEADERS,
    'radar_raw': RADAR_RAW_HEADERS,
    'perception_raw': PERCEPTION_RAW_HEADERS,
}

RECORD_STREAM_FILENAMES = {
    'window_metrics': 'window_metrics.csv',
    'event_stream': 'event_stream.csv',
    'bus_traffic': 'bus_traffic.csv',
}

FCS_VIEW_PRIMER_TYPES = (
    'fcs_pwms',
    'fcs_states',
    'fcs_datactrl',
    'fcs_gncbus',
    'avoiflag',
    'fcs_datafutaba',
    'fcs_param',
    'fcs_line_aim2ab',
    'fcs_line_ab',
    'fcs_datagcs',
)

FCS_VIEW_SNAPSHOT_TRIGGER_TYPES = {
    'fcs_param',
    'fcs_root',
}

FCS_VIEW_MEANINGFUL_TYPES = {
    'fcs_states',
    'fcs_datactrl',
    'fcs_gncbus',
    'avoiflag',
    'fcs_datafutaba',
    'fcs_param',
    'fcs_line_aim2ab',
    'fcs_line_ab',
    'fcs_datagcs',
}

SCHEMA_VERSION = 'v1.0'
SOFTWARE_VERSION = 'apollo-gcs-web-backend-dev'
CONTRACT_VERSION = 'v1.0'


def build_event_stream_paths(session_dir: str) -> Dict[str, str]:
    analysis_runtime_dir = os.path.join(session_dir, ANALYSIS_OUTPUT_DIRNAME, RUNTIME_OUTPUT_DIRNAME)
    return {
        'canonical': os.path.join(session_dir, RECORD_STREAM_FILENAMES['event_stream']),
        'legacy_runtime': os.path.join(analysis_runtime_dir, RECORD_STREAM_FILENAMES['event_stream']),
    }


def _derive_scenario_stress_level(payload: Optional[Dict[str, Any]]) -> str:
    meta = payload or {}
    score = 0
    if str(meta.get('obstacle_density', '')).strip().lower() == 'high':
        score += 2
    elif str(meta.get('obstacle_density', '')).strip().lower() == 'medium':
        score += 1

    if str(meta.get('wind_level', '')).strip().lower() == 'high':
        score += 2
    elif str(meta.get('wind_level', '')).strip().lower() == 'medium':
        score += 1

    if str(meta.get('link_quality', '')).strip().lower() == 'degraded':
        score += 2
    if str(meta.get('sensor_quality', '')).strip().lower() == 'degraded':
        score += 2

    disturbance_parts = [part for part in re.split(r'[+,;|]', str(meta.get('disturbance_profile', '') or '')) if part.strip()]
    if len(disturbance_parts) >= 3:
        score += 2
    elif len(disturbance_parts) >= 2:
        score += 1

    if score >= 6:
        return 'high'
    if score >= 3:
        return 'medium'
    if score > 0:
        return 'low'
    return 'nominal'


def normalize_session_meta_for_thesis(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = dict(payload or {})
    session_dir = str(meta.get('session_directory') or meta.get('session_dir') or meta.get('data_directory') or '')
    record_layout = meta.setdefault('record_layout', {})
    if session_dir:
        event_paths = build_event_stream_paths(session_dir)
        record_layout.setdefault('event_stream', event_paths['canonical'])
        record_layout.setdefault('analysis_runtime_event_stream', event_paths['legacy_runtime'])

    figure_asset_status = str(meta.get('figure_asset_status', '') or '').strip().lower()
    if not figure_asset_status:
        if meta.get('figure_asset_ready') is True:
            figure_asset_status = 'ready'
        elif meta.get('figure_asset_ready') is False:
            figure_asset_status = 'blocked'
    if figure_asset_status:
        meta['figure_asset_status'] = figure_asset_status
        meta['figure_asset_ready'] = figure_asset_status == 'ready'

    architecture_profiles = meta.get('architecture_profiles') or {}
    baseline_profiles = architecture_profiles.get('baseline_profiles') or []
    candidate_profiles = architecture_profiles.get('candidate_profiles') or []
    research_profiles = architecture_profiles.get('research_profiles') or []
    planned_case = meta.get('planned_case') or {}
    runtime_architecture = meta.get('runtime_architecture') or {}

    baseline_architecture_id = (
        meta.get('baseline_architecture_id')
        or meta.get('baseline_allocation_id')
        or (baseline_profiles[0].get('profile_id') if baseline_profiles else '')
        or 'native'
    )
    if baseline_architecture_id:
        meta['baseline_architecture_id'] = str(baseline_architecture_id)

    candidate_ids = meta.get('candidate_architecture_ids')
    if not isinstance(candidate_ids, list) or not candidate_ids:
        candidate_ids = []
        for value in [
            meta.get('candidate_allocation_id'),
            meta.get('current_allocation_id'),
            meta.get('recommended_allocation_id'),
            meta.get('canonical_profile_id'),
            runtime_architecture.get('profile_id'),
            runtime_architecture.get('canonical_profile_id'),
            planned_case.get('canonical_profile_id'),
            meta.get('architecture_id'),
        ]:
            if value:
                candidate_ids.append(str(value))
        if not candidate_ids:
            candidate_ids = [
                str(item.get('profile_id'))
                for item in [*candidate_profiles, *research_profiles]
                if item.get('profile_id')
            ]
    meta['candidate_architecture_ids'] = list(dict.fromkeys(str(value) for value in candidate_ids if value))

    if not meta.get('scenario_stress_level'):
        meta['scenario_stress_level'] = _derive_scenario_stress_level(meta)

    return meta

RAW_OUTPUT_DIRNAME = 'raw'
BUS_OUTPUT_DIRNAME = 'bus'
RECORDS_OUTPUT_DIRNAME = 'records'
FCS_OUTPUT_DIRNAME = 'fcs'
LIDAR_OUTPUT_DIRNAME = 'lidar'
CAMERA_OUTPUT_DIRNAME = 'camera'
ANALYSIS_OUTPUT_DIRNAME = 'analysis'
RUNTIME_OUTPUT_DIRNAME = 'runtime'
PLANNING_OUTPUT_DIRNAME = 'planning'
PLANNING_TRAJECTORY_DT_SECONDS = 0.01

FCS_ONBOARD_EXTRA_HEADERS = [
    'ParamAil_YaccLMT',
    'ParamEle_XaccLMT',
    'ParamGuide_Hground',
    'ParamGuide_AutoTakeoffHcmd',
    'ftb_intterrupt_plan',
    'TimeStamp',
    'receive_time',
]

PLANNING_TELEMETRY_HEADERS = [
    'timestamp_local', 'seq_id', 'timestamp_remote', 'scenario', 'cpu_usage', 'waypoint_idx',
    'planning_mode', 'global_path_count', 'local_traj_count', 'obstacle_count', 'status', 'cmd_idx', 'cmd_mission'
]

LIDAR_TELEMETRY_HEADERS = [
    'timestamp_local', 'scenario', 'cmd_idx', 'cmd_mission', 'msg_type', 'frame_id', 'timestamp_sec',
    'proc_time_ms', 'fps', 'points_in', 'points_out', 'is_running', 'lidar_connected',
    'error_code', 'obstacles_json', 'performance_json', 'obs_count', 'obs_density'
]


def _rename_fcs_onboard_header(header_name: str) -> str:
    if header_name == 'timestamp':
        return 'time'
    if header_name.startswith('pwm') and header_name[3:].isdigit():
        return f"pwms_{int(header_name[3:]) - 1}"
    return header_name


def _get_fcs_onboard_headers() -> List[str]:
    headers: List[str] = []
    for header_name in csv_helper.get_full_header().split(','):
        if header_name.startswith('esc'):
            continue
        headers.append(_rename_fcs_onboard_header(header_name))
    headers.extend(FCS_ONBOARD_EXTRA_HEADERS)
    return headers


FUNC_CODE_NAMES = {
    0x41: 'NCLINK_RECEIVE_EXTY_FCS_PWMS',
    0x42: 'NCLINK_RECEIVE_EXTY_FCS_STATES',
    0x43: 'NCLINK_RECEIVE_EXTY_FCS_DATACTRL',
    0x44: 'NCLINK_RECEIVE_EXTY_FCS_GNCBUS',
    0x45: 'NCLINK_RECEIVE_EXTY_FCS_AVOIFLAG',
    0x46: 'NCLINK_RECEIVE_EXTY_FCS_DATAGCS',
    0x47: 'NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AIM2AB',
    0x48: 'NCLINK_RECEIVE_EXTY_FCS_LINESTRUC_AB',
    0x49: 'NCLINK_RECEIVE_EXTY_FCS_PARAM',
    0x4A: 'NCLINK_RECEIVE_EXTY_FCS_ROOT',
    0x4B: 'NCLINK_RECEIVE_EXTY_FCS_ESC',
    0x70: 'NCLINK_GCS_COMMAND',
    0x71: 'NCLINK_GCS_TELEMETRY',
}


BUS_LOGICAL_ROUTE_MAP = {
    'fcs_pwms': ('LF_Flight_Control', 'LF_Motor_Driver'),
    'fcs_states': ('LF_INS_Parser', 'LF_Flight_Control'),
    'fcs_datactrl': ('LF_RC_Parser', 'LF_Flight_Control'),
    'fcs_gncbus': ('LF_Flight_Control', 'LF_SoC_Adapter'),
    'avoiflag': ('LF_Flight_Control', 'LF_Path_Planning'),
    'fcs_datafutaba': ('LF_Communication', 'LF_Flight_Control'),
    'fcs_datagcs': ('LF_Communication', 'LF_Path_Planning'),
    'fcs_line_aim2ab': ('LF_Path_Planning', 'LF_Flight_Control'),
    'fcs_line_ab': ('LF_Path_Planning', 'LF_Flight_Control'),
    'fcs_param': ('LF_Flight_Control', 'LF_SoC_Adapter'),
    'fcs_root': ('LF_Flight_Control', 'LF_SoC_Adapter'),
    'planning_telemetry': ('LF_Path_Planning', 'LF_Flight_Control'),
}


class RawDataRecorder:
    """
    原始数据录制器
    
    核心功能：
    1. 按数据类型分文件存储（CSV格式）
    2. 支持多种数据类型：flight_perf、resources、bus_traffic、obstacles
    3. 自动创建文件目录和表头
    4. 高效写入，避免频繁打开关闭文件
    """
    
    def __init__(
        self,
        session_id: str,
        base_directory: str = "data",
        case_id_override: Optional[str] = None,
        plan_case_id: Optional[str] = None,
        session_meta_patch: Optional[dict] = None,
    ):
        """
        初始化录制器
        
        Args:
            session_id: 会话ID，用于创建子文件夹
            base_directory: 基础数据目录
        """
        self.session_id = session_id
        self.base_directory = base_directory
        self.session_meta_patch = dict(session_meta_patch or {})
        self.runtime_context = {}
        self.session_directory = os.path.join(base_directory, session_id)
        self.analysis_directory = os.path.join(self.session_directory, ANALYSIS_OUTPUT_DIRNAME)
        self.runtime_directory = os.path.join(self.analysis_directory, RUNTIME_OUTPUT_DIRNAME)
        self.records_directory = os.path.join(self.session_directory, RECORDS_OUTPUT_DIRNAME)
        self.raw_directory = os.path.join(self.records_directory, RAW_OUTPUT_DIRNAME)
        self.bus_directory = os.path.join(self.records_directory, BUS_OUTPUT_DIRNAME)
        self.fcs_directory = os.path.join(self.records_directory, FCS_OUTPUT_DIRNAME)
        self.planning_directory = os.path.join(self.records_directory, PLANNING_OUTPUT_DIRNAME)
        self.lidar_directory = os.path.join(self.records_directory, LIDAR_OUTPUT_DIRNAME)
        self.camera_directory = os.path.join(self.records_directory, CAMERA_OUTPUT_DIRNAME)
        self.is_recording = False
        
        # 创建会话目录
        os.makedirs(self.session_directory, exist_ok=True)
        os.makedirs(self.analysis_directory, exist_ok=True)
        os.makedirs(self.runtime_directory, exist_ok=True)
        os.makedirs(self.records_directory, exist_ok=True)
        os.makedirs(self.bus_directory, exist_ok=True)
        os.makedirs(self.fcs_directory, exist_ok=True)
        os.makedirs(self.planning_directory, exist_ok=True)
        os.makedirs(self.lidar_directory, exist_ok=True)
        os.makedirs(self.camera_directory, exist_ok=True)
        
        # 文件句柄和写入器
        self.file_handles: Dict[str, object] = {}
        self.csv_writers: Dict[str, object] = {}
        self.raw_jsonl_handles: Dict[str, object] = {}
        self.raw_csv_file_handles: Dict[str, object] = {}
        self.raw_csv_writers: Dict[str, object] = {}
        self.function_file_handles: Dict[int, object] = {}
        self.function_csv_writers: Dict[int, object] = {}
        self.raw_stream_keys = [
            'flight_control_raw',
            'planning_raw',
            'radar_raw',
            'perception_raw',
        ]
        self.function_directory = os.path.join(self.records_directory, "function_packets")
        os.makedirs(self.function_directory, exist_ok=True)
        self.case_id = case_id_override or self._allocate_case_id()
        self.plan_case_id = plan_case_id or self.session_meta_patch.get('plan_case_id')
        self.enabled_ports = []
        self.recording_label = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 数据计数器
        self.data_counters = defaultdict(int)
        self.func_code_stats = defaultdict(lambda: {
            'func_name': 'unknown',
            'packet_count': 0,
            'total_bytes': 0,
            'last_msg_type': 'unknown'
        })
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # 频率计算缓存 {msg_id: last_timestamp}
        self.last_msg_times = defaultdict(float)
        self.current_frequencies = defaultdict(float)
        self.fcs_cache = []
        self.fcs_cycle_seen = set()
        self.fcs_snapshot_pending = False
        self.fcs_cycle_id = 0
        self.fcs_cycle_anchor_ts: Optional[int] = None
        self.fcs_cycle_packet_index = 0
        self.fcs_cycle_open = False
        self.fcs_last_receive_time = ''
        self.fcs_last_timestamp_ms = ''
        self.fcs_root_snapshot = {
            'ParamAil_YaccLMT': '',
            'ParamEle_XaccLMT': '',
            'ParamGuide_Hground': '',
            'ParamGuide_AutoTakeoffHcmd': '',
            'ftb_intterrupt_plan': '',
        }

        logger.info(f"数据录制器初始化完成: {self.session_directory}")
    
    # ----------------------------------------------------------------
    # 节点定义 (Aligned with Hardware Architecture & DSM)
    # ----------------------------------------------------------------
    NODE_MCU = 1      # MCU (Flight Control, Motor Drivers, Sensors)
    NODE_GCS = 2      # Ground Station (Data Consumer)
    NODE_SOC = 3      # SoC (Planning, Radar/Camera Algo, AI)
    NODE_UNKNOWN = 0  # Unknown

    def _get_bus_info(self, decoded_data: dict) -> dict:
        """
        根据消息类型推断总线信息 (源节点、目标节点、消息ID)
        Logic: Reflects Physical Data Links (MCU->GCS, SoC->GCS)
        """
        node_info = {
            'source': self.NODE_UNKNOWN,
            'target': self.NODE_GCS, # Default downlink to GCS
            'msg_id': 0
        }
        msg_type = decoded_data.get('type', 'unknown')
        data = decoded_data.get('data', {})
        port_type = decoded_data.get('port_type')
        
        # 获取消息ID (func_code)
        if 'func_code' in decoded_data:
            node_info['msg_id'] = decoded_data['func_code']
        
        # 1. MCU Domain Data (fcs_*)
        # 对应 DSM 节点: LF_Flight_Algo, LF_Motor_Driver, LF_MCU_Comm等
        if msg_type.startswith('fcs_'):
            node_info['source'] = self.NODE_MCU
            if not node_info['msg_id']:
                # 尝试映射常见类型到ID (如果func_code缺失)
                type_map = {
                    'fcs_pwms': 65,         # LF_Motor_Driver Output
                    'fcs_states': 66,       # LF_INS_Parser Output
                    'fcs_datactrl': 67,     # LF_Flight_Algo Output
                    'fcs_gncbus': 68,       # LF_MCU_Comm (Internal Bus Dump)
                    'avoiflag': 69,         # Avoidance Flag
                    'fcs_datafutaba': 70,   # LF_RC_Parser Output
                    'fcs_line_aim2ab': 71,
                    'fcs_line_ab': 72,
                    'fcs_param': 73,
                }
                node_info['msg_id'] = type_map.get(msg_type, 0)
                
        # 2. SoC Domain: Planning (planning_telemetry)
        # 对应 DSM 节点: LF_Planning_Algo
        elif msg_type == 'planning_telemetry':
            node_info['source'] = self.NODE_SOC
            node_info['msg_id'] = node_info['msg_id'] or 0x71
            
        # 3. 避障标志 (通常由飞控MCU决策输出，或者SoC透传)
        elif msg_type == 'avoiflag':
            node_info['source'] = self.NODE_MCU
            node_info['msg_id'] = 0x45

        if port_type is not None:
            port_name = getattr(port_type, 'name', str(port_type))
            if 'LIDAR' in port_name or 'PLANNING' in port_name:
                node_info['source'] = self.NODE_SOC
            elif 'TELEMETRY' in port_name or 'RECEIVE' in port_name:
                node_info['source'] = self.NODE_MCU
            
        return node_info

    def start_recording(self):
        """开始录制，打开所有文件"""
        if self.is_recording:
            logger.warning(f"录制已在进行中: {self.session_id}")
            return
        
        self.is_recording = True
        self.start_time = time.time()

        self._init_fcs_cycle_cache()
        self._init_fcs_telemetry_file()
        self._init_planning_telemetry_file()
        self._init_lidar_telemetry_file()
        self._init_window_metrics_file()
        self._init_events_file()

        self._write_session_meta()

        logger.info(f"开始录制: {self.session_id}")
    
    def stop_recording(self):
        """停止录制，关闭所有文件"""
        if not self.is_recording:
            logger.warning(f"录制未开始: {self.session_id}")
            return
        self._flush_fcs_snapshot_if_pending()
        
        self.is_recording = False
        self.end_time = time.time()
        
        # 关闭所有文件
        for file_handle in self.file_handles.values():
            try:
                file_handle.close()
            except Exception as e:
                logger.error(f"关闭文件失败: {e}")

        for file_handle in self.function_file_handles.values():
            try:
                file_handle.close()
            except Exception as e:
                logger.error(f"关闭功能字文件失败: {e}")

        for file_handle in self.raw_jsonl_handles.values():
            try:
                file_handle.close()
            except Exception as e:
                logger.error(f"关闭原始数据流文件失败: {e}")

        for file_handle in self.raw_csv_file_handles.values():
            try:
                file_handle.close()
            except Exception as e:
                logger.error(f"关闭原始数据CSV文件失败: {e}")
        
        self.file_handles.clear()
        self.csv_writers.clear()
        self.raw_jsonl_handles.clear()
        self.raw_csv_file_handles.clear()
        self.raw_csv_writers.clear()
        self.function_file_handles.clear()
        self.function_csv_writers.clear()

        self._write_session_meta()
        self._write_data_quality_report()
        
        duration = self.end_time - self.start_time if self.start_time else 0
        logger.info(f"录制已停止: {self.session_id}, 时长: {duration:.2f}秒")
        logger.info(f"数据统计: {dict(self.data_counters)}")
    

    def _init_fcs_cycle_cache(self):
        """初始化飞控周期缓存，用于生成 onboard 兼容快照。"""
        header = csv_helper.get_full_header()
        self.fcs_cache = self._build_initial_fcs_cache(header)
        self.fcs_cycle_seen.clear()
        self.fcs_snapshot_pending = False

    def _init_fcs_telemetry_file(self):
        filepath = os.path.join(self.fcs_directory, 'fcs_telemetry.csv')
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        writer.writerow(_get_fcs_onboard_headers())
        self.file_handles['fcs_telemetry'] = file_handle
        self.csv_writers['fcs_telemetry'] = writer

    def _build_initial_fcs_cache(self, header: str) -> list:
        cache = [""] * len(header.split(','))
        for msg_type in FCS_VIEW_PRIMER_TYPES:
            csv_helper.update_cache_and_get_line(msg_type, {'timestamp': '', 'data': {}}, cache)
        if cache:
            cache[0] = ''
        return cache

    def _has_meaningful_fcs_cycle(self) -> bool:
        return any(msg_type in FCS_VIEW_MEANINGFUL_TYPES for msg_type in self.fcs_cycle_seen)

    def _write_fcs_view_snapshot(self):
        self._write_fcs_telemetry_snapshot()

    def _write_fcs_telemetry_snapshot(self):
        writer = self.csv_writers.get('fcs_telemetry')
        if writer is None:
            return

        source_headers = csv_helper.get_full_header().split(',')
        cache_map = {
            header_name: (self.fcs_cache[index] if index < len(self.fcs_cache) else '')
            for index, header_name in enumerate(source_headers)
        }

        relative_seconds = 0.0
        if self.start_time and self.fcs_last_timestamp_ms:
            relative_seconds = max(0.0, (float(self.fcs_last_timestamp_ms) - (self.start_time * 1000.0)) / 1000.0)

        row = [f"{relative_seconds:.6f}"]
        for header_name in source_headers[1:]:
            if header_name.startswith('esc'):
                continue
            row.append(cache_map.get(header_name, ''))

        row.extend([
            self.fcs_root_snapshot.get('ParamAil_YaccLMT', ''),
            self.fcs_root_snapshot.get('ParamEle_XaccLMT', ''),
            self.fcs_root_snapshot.get('ParamGuide_Hground', ''),
            self.fcs_root_snapshot.get('ParamGuide_AutoTakeoffHcmd', ''),
            self.fcs_root_snapshot.get('ftb_intterrupt_plan', ''),
            self.fcs_last_timestamp_ms,
            self.fcs_last_receive_time,
        ])
        writer.writerow(row)
        self.data_counters['fcs_telemetry'] = self.data_counters.get('fcs_telemetry', 0) + 1
        if self.data_counters['fcs_telemetry'] % 50 == 0:
            self.file_handles['fcs_telemetry'].flush()

    def _flush_fcs_snapshot_if_pending(self):
        if not self.fcs_snapshot_pending:
            return
        if not self._has_meaningful_fcs_cycle():
            self.fcs_cycle_seen.clear()
            self.fcs_snapshot_pending = False
            return
        self._write_fcs_view_snapshot()
        self.fcs_cycle_seen.clear()
        self.fcs_snapshot_pending = False

    def _init_planning_telemetry_file(self):
        filepath = os.path.join(self.planning_directory, 'planning_telemetry.csv')
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        writer.writerow(PLANNING_TELEMETRY_HEADERS)
        self.file_handles['planning_telemetry'] = file_handle
        self.csv_writers['planning_telemetry'] = writer

    def _init_lidar_telemetry_file(self):
        filepath = os.path.join(self.lidar_directory, 'radar_data.csv')
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        writer.writerow(LIDAR_TELEMETRY_HEADERS)
        self.file_handles['radar_data'] = file_handle
        self.csv_writers['radar_data'] = writer

    def _init_window_metrics_file(self):
        filepath = os.path.join(self.runtime_directory, RECORD_STREAM_FILENAMES['window_metrics'])
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        writer.writerow(WINDOW_METRICS_HEADERS)
        self.file_handles['window_metrics'] = file_handle
        self.csv_writers['window_metrics'] = writer

    def _init_events_file(self):
        event_paths = build_event_stream_paths(self.session_directory)

        filepath = event_paths['canonical']
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        writer.writerow(EVENT_HEADERS)
        self.file_handles['event_stream'] = file_handle
        self.csv_writers['event_stream'] = writer

        legacy_path = event_paths['legacy_runtime']
        if os.path.normpath(legacy_path) != os.path.normpath(filepath):
            os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
            legacy_handle = open(legacy_path, 'w', newline='', encoding='utf-8')
            legacy_writer = csv.writer(legacy_handle)
            legacy_writer.writerow(EVENT_HEADERS)
            self.file_handles['event_stream_legacy_runtime'] = legacy_handle
            self.csv_writers['event_stream_legacy_runtime'] = legacy_writer

    def _init_raw_stream_tables(self):
        for stream_key, filename in RAW_STREAM_TABLE_FILENAMES.items():
            file_path = os.path.join(self.raw_directory, filename)
            file_handle = open(file_path, 'w', newline='', encoding='utf-8')
            writer = csv.writer(file_handle)
            writer.writerow(RAW_STREAM_TABLE_HEADERS[stream_key])
            self.raw_csv_file_handles[stream_key] = file_handle
            self.raw_csv_writers[stream_key] = writer

    
    def _init_flight_perf_file(self):
        """初始化飞行性能数据文件"""
        filepath = os.path.join(self.session_directory, "flight_perf.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'lat', 'lon', 'alt',
            'target_lat', 'target_lon', 'target_alt',
            'roll', 'pitch', 'yaw'
        ])
        
        self.file_handles['flight_perf'] = file_handle
        self.csv_writers['flight_perf'] = writer
    
    def _init_resources_file(self):
        """初始化资源数据文件（CPU、内存等）"""
        filepath = os.path.join(self.session_directory, "resources.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'node_id', 'cpu_load', 'memory_usage',
            'exec_time_us', 'task_id'
        ])
        
        self.file_handles['resources'] = file_handle
        self.csv_writers['resources'] = writer
    
    def _init_bus_traffic_file(self):
        """初始化总线通信数据文件"""
        filepath = os.path.join(self.bus_directory, RECORD_STREAM_FILENAMES['bus_traffic'])
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'msg_id', 'msg_size', 'source_node', 'target_node',
            'source_module', 'target_module', 'frequency', 'latency_ms',
            'msg_type', 'port_type', 'seq_id', 'func_name'
        ])
        
        self.file_handles['bus_traffic'] = file_handle
        self.csv_writers['bus_traffic'] = writer

    def _ensure_view_writer(self, key: str):
        if key == 'window_metrics' and key not in self.file_handles:
            self._init_window_metrics_file()
        elif key == 'event_stream' and key not in self.file_handles:
            self._init_events_file()
        elif key == 'bus_traffic' and key not in self.file_handles:
            self._init_bus_traffic_file()

    def _as_epoch_seconds(self, arrival_ts_ms: Optional[int]) -> float:
        if arrival_ts_ms is None:
            return time.time()
        return float(arrival_ts_ms) / 1000.0

    def _serialize_json_compact(self, payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))

    def _normalize_path_points(self, points: Any) -> List[Dict[str, float]]:
        normalized: List[Dict[str, float]] = []
        if not isinstance(points, list):
            return normalized
        for point in points:
            if not isinstance(point, dict):
                continue
            normalized.append({
                'x': float(point.get('x', 0.0)),
                'y': float(point.get('y', 0.0)),
                'z': float(point.get('z', 0.0)),
            })
        return normalized

    def _normalize_obstacles(self, obstacles: Any) -> List[Dict[str, float]]:
        normalized: List[Dict[str, float]] = []
        if not isinstance(obstacles, list):
            return normalized
        for obstacle in obstacles:
            if not isinstance(obstacle, dict):
                continue
            center = obstacle.get('center', {}) or {}
            size = obstacle.get('size', {}) or {}
            velocity = obstacle.get('velocity', {}) or {}
            normalized.append({
                'cx': float(center.get('x', 0.0)),
                'cy': float(center.get('y', 0.0)),
                'cz': float(center.get('z', 0.0)),
                'sx': float(size.get('x', 0.0)),
                'sy': float(size.get('y', 0.0)),
                'sz': float(size.get('z', 0.0)),
                'vx': float(velocity.get('x', 0.0)),
                'vy': float(velocity.get('y', 0.0)),
                'vz': float(velocity.get('z', 0.0)),
            })
        return normalized

    def _derive_trajectory_kinematics(self, points: List[Dict[str, float]], dt_seconds: float = PLANNING_TRAJECTORY_DT_SECONDS) -> List[Dict[str, float]]:
        if not points:
            return []

        velocities = []
        accelerations = []
        for index, point in enumerate(points):
            if index + 1 < len(points):
                next_point = points[index + 1]
                velocity = (
                    (next_point['x'] - point['x']) / dt_seconds,
                    (next_point['y'] - point['y']) / dt_seconds,
                    (next_point['z'] - point['z']) / dt_seconds,
                )
            elif velocities:
                velocity = velocities[-1]
            else:
                velocity = (0.0, 0.0, 0.0)
            velocities.append(velocity)

        for index, velocity in enumerate(velocities):
            if index + 1 < len(velocities):
                next_velocity = velocities[index + 1]
                acceleration = (
                    (next_velocity[0] - velocity[0]) / dt_seconds,
                    (next_velocity[1] - velocity[1]) / dt_seconds,
                    (next_velocity[2] - velocity[2]) / dt_seconds,
                )
            elif accelerations:
                acceleration = accelerations[-1]
            else:
                acceleration = (0.0, 0.0, 0.0)
            accelerations.append(acceleration)

        derived_points = []
        for index, point in enumerate(points):
            vx, vy, vz = velocities[index]
            ax, ay, az = accelerations[index]
            horizontal_speed = math.sqrt((vx * vx) + (vy * vy))
            speed = math.sqrt((horizontal_speed * horizontal_speed) + (vz * vz))
            yaw = math.atan2(vy, vx) if speed > 0.0 else 0.0
            pitch = math.atan2(vz, horizontal_speed) if speed > 0.0 else 0.0
            derived_points.append({
                'x': point['x'],
                'y': point['y'],
                'z': point['z'],
                'vx': vx,
                'vy': vy,
                'vz': vz,
                'speed': speed,
                'yaw': yaw,
                'pitch': pitch,
                'ax': ax,
                'ay': ay,
                'az': az,
            })
        return derived_points

    def _get_planning_local_path(self, data: dict) -> List[dict]:
        return self._normalize_path_points(data.get('local_path') or data.get('local_traj') or [])

    def _default_scenario(self) -> str:
        return str(self.session_meta_patch.get('scenario_id', self.plan_case_id or self.case_id or ''))

    def _default_cmd_idx(self) -> Any:
        planned_case = self.session_meta_patch.get('planned_case', {}) if isinstance(self.session_meta_patch, dict) else {}
        return planned_case.get('cmd_idx', self.session_meta_patch.get('cmd_idx', ''))

    def _default_cmd_mission(self) -> Any:
        planned_case = self.session_meta_patch.get('planned_case', {}) if isinstance(self.session_meta_patch, dict) else {}
        return planned_case.get('mission_id', self.session_meta_patch.get('cmd_mission', ''))

    def _write_planning_telemetry_row(self, data: dict, arrival_ts_ms: Optional[int]) -> None:
        writer = self.csv_writers.get('planning_telemetry')
        if writer is None:
            return

        local_path = self._get_planning_local_path(data)
        global_path = self._normalize_path_points(data.get('global_path', []))
        obstacles = data.get('obstacles', []) if isinstance(data.get('obstacles', []), list) else []
        waypoint_idx = data.get('waypoint_idx', data.get('current_waypoint_idx', ''))
        planning_mode = data.get('planning_mode', data.get('update_flags', data.get('status', '')))
        obstacle_count = data.get('obstacle_count', len(obstacles))
        timestamp_local = f'{self._as_epoch_seconds(arrival_ts_ms):.6f}' if arrival_ts_ms is not None else ''

        writer.writerow([
            timestamp_local,
            data.get('seq_id', ''),
            data.get('timestamp', ''),
            self._default_scenario(),
            data.get('cpu_usage', ''),
            waypoint_idx,
            planning_mode,
            data.get('global_path_count', len(global_path)),
            data.get('local_traj_count', len(local_path)),
            obstacle_count,
            data.get('status', ''),
            data.get('Tele_GCS_CmdIdx', data.get('cmd_idx', self._default_cmd_idx())),
            data.get('Tele_GCS_Mission', data.get('Mission', self._default_cmd_mission())),
        ])

        self.data_counters['planning_telemetry'] += 1
        if self.data_counters['planning_telemetry'] % 20 == 0:
            self.file_handles['planning_telemetry'].flush()

    def _write_lidar_telemetry_row(self, data: dict, arrival_ts_ms: Optional[int]) -> None:
        writer = self.csv_writers.get('radar_data')
        if writer is None:
            return

        obstacles = data.get('obstacles', []) if isinstance(data.get('obstacles', []), list) else []
        obs_count = int(data.get('obstacle_count', len(obstacles)) or 0)
        performance = {
            'stage1_source': 'planning_telemetry',
            'derived_from': 'planning obstacles',
        }
        timestamp_local = f'{self._as_epoch_seconds(arrival_ts_ms):.6f}' if arrival_ts_ms is not None else ''
        timestamp_sec = f'{float(arrival_ts_ms) / 1000.0:.6f}' if arrival_ts_ms is not None else ''

        writer.writerow([
            timestamp_local,
            self._default_scenario(),
            data.get('Tele_GCS_CmdIdx', data.get('cmd_idx', self._default_cmd_idx())),
            data.get('Tele_GCS_Mission', data.get('Mission', self._default_cmd_mission())),
            'planning_obstacle_flow',
            data.get('seq_id', ''),
            timestamp_sec,
            data.get('planning_time_ms', data.get('proc_time_ms', 0)),
            data.get('fps', 0),
            data.get('input_points', 0),
            data.get('filtered_points', 0),
            1,
            1,
            '',
            json.dumps(obstacles, ensure_ascii=False, separators=(',', ':')),
            json.dumps(performance, ensure_ascii=False, separators=(',', ':')),
            obs_count,
            obs_count,
        ])

        self.data_counters['radar_data'] += 1
        if self.data_counters['radar_data'] % 20 == 0:
            self.file_handles['radar_data'].flush()

    def _ensure_function_directory(self):
        os.makedirs(self.function_directory, exist_ok=True)

    def _build_case_id(self) -> str:
        return self.case_id

    def _allocate_case_id(self) -> str:
        session_date = self._extract_session_date()
        existing_meta_path = os.path.join(self.session_directory, 'session_meta.json')
        if os.path.exists(existing_meta_path):
            try:
                with open(existing_meta_path, 'r', encoding='utf-8') as meta_file:
                    existing_case_id = json.load(meta_file).get('case_id')
                match = re.match(r'^case(\d{3,4})(?:_\d{8})?$', str(existing_case_id or ''))
                if match:
                    return f"case{int(match.group(1)):03d}_{session_date}"
            except Exception:
                pass

        max_case_index = 0
        session_count = 0
        if os.path.isdir(self.base_directory):
            for child_name in os.listdir(self.base_directory):
                child_path = os.path.join(self.base_directory, child_name)
                if not os.path.isdir(child_path) or child_name == self.session_id:
                    continue
                session_count += 1
                meta_path = os.path.join(child_path, 'session_meta.json')
                if not os.path.exists(meta_path):
                    continue
                try:
                    with open(meta_path, 'r', encoding='utf-8') as meta_file:
                        case_id = json.load(meta_file).get('case_id', '')
                    match = re.match(r'^case(\d{3,4})(?:_\d{8})?$', str(case_id))
                    if match:
                        max_case_index = max(max_case_index, int(match.group(1)))
                except Exception:
                    continue

        return f"case{max(max_case_index, session_count) + 1:03d}_{session_date}"

    def _extract_session_date(self) -> str:
        match = re.search(r'(\d{8})', self.session_id)
        if match:
            return match.group(1)
        return datetime.now().strftime('%Y%m%d')

    def _build_mission_phase(self, mission_id: Optional[int]) -> str:
        mission_map = {
            0: 'idle',
            1: 'manual',
            2: 'standby',
            3: 'guided',
            4: 'takeoff',
            5: 'cruise',
            6: 'descent',
            14: 'auto_takeoff',
            15: 'auto_landing',
            16: 'hover',
            24: 'avoidance_enabled',
            25: 'avoidance_disabled',
        }
        mission_key = int(mission_id or 0)
        return mission_map.get(mission_key, f'mission_{mission_key}')

    def _write_session_meta(self):
        meta_path = os.path.join(self.session_directory, 'session_meta.json')
        event_paths = build_event_stream_paths(self.session_directory)
        payload = {
            'session_id': self.session_id,
            'case_id': self._build_case_id(),
            'plan_case_id': self.plan_case_id,
            'session_directory': self.session_directory,
            'schema_version': SCHEMA_VERSION,
            'contract_version': CONTRACT_VERSION,
            'record_layout_version': 'v4',
            'record_layout': {
                'records_root': self.records_directory,
                'bus': self.bus_directory,
                'function_packets': self.function_directory,
                'fcs': self.fcs_directory,
                'planning': self.planning_directory,
                'lidar': self.lidar_directory,
                'camera': self.camera_directory,
                'event_stream': event_paths['canonical'],
                'analysis_runtime': self.runtime_directory,
                'analysis_runtime_event_stream': event_paths['legacy_runtime'],
                'analysis_reports': self.analysis_directory,
            },
            'record_categories': {
                'bus': 'DSM 使用的总线通信记录，包含节点口径与 thesis 逻辑模块口径',
                'function_packets': '按功能字拆分的原始包记录，便于协议级核验与回放',
                'fcs': '飞控遥测 CSV，直接作为 DSM 飞控输入',
                'planning': '规划遥测 CSV，直接作为 DSM 规划输入',
                'lidar': '由规划遥测派生的障碍物/LiDAR CSV，直接作为 DSM LiDAR 输入',
                'camera': '相机目录预留，当前链路默认不落盘',
                'analysis_runtime': '实验运行过程中的事件流与窗口指标，属于分析侧观测数据',
                'analysis_reports': 'DSM、评估、优化等分析产物',
            },
            'platform_type': 'apollo_online',
            'start_ts': int(self.start_time * 1000) if self.start_time else None,
            'end_ts': int(self.end_time * 1000) if self.end_time else None,
            'record_start_ts': int(self.start_time * 1000) if self.start_time else None,
            'record_stop_ts': int(self.end_time * 1000) if self.end_time else None,
            'enabled_ports': self.enabled_ports,
            'enabled_raw_families': [],
            'enabled_record_streams': [
                key for key in ['fcs_telemetry', 'planning_telemetry', 'radar_data', 'bus_traffic']
                if self.data_counters.get(key, 0) > 0
            ],
            'standardization_status': 'waiting',
            'dsm_status': 'waiting',
            'evaluation_status': 'waiting',
            'optimization_status': 'waiting',
            'software_version': SOFTWARE_VERSION,
            'notes': '',
            'operator_note': ''
        }
        payload.update(self.session_meta_patch)
        payload['operator_note'] = payload.get('operator_note', payload.get('notes', ''))
        payload['notes'] = payload.get('notes', payload.get('operator_note', ''))

        runtime_case = self.runtime_context.get('case', {}) if isinstance(self.runtime_context, dict) else {}
        runtime_task = self.runtime_context.get('task', {}) if isinstance(self.runtime_context, dict) else {}
        runtime_scenario = self.runtime_context.get('scenario', {}) if isinstance(self.runtime_context, dict) else {}
        runtime_architecture = self.runtime_context.get('architecture', {}) if isinstance(self.runtime_context, dict) else {}

        if runtime_case:
            payload.setdefault('runtime_case', runtime_case)
        if runtime_task:
            payload.setdefault('runtime_task', runtime_task)
        if runtime_scenario:
            payload.setdefault('scenario_id', runtime_scenario.get('scenario_id'))
            payload.setdefault('scenario_name', runtime_scenario.get('display_name'))
            payload.setdefault('environment_class', runtime_scenario.get('environment_class'))
            payload.setdefault('disturbance_tags', runtime_scenario.get('disturbance_tags'))
            payload.setdefault('heuristic_tags', runtime_scenario.get('heuristic_tags'))
            payload.setdefault('runtime_scenario', runtime_scenario)
        if runtime_architecture:
            payload.setdefault('architecture_id', runtime_architecture.get('architecture_id'))
            payload.setdefault('runtime_architecture', runtime_architecture)
        if self.session_meta_patch.get('architecture_profiles'):
            payload.setdefault('architecture_profiles', self.session_meta_patch.get('architecture_profiles'))

        payload = normalize_session_meta_for_thesis(payload)

        with open(meta_path, 'w', encoding='utf-8') as meta_file:
            json.dump(payload, meta_file, ensure_ascii=False, indent=2)

    def apply_session_meta_patch(self, patch: Optional[dict]) -> None:
        if not patch:
            return
        self.session_meta_patch.update({key: value for key, value in patch.items() if value is not None})
        self.plan_case_id = self.session_meta_patch.get('plan_case_id', self.plan_case_id)

    def set_runtime_context(self, runtime_context: Optional[dict]) -> None:
        self.runtime_context = dict(runtime_context or {})
        case_context = self.runtime_context.get('case', {}) if isinstance(self.runtime_context, dict) else {}
        scenario_context = self.runtime_context.get('scenario', {}) if isinstance(self.runtime_context, dict) else {}
        task_context = self.runtime_context.get('task', {}) if isinstance(self.runtime_context, dict) else {}
        architecture_context = self.runtime_context.get('architecture', {}) if isinstance(self.runtime_context, dict) else {}

        patch = {}
        if case_context.get('case_id'):
            patch['plan_case_id'] = case_context.get('case_id')
        if scenario_context.get('scenario_id'):
            patch['scenario_id'] = scenario_context.get('scenario_id')
            patch['scenario_name'] = scenario_context.get('display_name')
            patch['environment_class'] = scenario_context.get('environment_class')
            patch['disturbance_tags'] = scenario_context.get('disturbance_tags', [])
            patch['heuristic_tags'] = scenario_context.get('heuristic_tags', [])
        if task_context:
            patch['runtime_task'] = task_context
        if architecture_context:
            patch['architecture_id'] = architecture_context.get('architecture_id')
            patch['architecture_name'] = architecture_context.get('display_name')
            patch['runtime_architecture'] = architecture_context
        self.apply_session_meta_patch(patch)

    def _get_raw_stream_handle(self, stream_key: str):
        if stream_key in self.raw_jsonl_handles:
            return self.raw_jsonl_handles[stream_key]

        file_path = os.path.join(self.raw_directory, RAW_STREAM_FILENAMES[stream_key])
        file_handle = open(file_path, 'a', encoding='utf-8')
        self.raw_jsonl_handles[stream_key] = file_handle
        return file_handle

    def _build_raw_metadata_row(self, raw_record: dict) -> list:
        return [
            raw_record.get('arrival_ts', ''),
            raw_record.get('record_id', ''),
            raw_record.get('session_id', ''),
            raw_record.get('case_id', ''),
            raw_record.get('source_module', ''),
            raw_record.get('source_family', ''),
            raw_record.get('func_code', ''),
            raw_record.get('interface_name', ''),
            raw_record.get('port_type', ''),
            raw_record.get('payload_size_bytes', 0),
            raw_record.get('parse_status', ''),
            raw_record.get('seq_id', ''),
            raw_record.get('device_ts', ''),
            raw_record.get('mission_phase', ''),
            '|'.join(raw_record.get('normalized_refs', [])),
            raw_record.get('relative_ts_ms', ''),
            raw_record.get('cycle_id', ''),
            raw_record.get('cycle_anchor_ts', ''),
            raw_record.get('cycle_offset_ms', ''),
            raw_record.get('cycle_packet_index', ''),
        ]

    def _extract_raw_csv_row(self, stream_key: str, msg_type: str, raw_record: dict) -> list:
        metadata_row = self._build_raw_metadata_row(raw_record)
        payload = raw_record.get('payload_json', {}) or {}

        if stream_key == 'flight_control_raw':
            sparse_row = csv_helper.get_data_for_type(msg_type, {
                'timestamp': raw_record.get('arrival_ts', ''),
                'data': payload,
            }).split(',')
            return metadata_row + sparse_row + [json.dumps(payload, ensure_ascii=False, separators=(',', ':'))]

        if stream_key == 'planning_raw':
            position = payload.get('position', {}) or {}
            local_path = payload.get('local_path', payload.get('local_traj', []))
            return metadata_row + [
                payload.get('timestamp', ''),
                payload.get('current_pos_x', position.get('x', '')),
                payload.get('current_pos_y', position.get('y', '')),
                payload.get('current_pos_z', position.get('z', '')),
                payload.get('current_vel', payload.get('velocity', '')),
                payload.get('update_flags', ''),
                payload.get('status', ''),
                payload.get('global_path_count', ''),
                payload.get('local_traj_count', ''),
                payload.get('obstacle_count', ''),
                json.dumps(payload.get('global_path', []), ensure_ascii=False, separators=(',', ':')),
                json.dumps(local_path, ensure_ascii=False, separators=(',', ':')),
                json.dumps(payload.get('obstacles', []), ensure_ascii=False, separators=(',', ':')),
                json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
            ]

        if stream_key == 'radar_raw':
            return metadata_row + [
                msg_type,
                payload.get('obstacle_count', ''),
                payload.get('frame_id', ''),
                payload.get('timestamp_sec', ''),
                payload.get('processing_time_ms', ''),
                payload.get('frame_rate', ''),
                payload.get('input_points', ''),
                payload.get('filtered_points', ''),
                payload.get('is_running', ''),
                payload.get('obstacle_input_connected', payload.get('lidar_connected', '')),
                payload.get('error_code', ''),
                json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
            ]

        return metadata_row + [
            msg_type,
            json.dumps(raw_record.get('payload_json', {}), ensure_ascii=False, separators=(',', ':')),
        ]
    
    def record_flight_perf(self, data: dict):
        """
        记录飞行性能数据
        
        Args:
            data: 飞行状态数据字典
        """
        if not self.is_recording or 'flight_perf' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['flight_perf']
            
            writer.writerow([
                timestamp,
                data.get('latitude', 0),
                data.get('longitude', 0),
                data.get('altitude', 0),
                data.get('target_lat', data.get('latitude', 0)),
                data.get('target_lon', data.get('longitude', 0)),
                data.get('target_alt', data.get('altitude', 0)),
                data.get('roll', 0),
                data.get('pitch', 0),
                data.get('yaw', 0)
            ])
            
            # 定期刷新缓冲区
            self.data_counters['flight_perf'] += 1
            if self.data_counters['flight_perf'] % 100 == 0:
                self.file_handles['flight_perf'].flush()
                
        except Exception as e:
            logger.error(f"记录飞行性能数据失败: {e}")
    
    def record_resources(self, data: dict):
        """
        记录资源数据（CPU、内存）
        
        Args:
            data: 资源数据字典
        """
        if not self.is_recording or 'resources' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['resources']
            
            writer.writerow([
                timestamp,
                data.get('node_id', 0),
                data.get('cpu_load', 0),
                data.get('memory_usage', 0),
                data.get('exec_time_us', 0),
                data.get('task_id', 0)
            ])
            
            self.data_counters['resources'] += 1
            if self.data_counters['resources'] % 100 == 0:
                self.file_handles['resources'].flush()
                
        except Exception as e:
            logger.error(f"记录资源数据失败: {e}")
    
    def record_bus_traffic(self, data: dict):
        """
        记录总线通信数据
        
        Args:
            data: 通信数据字典
        """
        if not self.is_recording:
            return
        
        try:
            self._ensure_view_writer('bus_traffic')
            timestamp = time.time()
            writer = self.csv_writers['bus_traffic']
            
            writer.writerow([
                timestamp,
                data.get('func_code', data.get('msg_id', 0)),
                data.get('msg_size', 0),
                data.get('source_node', ''),
                data.get('target_node', ''),
                data.get('source_module', ''),
                data.get('target_module', ''),
                data.get('frequency', 0),
                data.get('latency_ms', 0),
                data.get('msg_type', ''),
                data.get('port_type', ''),
                data.get('seq_id', ''),
                data.get('func_name', ''),
            ])
            
            self.data_counters['bus_traffic'] += 1
            if self.data_counters['bus_traffic'] % 100 == 0:
                self.file_handles['bus_traffic'].flush()
                
        except Exception as e:
            logger.error(f"记录总线通信数据失败: {e}")

    def _get_function_writer(self, func_code: int, func_name: str):
        if func_code in self.function_csv_writers:
            return self.function_csv_writers[func_code]

        self._ensure_function_directory()
        safe_name = (func_name or f'0x{func_code:02X}').replace('/', '_').replace(' ', '_')
        file_path = os.path.join(self.function_directory, f"func_0x{func_code:02X}_{safe_name}.csv")
        file_handle = open(file_path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        writer.writerow([
            'timestamp_local', 'func_code', 'func_name', 'msg_type', 'port_type', 'msg_size', 'payload_json'
        ])
        self.function_file_handles[func_code] = file_handle
        self.function_csv_writers[func_code] = writer
        return writer

    def _infer_source_family(self, msg_type: str) -> str:
        if msg_type in ['planning_telemetry']:
            return 'planning_raw'
        if msg_type.startswith('camera_') or msg_type.startswith('perception_'):
            return 'perception_raw'
        return 'flight_control_raw'

    def _infer_source_module(self, msg_type: str) -> str:
        if msg_type == 'planning_telemetry':
            return 'planning'
        if msg_type.startswith('camera_') or msg_type.startswith('perception_'):
            return 'perception'
        return 'flight_control'

    def _record_planning_obstacles_as_radar(self, data: dict, packet_meta: Optional[dict] = None):
        if not self.is_recording:
            return

        packet_ts = packet_meta.get('timestamp') if packet_meta else None
        if packet_ts is None:
            packet_ts = int(time.time() * 1000)

        obstacles = data.get('obstacles', []) or []
        radar_payload = {
            'obstacle_count': int(data.get('obstacle_count', len(obstacles) if isinstance(obstacles, list) else 0) or 0),
            'frame_id': data.get('seq_id', ''),
            'timestamp_sec': round(float(packet_ts) / 1000.0, 6),
            'processing_time_ms': data.get('planning_time_ms', ''),
            'frame_rate': '',
            'input_points': '',
            'filtered_points': '',
            'is_running': True,
            'obstacle_input_connected': True,
            'error_code': '',
            'obstacles': obstacles,
            'source': 'planning_telemetry',
        }

        raw_record = {
            'arrival_ts': int(packet_ts),
            'record_id': f"raw_radar_raw_{self.data_counters['raw_records'] + 1:08d}",
            'session_id': self.session_id,
            'source_module': 'radar',
            'source_family': 'radar_raw',
            'func_code': 0x71,
            'interface_name': 'PLANNING_DERIVED_OBSTACLES',
            'port_type': getattr(packet_meta.get('port_type'), 'name', str(packet_meta.get('port_type', 'derived'))) if packet_meta else 'derived',
            'payload_size_bytes': len(json.dumps(radar_payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')),
            'parse_status': 'derived',
            'seq_id': data.get('seq_id', None),
            'device_ts': data.get('timestamp'),
            'case_id': self._build_case_id(),
            'mission_phase': self._build_mission_phase(data.get('Tele_GCS_Mission', data.get('Mission', 0))),
            'normalized_refs': ['thesis_delivery_root'],
            'payload_json': radar_payload,
            'relative_ts_ms': max(0, int(packet_ts) - int(self.start_time * 1000)) if self.start_time else '',
            'cycle_id': '',
            'cycle_anchor_ts': '',
            'cycle_offset_ms': '',
            'cycle_packet_index': '',
        }

        file_handle = self._get_raw_stream_handle('radar_raw')
        file_handle.write(json.dumps(raw_record, ensure_ascii=False) + '\n')
        raw_csv_writer = self.raw_csv_writers.get('radar_raw')
        if raw_csv_writer:
            raw_csv_writer.writerow(self._extract_raw_csv_row('radar_raw', 'planning_obstacles', raw_record))

        self.data_counters['raw_records'] += 1
        self.data_counters['radar_raw'] += 1
        if self.data_counters['radar_raw'] % 20 == 0:
            file_handle.flush()
            raw_csv_handle = self.raw_csv_file_handles.get('radar_raw')
            if raw_csv_handle:
                raw_csv_handle.flush()

    def _start_fcs_cycle(self, arrival_ts: int) -> None:
        self.fcs_cycle_id += 1
        self.fcs_cycle_anchor_ts = arrival_ts
        self.fcs_cycle_packet_index = 0
        self.fcs_cycle_open = True

    def _build_cycle_metadata(self, msg_type: str, source_family: str, arrival_ts: int) -> dict:
        relative_ts_ms = ''
        if self.start_time:
            relative_ts_ms = max(0, int(arrival_ts) - int(self.start_time * 1000))

        if source_family != 'flight_control_raw':
            return {
                'relative_ts_ms': relative_ts_ms,
                'cycle_id': '',
                'cycle_anchor_ts': '',
                'cycle_offset_ms': '',
                'cycle_packet_index': '',
            }

        if msg_type == 'fcs_pwms' or not self.fcs_cycle_open:
            self._start_fcs_cycle(arrival_ts)

        self.fcs_cycle_packet_index += 1
        cycle_anchor_ts = self.fcs_cycle_anchor_ts if self.fcs_cycle_anchor_ts is not None else arrival_ts

        return {
            'relative_ts_ms': relative_ts_ms,
            'cycle_id': self.fcs_cycle_id,
            'cycle_anchor_ts': cycle_anchor_ts,
            'cycle_offset_ms': max(0, int(arrival_ts) - int(cycle_anchor_ts)),
            'cycle_packet_index': self.fcs_cycle_packet_index,
        }

    def _extract_raw_record(self, decoded_data: dict) -> dict:
        msg_type = decoded_data.get('type', 'unknown')
        data = decoded_data.get('data', {}) or {}
        func_code = int(decoded_data.get('func_code', 0) or 0)
        interface_name = FUNC_CODE_NAMES.get(func_code, msg_type)
        port_type = getattr(decoded_data.get('port_type'), 'name', str(decoded_data.get('port_type', 'unknown')))
        payload_size = len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        source_family = self._infer_source_family(msg_type)
        arrival_ts = int(decoded_data.get('timestamp', int(time.time() * 1000)))
        record_id = f"raw_{source_family}_{self.data_counters['raw_records'] + 1:08d}"
        seq_id = data.get('seq_id', '')
        cycle_metadata = self._build_cycle_metadata(msg_type, source_family, arrival_ts)

        return {
            'arrival_ts': arrival_ts,
            'record_id': record_id,
            'session_id': self.session_id,
            'source_module': self._infer_source_module(msg_type),
            'source_family': source_family,
            'func_code': func_code,
            'interface_name': interface_name,
            'port_type': port_type,
            'payload_size_bytes': payload_size,
            'parse_status': 'ok' if msg_type != 'unknown' else 'unknown',
            'seq_id': seq_id if seq_id != '' else None,
            'device_ts': data.get('timestamp'),
            'case_id': self._build_case_id(),
            'mission_phase': self._build_mission_phase(data.get('Tele_GCS_Mission', data.get('Mission', 0))),
            'normalized_refs': [
                ref for ref in [
                    'fcs' if msg_type.startswith('fcs_') else None,
                    'planning' if msg_type == 'planning_telemetry' else None,
                    'analysis_runtime' if msg_type in ['planning_telemetry', 'fcs_states', 'fcs_datagcs', 'fcs_line_aim2ab', 'avoiflag'] else None,
                ] if ref
            ],
            'payload_json': data,
            **cycle_metadata,
        }

    def record_raw_stream(self, decoded_data: dict):
        if not self.is_recording:
            return
        try:
            msg_type = decoded_data.get('type', 'unknown')
            stream_key = self._infer_source_family(msg_type)
            raw_record = self._extract_raw_record(decoded_data)
            file_handle = self._get_raw_stream_handle(stream_key)
            file_handle.write(json.dumps(raw_record, ensure_ascii=False) + '\n')
            raw_csv_writer = self.raw_csv_writers.get(stream_key)
            if raw_csv_writer:
                raw_csv_writer.writerow(self._extract_raw_csv_row(stream_key, msg_type, raw_record))
            self.data_counters['raw_records'] += 1
            self.data_counters[stream_key] += 1
            if self.data_counters[stream_key] % 20 == 0:
                file_handle.flush()
                raw_csv_handle = self.raw_csv_file_handles.get(stream_key)
                if raw_csv_handle:
                    raw_csv_handle.flush()
        except Exception as e:
            logger.error(f"记录原始数据流失败: {e}")

    def record_window_metrics(self, metrics: dict):
        if not self.is_recording:
            return
        try:
            self._ensure_view_writer('window_metrics')
            writer = self.csv_writers['window_metrics']
            mission_id = metrics.get('mission_id', 0)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                self._build_case_id(),
                self._build_mission_phase(mission_id),
                metrics.get('control_jitter_ms', 0.0),
                metrics.get('attitude_peak_phi_deg', 0.0),
                metrics.get('planning_time_ms', 0.0),
                metrics.get('planner_cycle_hz', 0.0),
                metrics.get('tracking_rmse', 0.0),
                metrics.get('avoid_trigger_count', 0),
                metrics.get('mission_switch_count', 0),
                metrics.get('next_waypoint', 0),
                metrics.get('radar_fps', 0.0),
                metrics.get('perception_latency_ms', 0.0),
                metrics.get('obstacle_count', 0.0),
                metrics.get('esc_power_pct_avg', metrics.get('esc_power_pct', 0.0)),
            ])
            self.data_counters['window_metrics'] += 1
            if self.data_counters['window_metrics'] % 5 == 0:
                self.file_handles['window_metrics'].flush()
        except Exception as e:
            logger.error(f"记录窗口指标失败: {e}")

    def record_event(self, event: dict):
        if not self.is_recording:
            return
        try:
            self._ensure_view_writer('event_stream')
            event_row = [
                event.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]),
                event.get('session_id', self.session_id),
                event.get('case_id', self._build_case_id()),
                event.get('event_type', ''),
                event.get('event_source', 'apollo_backend'),
                event.get('event_level', 'info'),
                event.get('event_value', ''),
                event.get('event_detail', event.get('event_text', '')),
                event.get('mission_phase', self._build_mission_phase(event.get('mission_id', 0))),
                event.get('scenario_id', self.session_meta_patch.get('scenario_id', 'scenario_default')),
                event.get('architecture_id', self.session_meta_patch.get('architecture_id', '')),
                event.get('effective_task', (self.runtime_context.get('task', {}) if isinstance(self.runtime_context, dict) else {}).get('task_name', '')),
                '|'.join(event.get('scenario_evidence_tags', (self.runtime_context.get('scenario', {}) if isinstance(self.runtime_context, dict) else {}).get('heuristic_tags', []))),
            ]
            self.csv_writers['event_stream'].writerow(event_row)
            if 'event_stream_legacy_runtime' in self.csv_writers:
                self.csv_writers['event_stream_legacy_runtime'].writerow(event_row)
            self.data_counters['experiment_events'] += 1
            self.file_handles['event_stream'].flush()
            if 'event_stream_legacy_runtime' in self.file_handles:
                self.file_handles['event_stream_legacy_runtime'].flush()
        except Exception as e:
            logger.error(f"记录实验事件失败: {e}")

    def _write_data_quality_report(self):
        report_path = os.path.join(self.session_directory, 'data_quality_report.json')
        try:
            report = self.get_session_info()
            report['generated_at'] = datetime.now().isoformat()
            generated_files = []
            for root, _, files in os.walk(self.session_directory):
                rel_root = os.path.relpath(root, self.session_directory)
                if rel_root == '.':
                    generated_files.extend(files)
                else:
                    generated_files.extend([os.path.join(rel_root, file_name) for file_name in files])
            report['generated_files'] = sorted(set(generated_files) | {'data_quality_report.json'})
            with open(report_path, 'w', encoding='utf-8') as report_file:
                json.dump(report, report_file, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"写入数据质量报告失败: {e}")

    def record_function_packet(self, func_code: int, func_name: str, msg_type: str, port_type: str, msg_size: int, data: dict):
        if not self.is_recording or not func_code:
            return

        try:
            writer = self._get_function_writer(func_code, func_name)
            writer.writerow([
                time.time(),
                f"0x{func_code:02X}",
                func_name,
                msg_type,
                port_type,
                msg_size,
                json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            ])

            stats = self.func_code_stats[func_code]
            stats['func_name'] = func_name
            stats['packet_count'] += 1
            stats['total_bytes'] += int(msg_size or 0)
            stats['last_msg_type'] = msg_type

            if stats['packet_count'] % 50 == 0:
                self.function_file_handles[func_code].flush()
        except Exception as e:
            logger.error(f"记录功能字数据失败 func=0x{func_code:02X}: {e}")
    
    def _init_futaba_file(self):
        """初始化Futaba遥控数据文件"""
        filepath = os.path.join(self.session_directory, "futaba_remote.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'remote_roll', 'remote_pitch', 'remote_yaw',
            'remote_throttle', 'remote_switch', 'remote_fail'
        ])
        
        self.file_handles['futaba_remote'] = file_handle
        self.csv_writers['futaba_remote'] = writer
    
    def _init_gncbus_file(self):
        """初始化GN&C总线数据文件"""
        filepath = os.path.join(self.session_directory, "gncbus.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'cmd_phi', 'cmd_hdot', 'cmd_r',
            'cmd_psi', 'cmd_vx', 'cmd_vy', 'cmd_height'
        ])
        
        self.file_handles['gncbus'] = file_handle
        self.csv_writers['gncbus'] = writer
    
    def _init_esc_file(self):
        """初始化ESC电机参数数据文件"""
        filepath = os.path.join(self.session_directory, "esc_parameters.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        header = ['timestamp']
        for i in range(1, 7):
            header.extend([
                f'm{i}_error_count',
                f'm{i}_rpm',
                f'm{i}_power_pct'
            ])
        writer.writerow(header)
        
        self.file_handles['esc'] = file_handle
        self.csv_writers['esc'] = writer
    
    def _init_datafutaba_file(self):
        """初始化Futaba遥控输入数据文件（DATAFUTABA）"""
        filepath = os.path.join(self.session_directory, "futaba_input.csv")
        file_handle = open(filepath, 'w', newline='', encoding='utf-8')
        writer = csv.writer(file_handle)
        
        # 写入表头
        writer.writerow([
            'timestamp', 'roll', 'pitch', 'yaw', 'throttle',
            'switch', 'fail_flag'
        ])
        
        self.file_handles['futaba_input'] = file_handle
        self.csv_writers['futaba_input'] = writer
    
    def record_esc(self, data: dict):
        """
        记录ESC电机参数数据
        
        Args:
            data: ESC数据字典
        """
        if not self.is_recording or 'esc' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['esc']
            
            row = [timestamp]
            for i in range(1, 7):
                row.extend([
                    data.get(f'esc{i}_error_count', 0),
                    data.get(f'esc{i}_rpm', 0),
                    data.get(f'esc{i}_power_rating_pct', 0)
                ])
            
            writer.writerow(row)
            self.data_counters['esc'] = self.data_counters.get('esc', 0) + 1
            
            if self.data_counters['esc'] % 100 == 0:
                self.file_handles['esc'].flush()
                
        except Exception as e:
            logger.error(f"记录ESC数据失败: {e}")
    
    def record_datafutaba(self, data: dict):
        """
        记录Futaba遥控输入数据（DATAFUTABA）
        
        Args:
            data: Futaba数据字典
        """
        if not self.is_recording or 'futaba_input' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['futaba_input']
            
            writer.writerow([
                timestamp,
                data.get('Tele_ftb_Roll', 0),
                data.get('Tele_ftb_Pitch', 0),
                data.get('Tele_ftb_Yaw', 0),
                data.get('Tele_ftb_Col', 0),
                data.get('Tele_ftb_Switch', 0),
                data.get('Tele_ftb_com_Ftb_fail', 0)
            ])
            
            self.data_counters['futaba_input'] = self.data_counters.get('futaba_input', 0) + 1
            
            if self.data_counters['futaba_input'] % 100 == 0:
                self.file_handles['futaba_input'].flush()
                
        except Exception as e:
            logger.error(f"记录Futaba输入数据失败: {e}")
    
    def record_futaba(self, data: dict):
        """
        记录Futaba遥控数据
        
        Args:
            data: Futaba遥控数据字典
        """
        if not self.is_recording or 'futaba_remote' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['futaba_remote']
            
            writer.writerow([
                timestamp,
                data.get('Tele_ftb_Roll', 0),
                data.get('Tele_ftb_Pitch', 0),
                data.get('Tele_ftb_Yaw', 0),
                data.get('Tele_ftb_Col', 0),
                data.get('Tele_ftb_Switch', 0),
                data.get('Tele_ftb_com_Ftb_fail', 0)
            ])
            
            self.data_counters['futaba_remote'] = self.data_counters.get('futaba_remote', 0) + 1
            if self.data_counters['futaba_remote'] % 100 == 0:
                self.file_handles['futaba_remote'].flush()
                
        except Exception as e:
            logger.error(f"记录Futaba遥控数据失败: {e}")
    
    def record_gncbus(self, data: dict):
        """
        记录GN&C总线数据（GNC指令值）
        
        Args:
            data: GN&C总线数据字典
        """
        if not self.is_recording or 'gncbus' not in self.csv_writers:
            return
        
        try:
            timestamp = time.time()
            writer = self.csv_writers['gncbus']
            
            writer.writerow([
                timestamp,
                data.get('GNCBus_CmdValue_phi_cmd', 0),
                data.get('GNCBus_CmdValue_Hdot_cmd', 0),
                data.get('GNCBus_CmdValue_R_cmd', 0),
                data.get('GNCBus_CmdValue_psi_cmd', 0),
                data.get('GNCBus_CmdValue_Vx_cmd', 0),
                data.get('GNCBus_CmdValue_Vy_cmd', 0),
                data.get('GNCBus_CmdValue_height_cmd', 0)
            ])
            
            self.data_counters['gncbus'] = self.data_counters.get('gncbus', 0) + 1
            if self.data_counters['gncbus'] % 100 == 0:
                self.file_handles['gncbus'].flush()
                
        except Exception as e:
            logger.error(f"记录GN&C总线数据失败: {e}")
    
    def record_fcs_telemetry(self, msg_type: str, data: dict, packet_meta: Optional[dict] = None):
        """维护飞控周期缓存，并导出 onboard 兼容快照。"""
        if not self.is_recording:
            return
        try:
            if packet_meta:
                packet_ts = packet_meta.get('timestamp')
                if packet_ts is not None:
                    self.fcs_last_timestamp_ms = str(packet_ts)
                    self.fcs_last_receive_time = f"{float(packet_ts) / 1000.0:.6f}"

            if msg_type == 'fcs_root' and isinstance(data, dict):
                self.fcs_root_snapshot.update({
                    'ParamAil_YaccLMT': data.get('YaccLMT', data.get('ParamAil_YaccLMT', self.fcs_root_snapshot['ParamAil_YaccLMT'])),
                    'ParamEle_XaccLMT': data.get('XaccLMT', data.get('ParamEle_XaccLMT', self.fcs_root_snapshot['ParamEle_XaccLMT'])),
                    'ParamGuide_Hground': data.get('Hground', data.get('ParamGuide_Hground', self.fcs_root_snapshot['ParamGuide_Hground'])),
                    'ParamGuide_AutoTakeoffHcmd': data.get('AutoTakeoffHcmd', data.get('ParamGuide_AutoTakeoffHcmd', self.fcs_root_snapshot['ParamGuide_AutoTakeoffHcmd'])),
                    'ftb_intterrupt_plan': data.get('ftb_intterrupt_plan', self.fcs_root_snapshot['ftb_intterrupt_plan']),
                })

            if msg_type == 'fcs_pwms':
                self._flush_fcs_snapshot_if_pending()

            wrapped_data = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                'data': data
            }
            csv_helper.update_cache_and_get_line(msg_type, wrapped_data, self.fcs_cache)
            self.fcs_cycle_seen.add(msg_type)
            self.fcs_snapshot_pending = True

            if msg_type in FCS_VIEW_SNAPSHOT_TRIGGER_TYPES:
                self._flush_fcs_snapshot_if_pending()
        except Exception as e:
            logger.error(f"记录FCS遥测失败: {e}")

    def record_planning_telemetry(self, data: dict, packet_meta: Optional[dict] = None):
        """记录规划与 LiDAR DSM 输入。"""
        if not self.is_recording:
            return
        try:
            packet_ts = packet_meta.get('timestamp') if packet_meta else None
            self._write_planning_telemetry_row(data, packet_ts)
            self._write_lidar_telemetry_row(data, packet_ts)
        except Exception as e:
            logger.error(f"记录规划数据失败: {e}")

    def record_radar_data(self, msg_type: str, data: dict):
        """雷达原始数据已在 raw 中逐包落盘，这里不再额外生成磁盘 view。"""
        return

    def record_decoded_packet(self, decoded_data: dict):
        """
        统一的UDP数据包记录入口
        """
        if not self.is_recording:
            return

        if decoded_data.get('skip_recording'):
            return
        
        msg_type = decoded_data.get('type', 'unknown')
        data = decoded_data.get('data', {})
        # --------------------------------------------------------
        # [NEW] 全局总线流量记录 (适用于所有接收到的数据包)
        # --------------------------------------------------------
        try:
            current_time = time.time()
            bus_info = self._get_bus_info(decoded_data)
            msg_id = bus_info['msg_id']
            source_module, target_module = BUS_LOGICAL_ROUTE_MAP.get(msg_type, ('LF_Communication', 'LF_Communication'))
            
            # 计算频率
            freq = 0.0
            if msg_id > 0:
                last_time = self.last_msg_times[msg_id]
                if last_time > 0:
                    delta = current_time - last_time
                    if delta > 0.001: 
                        freq = 1.0 / delta
                        # 简单平滑处理
                        if self.current_frequencies[msg_id] == 0:
                             self.current_frequencies[msg_id] = freq
                        else:
                             self.current_frequencies[msg_id] = 0.9 * self.current_frequencies[msg_id] + 0.1 * freq
                self.last_msg_times[msg_id] = current_time
            
            # 估算Payload大小
            payload_size = len(str(data))
            
            bus_traffic_entry = {
                'func_code': msg_id,
                'func_name': FUNC_CODE_NAMES.get(msg_id, f'0x{msg_id:02X}' if msg_id else 'unknown'),
                'msg_type': msg_type,
                'port_type': getattr(decoded_data.get('port_type'), 'name', str(decoded_data.get('port_type', 'unknown'))),
                'msg_size': payload_size,
                'source_node': bus_info['source'],
                'target_node': bus_info['target'],
                'source_module': source_module,
                'target_module': target_module,
                'frequency': round(self.current_frequencies[msg_id], 1),
                'latency_ms': 5.0,
                'seq_id': data.get('seq_id', '')
            }
            self.record_bus_traffic(bus_traffic_entry)
            self.record_function_packet(
                msg_id,
                bus_traffic_entry['func_name'],
                msg_type,
                bus_traffic_entry['port_type'],
                payload_size,
                data
            )
            
        except Exception as e:
            # 避免总线记录错误影响主数据记录
            pass

        # 1. 飞控遥测数据 (FCS Telemetry)
        # 包括: pwms, states, datactrl, gncbus, avoiflag, futaba, lines
        if msg_type in ['fcs_pwms', 'fcs_states', 'fcs_datactrl', 'fcs_gncbus', 
                   'avoiflag', 'fcs_datafutaba', 'fcs_param',
                   'fcs_line_aim2ab', 'fcs_line_ab', 'fcs_datagcs', 'fcs_root']:
            self.record_fcs_telemetry(msg_type, data, decoded_data)
        
        # 2. 规划数据 (Planning)
        elif msg_type == 'planning_telemetry':
            self.record_planning_telemetry(data, decoded_data)
            
        # 统一输出已经覆盖协议主链路，不再额外生成旧版重复文件。

    def get_session_info(self) -> dict:
        """获取录制会话信息"""
        func_stats = []
        total_bytes = 0
        for func_code, stats in sorted(self.func_code_stats.items(), key=lambda item: item[0]):
            total_bytes += stats['total_bytes']
            func_stats.append({
                'func_code': f"0x{func_code:02X}",
                'func_code_int': func_code,
                'func_name': stats['func_name'],
                'packet_count': stats['packet_count'],
                'total_bytes': stats['total_bytes'],
                'avg_bytes': round(stats['total_bytes'] / stats['packet_count'], 2) if stats['packet_count'] else 0,
                'last_msg_type': stats['last_msg_type']
            })

        return {
            'session_id': self.session_id,
            'case_id': self._build_case_id(),
            'plan_case_id': self.plan_case_id,
            'is_recording': self.is_recording,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': (self.end_time - self.start_time) if self.start_time and self.end_time else 0,
            'data_directory': self.session_directory,
            'data_counters': dict(self.data_counters),
            'total_bytes': total_bytes,
            'func_stats': func_stats,
            'scenario_id': self.session_meta_patch.get('scenario_id'),
            'scenario_name': self.session_meta_patch.get('scenario_name'),
            'architecture_id': self.session_meta_patch.get('architecture_id'),
            'figure_run_id': self.session_meta_patch.get('figure_run_id'),
            'figure_batch_id': self.session_meta_patch.get('figure_batch_id'),
            'figure_batch_group': self.session_meta_patch.get('figure_batch_group'),
            'figure_ledger_range': self.session_meta_patch.get('figure_ledger_range'),
            'experiment_type': self.session_meta_patch.get('experiment_type'),
            'chapter_target': self.session_meta_patch.get('chapter_target'),
            'law_validation_scope': self.session_meta_patch.get('law_validation_scope'),
            'analysis_run_id': self.session_meta_patch.get('analysis_run_id'),
            'runtime_context': self.runtime_context,
        }

    def __del__(self):
        """析构函数，确保文件被正确关闭"""
        if self.is_recording:
            self.stop_recording()