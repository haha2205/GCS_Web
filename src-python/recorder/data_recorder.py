import csv
import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import recorder.csv_helper_full as csv_helper

logger = logging.getLogger(__name__)
_OPEN = open

PLANNING_TRAJECTORY_DT_SECONDS = 0.01

RECORDS_OUTPUT_DIRNAME = 'records'
BUS_OUTPUT_DIRNAME = 'bus'
FCS_OUTPUT_DIRNAME = 'fcs'
PLANNING_OUTPUT_DIRNAME = 'planning'
LIDAR_OUTPUT_DIRNAME = 'lidar'
CAMERA_OUTPUT_DIRNAME = 'camera'
FUNCTION_PACKETS_OUTPUT_DIRNAME = 'function_packets'
COMMUNICATION_OUTPUT_DIRNAME = 'communication'

FCS_ONBOARD_EXTRA_HEADERS = [
    'receive_time',
]

PLANNING_TELEMETRY_HEADERS = [
    'timestamp_local', 'seq_id', 'timestamp_remote',
    'current_pos_x', 'current_pos_y', 'current_pos_z', 'current_vel',
    'update_flags', 'global_path_updated', 'local_traj_updated', 'obstacles_updated',
    'status',
    'global_path_count', 'global_path_json',
    'local_traj_count', 'local_traj_json',
    'obstacle_count', 'obstacles_json',
]

LIDAR_TELEMETRY_HEADERS = [
    'timestamp_local', 'seq_id', 'timestamp_remote', 'obstacle_index', 'obstacle_count',
    'cx', 'cy', 'cz', 'sx', 'sy', 'sz', 'vx', 'vy', 'vz'
]

BUS_TRAFFIC_HEADERS = [
    'timestamp', 'msg_id', 'msg_size', 'source_node', 'target_node',
    'source_module', 'target_module', 'frequency', 'latency_ms',
    'msg_type', 'port_type', 'seq_id', 'func_name'
]

FUNCTION_PACKET_HEADERS = [
    'timestamp_local', 'func_code', 'func_name', 'msg_type', 'port_type', 'msg_size', 'payload_json'
]

FCS_VIEW_PRIMER_TYPES = (
    'fcs_pwms',
    'fcs_states',
    'fcs_datactrl',
    'fcs_gncbus',
    'avoiflag',
    'fcs_datafutaba',
    'fcs_param',
    'fcs_esc',
    'fcs_line_aim2ab',
    'fcs_line_ab',
    'fcs_datagcs',
)

FCS_VIEW_SNAPSHOT_TRIGGER_TYPES = {
    'fcs_param',
}

FCS_VIEW_MEANINGFUL_TYPES = {
    'fcs_states',
    'fcs_datactrl',
    'fcs_gncbus',
    'avoiflag',
    'fcs_datafutaba',
    'fcs_param',
    'fcs_esc',
    'fcs_line_aim2ab',
    'fcs_line_ab',
    'fcs_datagcs',
}

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
    0x4A: 'NCLINK_RECEIVE_EXTY_FCS_ESC',
    0x4B: 'NCLINK_RECEIVE_EXTY_FCS_ROOT',
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
    'fcs_esc': ('LF_Motor_Driver', 'LF_SoC_Adapter'),
    'planning_telemetry': ('LF_Path_Planning', 'LF_Flight_Control'),
}


def _rename_fcs_onboard_header(header_name: str) -> str:
    if header_name == 'timestamp':
        return 'timestamp_local'
    if header_name.startswith('pwm') and header_name[3:].isdigit():
        return f"pwms_{int(header_name[3:]) - 1}"
    return header_name


def _get_fcs_onboard_headers() -> List[str]:
    headers: List[str] = []
    for header_name in csv_helper.get_full_header().split(','):
        headers.append(_rename_fcs_onboard_header(header_name))
    headers.extend(FCS_ONBOARD_EXTRA_HEADERS)
    return headers


class RawDataRecorder:
    NODE_UNKNOWN = 0
    NODE_MCU = 1
    NODE_GCS = 2
    NODE_SOC = 3

    def __init__(
        self,
        session_id: str,
        base_directory: str = 'data',
        case_id_override: Optional[str] = None,
        plan_case_id: Optional[str] = None,
        session_meta_patch: Optional[dict] = None,
    ):
        self.session_id = session_id
        self.base_directory = base_directory
        self.session_meta_patch = dict(session_meta_patch or {})
        self.plan_case_id = plan_case_id or self.session_meta_patch.get('plan_case_id')
        self.session_directory = os.path.join(base_directory, session_id)
        self.records_directory = os.path.join(self.session_directory, RECORDS_OUTPUT_DIRNAME)
        self.bus_directory = os.path.join(self.records_directory, BUS_OUTPUT_DIRNAME)
        self.fcs_directory = os.path.join(self.records_directory, FCS_OUTPUT_DIRNAME)
        self.planning_directory = os.path.join(self.records_directory, PLANNING_OUTPUT_DIRNAME)
        self.lidar_directory = os.path.join(self.records_directory, LIDAR_OUTPUT_DIRNAME)
        self.camera_directory = os.path.join(self.records_directory, CAMERA_OUTPUT_DIRNAME)
        self.function_directory = os.path.join(self.records_directory, FUNCTION_PACKETS_OUTPUT_DIRNAME)
        self.communication_directory = os.path.join(self.records_directory, COMMUNICATION_OUTPUT_DIRNAME)

        self.enabled_ports: List[int] = []
        self.is_recording = False
        self.case_id = case_id_override or self._allocate_case_id()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        self.file_handles: Dict[str, object] = {}
        self.csv_writers: Dict[str, object] = {}
        self.function_file_handles: Dict[int, object] = {}
        self.function_csv_writers: Dict[int, object] = {}
        self.backend_log_handle: Optional[object] = None

        self.data_counters = defaultdict(int)
        self.func_code_stats = defaultdict(lambda: {
            'func_name': 'unknown',
            'packet_count': 0,
            'total_bytes': 0,
            'last_msg_type': 'unknown',
        })
        self.last_msg_times = defaultdict(float)
        self.current_frequencies = defaultdict(float)

        self.fcs_cache: List[Any] = []
        self.fcs_cycle_seen = set()
        self.fcs_snapshot_pending = False
        self.fcs_last_receive_time = ''
        self.fcs_last_timestamp_ms = ''
        for directory in [
            self.session_directory,
            self.records_directory,
            self.bus_directory,
            self.fcs_directory,
            self.planning_directory,
            self.lidar_directory,
            self.camera_directory,
            self.function_directory,
            self.communication_directory,
        ]:
            os.makedirs(directory, exist_ok=True)

        logger.info('数据录制器初始化完成: %s', self.session_directory)

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.start_time = time.time()
        self._init_fcs_cycle_cache()
        self._init_backend_communication_log_file()
        self._init_fcs_telemetry_file()
        self._init_planning_telemetry_file()
        self._init_lidar_telemetry_file()
        self._init_bus_traffic_file()
        self._write_session_meta()

    def stop_recording(self):
        if not self.is_recording:
            return
        self._flush_fcs_snapshot_if_pending()
        self.is_recording = False
        self.end_time = time.time()

        for handle in self.file_handles.values():
            try:
                handle.close()
            except Exception as exc:
                logger.error('关闭文件失败: %s', exc)

        for handle in self.function_file_handles.values():
            try:
                handle.close()
            except Exception as exc:
                logger.error('关闭功能字文件失败: %s', exc)

        if self.backend_log_handle is not None:
            try:
                self.backend_log_handle.close()
            except Exception as exc:
                logger.error('关闭通信日志文件失败: %s', exc)
            self.backend_log_handle = None

        self.file_handles.clear()
        self.csv_writers.clear()
        self.function_file_handles.clear()
        self.function_csv_writers.clear()
        self._write_session_meta()
        self._write_data_quality_report()

    def _init_fcs_cycle_cache(self):
        header = csv_helper.get_full_header()
        self.fcs_cache = [''] * len(header.split(','))
        for msg_type in FCS_VIEW_PRIMER_TYPES:
            csv_helper.update_cache_and_get_line(msg_type, {'timestamp': '', 'data': {}}, self.fcs_cache)
        if self.fcs_cache:
            self.fcs_cache[0] = ''
        self.fcs_cycle_seen.clear()
        self.fcs_snapshot_pending = False

    def _init_fcs_telemetry_file(self):
        path = os.path.join(self.fcs_directory, 'fcs_telemetry.csv')
        handle = _OPEN(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(handle)
        writer.writerow(_get_fcs_onboard_headers())
        self.file_handles['fcs_telemetry'] = handle
        self.csv_writers['fcs_telemetry'] = writer

    def _init_backend_communication_log_file(self):
        path = os.path.join(self.communication_directory, 'backend_communication.log')
        self.backend_log_handle = _OPEN(path, 'w', encoding='utf-8')

    def append_backend_communication_log(
        self,
        logger_name: str,
        level_name: str,
        message: str,
        created_ts: Optional[float] = None,
    ) -> None:
        if not self.is_recording or self.backend_log_handle is None:
            return
        log_dt = datetime.fromtimestamp(created_ts if created_ts is not None else time.time())
        self.backend_log_handle.write(
            f'{log_dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]} - {logger_name} - {level_name} - {message}\n'
        )
        self.data_counters['backend_communication_log'] += 1
        if self.data_counters['backend_communication_log'] % 20 == 0:
            self.backend_log_handle.flush()

    def _init_planning_telemetry_file(self):
        path = os.path.join(self.planning_directory, 'planning_telemetry.csv')
        handle = _OPEN(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(handle)
        writer.writerow(PLANNING_TELEMETRY_HEADERS)
        self.file_handles['planning_telemetry'] = handle
        self.csv_writers['planning_telemetry'] = writer

    def _init_lidar_telemetry_file(self):
        path = os.path.join(self.lidar_directory, 'radar_data.csv')
        handle = _OPEN(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(handle)
        writer.writerow(LIDAR_TELEMETRY_HEADERS)
        self.file_handles['radar_data'] = handle
        self.csv_writers['radar_data'] = writer

    def _init_bus_traffic_file(self):
        path = os.path.join(self.bus_directory, 'bus_traffic.csv')
        handle = _OPEN(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(handle)
        writer.writerow(BUS_TRAFFIC_HEADERS)
        self.file_handles['bus_traffic'] = handle
        self.csv_writers['bus_traffic'] = writer

    def _extract_session_date(self) -> str:
        match = re.search(r'(\d{8})', self.session_id)
        if match:
            return match.group(1)
        return datetime.now().strftime('%Y%m%d')

    def _allocate_case_id(self) -> str:
        session_date = self._extract_session_date()
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
                    with _OPEN(meta_path, 'r', encoding='utf-8') as meta_file:
                        case_id = json.load(meta_file).get('case_id', '')
                    match = re.match(r'^case(\d{3,4})(?:_\d{8})?$', str(case_id))
                    if match:
                        max_case_index = max(max_case_index, int(match.group(1)))
                except Exception:
                    continue
        return f"case{max(max_case_index, session_count) + 1:03d}_{session_date}"

    def _build_case_id(self) -> str:
        return self.case_id

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
            center = obstacle.get('center', {}) if isinstance(obstacle.get('center'), dict) else {}
            size = obstacle.get('size', {}) if isinstance(obstacle.get('size'), dict) else {}
            velocity = obstacle.get('velocity', {}) if isinstance(obstacle.get('velocity'), dict) else {}
            normalized.append({
                'cx': float(obstacle.get('cx', center.get('x', 0.0))),
                'cy': float(obstacle.get('cy', center.get('y', 0.0))),
                'cz': float(obstacle.get('cz', center.get('z', 0.0))),
                'sx': float(obstacle.get('sx', size.get('x', 0.0))),
                'sy': float(obstacle.get('sy', size.get('y', 0.0))),
                'sz': float(obstacle.get('sz', size.get('z', 0.0))),
                'vx': float(obstacle.get('vx', velocity.get('x', 0.0))),
                'vy': float(obstacle.get('vy', velocity.get('y', 0.0))),
                'vz': float(obstacle.get('vz', velocity.get('z', 0.0))),
            })
        return normalized

    def _get_planning_local_path(self, data: dict) -> List[dict]:
        return self._normalize_path_points(data.get('local_path') or data.get('local_traj') or [])

    def _get_planning_position(self, data: dict) -> Dict[str, float]:
        position = data.get('position', {}) if isinstance(data.get('position'), dict) else {}
        return {
            'x': float(data.get('current_pos_x', position.get('x', 0.0))),
            'y': float(data.get('current_pos_y', position.get('y', 0.0))),
            'z': float(data.get('current_pos_z', position.get('z', 0.0))),
        }

    def _get_planning_velocity(self, data: dict) -> float:
        return float(data.get('current_vel', data.get('velocity', 0.0)) or 0.0)

    def _get_update_flag(self, data: dict, bit_index: int) -> int:
        try:
            update_flags = int(data.get('update_flags', 0) or 0)
        except (TypeError, ValueError):
            update_flags = 0
        return 1 if (update_flags & (1 << bit_index)) else 0

    def _default_scenario(self) -> str:
        return str(self.session_meta_patch.get('scenario_id', self.plan_case_id or self.case_id or ''))

    def _default_cmd_idx(self) -> Any:
        return self.session_meta_patch.get('cmd_idx', '')

    def _default_cmd_mission(self) -> Any:
        return self.session_meta_patch.get('cmd_mission', '')

    def _as_epoch_seconds(self, arrival_ts_ms: Optional[int]) -> float:
        if arrival_ts_ms is None:
            return time.time()
        return float(arrival_ts_ms) / 1000.0

    def _has_meaningful_fcs_cycle(self) -> bool:
        return any(msg_type in FCS_VIEW_MEANINGFUL_TYPES for msg_type in self.fcs_cycle_seen)

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

        row = [f'{relative_seconds:.6f}']
        for header_name in source_headers[1:]:
            row.append(cache_map.get(header_name, ''))
        row.append(self.fcs_last_receive_time)
        writer.writerow(row)
        self.data_counters['fcs_telemetry'] += 1
        if self.data_counters['fcs_telemetry'] % 50 == 0:
            self.file_handles['fcs_telemetry'].flush()

    def _flush_fcs_snapshot_if_pending(self):
        if not self.fcs_snapshot_pending:
            return
        if self._has_meaningful_fcs_cycle():
            self._write_fcs_telemetry_snapshot()
        self.fcs_cycle_seen.clear()
        self.fcs_snapshot_pending = False

    def _write_planning_telemetry_row(self, data: dict, arrival_ts_ms: Optional[int]):
        writer = self.csv_writers.get('planning_telemetry')
        if writer is None:
            return
        local_path = self._get_planning_local_path(data)
        global_path = self._normalize_path_points(data.get('global_path', []))
        obstacles = self._normalize_obstacles(data.get('obstacles', []))
        position = self._get_planning_position(data)
        writer.writerow([
            f'{self._as_epoch_seconds(arrival_ts_ms):.6f}' if arrival_ts_ms is not None else '',
            data.get('seq_id', ''),
            data.get('timestamp', ''),
            position['x'],
            position['y'],
            position['z'],
            self._get_planning_velocity(data),
            data.get('update_flags', ''),
            self._get_update_flag(data, 0),
            self._get_update_flag(data, 1),
            self._get_update_flag(data, 2),
            data.get('status', ''),
            data.get('global_path_count', len(global_path)),
            json.dumps(global_path, ensure_ascii=False, separators=(',', ':')),
            data.get('local_traj_count', len(local_path)),
            json.dumps(local_path, ensure_ascii=False, separators=(',', ':')),
            data.get('obstacle_count', len(obstacles)),
            json.dumps(obstacles, ensure_ascii=False, separators=(',', ':')),
        ])
        self.data_counters['planning_telemetry'] += 1
        if self.data_counters['planning_telemetry'] % 20 == 0:
            self.file_handles['planning_telemetry'].flush()

    def _write_lidar_telemetry_row(self, data: dict, arrival_ts_ms: Optional[int]):
        writer = self.csv_writers.get('radar_data')
        if writer is None:
            return
        obstacles = self._normalize_obstacles(data.get('obstacles', []))
        obs_count = int(data.get('obstacle_count', len(obstacles)) or 0)
        for obstacle_index, obstacle in enumerate(obstacles):
            writer.writerow([
                f'{self._as_epoch_seconds(arrival_ts_ms):.6f}' if arrival_ts_ms is not None else '',
                data.get('seq_id', ''),
                data.get('timestamp', ''),
                obstacle_index,
                obs_count,
                obstacle['cx'],
                obstacle['cy'],
                obstacle['cz'],
                obstacle['sx'],
                obstacle['sy'],
                obstacle['sz'],
                obstacle['vx'],
                obstacle['vy'],
                obstacle['vz'],
            ])
            self.data_counters['radar_data'] += 1
        if self.data_counters['radar_data'] % 50 == 0 and self.data_counters['radar_data'] > 0:
            self.file_handles['radar_data'].flush()

    def _get_bus_info(self, decoded_data: dict) -> dict:
        msg_type = decoded_data.get('type', 'unknown')
        port_type = decoded_data.get('port_type')
        func_code = int(decoded_data.get('func_code', 0) or 0)
        info = {
            'source': self.NODE_UNKNOWN,
            'target': self.NODE_GCS,
            'msg_id': func_code,
        }
        if msg_type.startswith('fcs_') or msg_type == 'avoiflag':
            info['source'] = self.NODE_MCU
        elif msg_type == 'planning_telemetry':
            info['source'] = self.NODE_SOC
            info['msg_id'] = info['msg_id'] or 0x71

        if port_type is not None:
            port_name = getattr(port_type, 'name', str(port_type))
            if 'PLANNING' in port_name or 'LIDAR' in port_name:
                info['source'] = self.NODE_SOC
            elif 'TELEMETRY' in port_name or 'RECEIVE' in port_name:
                info['source'] = self.NODE_MCU
        return info

    def record_bus_traffic(self, entry: dict):
        if not self.is_recording:
            return
        writer = self.csv_writers.get('bus_traffic')
        if writer is None:
            return
        writer.writerow([
            entry.get('timestamp', time.time()),
            entry.get('func_code', 0),
            entry.get('msg_size', 0),
            entry.get('source_node', ''),
            entry.get('target_node', ''),
            entry.get('source_module', ''),
            entry.get('target_module', ''),
            entry.get('frequency', 0),
            entry.get('latency_ms', 0),
            entry.get('msg_type', ''),
            entry.get('port_type', ''),
            entry.get('seq_id', ''),
            entry.get('func_name', ''),
        ])
        self.data_counters['bus_traffic'] += 1
        if self.data_counters['bus_traffic'] % 100 == 0:
            self.file_handles['bus_traffic'].flush()

    def _get_function_writer(self, func_code: int, func_name: str):
        if func_code in self.function_csv_writers:
            return self.function_csv_writers[func_code]
        safe_name = (func_name or f'0x{func_code:02X}').replace('/', '_').replace(' ', '_')
        path = os.path.join(self.function_directory, f'func_0x{func_code:02X}_{safe_name}.csv')
        handle = _OPEN(path, 'w', newline='', encoding='utf-8')
        writer = csv.writer(handle)
        writer.writerow(FUNCTION_PACKET_HEADERS)
        self.function_file_handles[func_code] = handle
        self.function_csv_writers[func_code] = writer
        return writer

    def record_function_packet(self, func_code: int, func_name: str, msg_type: str, port_type: str, msg_size: int, data: dict, arrival_ts_ms: Optional[int]):
        if not self.is_recording or not func_code:
            return
        writer = self._get_function_writer(func_code, func_name)
        writer.writerow([
            f'{self._as_epoch_seconds(arrival_ts_ms):.6f}',
            f'0x{func_code:02X}',
            func_name,
            msg_type,
            port_type,
            msg_size,
            json.dumps(data, ensure_ascii=False, separators=(',', ':')),
        ])
        self.data_counters['function_packets'] += 1
        stats = self.func_code_stats[func_code]
        stats['func_name'] = func_name
        stats['packet_count'] += 1
        stats['total_bytes'] += int(msg_size or 0)
        stats['last_msg_type'] = msg_type
        if stats['packet_count'] % 50 == 0:
            self.function_file_handles[func_code].flush()

    def record_fcs_telemetry(self, msg_type: str, data: dict, packet_meta: Optional[dict] = None):
        if not self.is_recording:
            return
        packet_ts = packet_meta.get('timestamp') if packet_meta else None
        if packet_ts is not None:
            self.fcs_last_timestamp_ms = str(packet_ts)
            self.fcs_last_receive_time = f'{float(packet_ts) / 1000.0:.6f}'

        if msg_type == 'fcs_pwms':
            self._flush_fcs_snapshot_if_pending()

        csv_helper.update_cache_and_get_line(msg_type, {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'data': data,
        }, self.fcs_cache)
        self.fcs_cycle_seen.add(msg_type)
        self.fcs_snapshot_pending = True

        if msg_type in FCS_VIEW_SNAPSHOT_TRIGGER_TYPES:
            self._flush_fcs_snapshot_if_pending()

    def record_planning_telemetry(self, data: dict, packet_meta: Optional[dict] = None):
        if not self.is_recording:
            return
        packet_ts = packet_meta.get('timestamp') if packet_meta else None
        self._write_planning_telemetry_row(data, packet_ts)
        self._write_lidar_telemetry_row(data, packet_ts)

    def record_decoded_packet(self, decoded_data: dict):
        if not self.is_recording or decoded_data.get('skip_recording'):
            return

        msg_type = decoded_data.get('type', 'unknown')
        data = decoded_data.get('data', {}) or {}
        func_code = int(decoded_data.get('func_code', 0) or 0)
        port_type = getattr(decoded_data.get('port_type'), 'name', str(decoded_data.get('port_type', 'unknown')))
        arrival_ts_ms = int(decoded_data.get('timestamp', int(time.time() * 1000)))
        payload_size = len(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))

        current_time = self._as_epoch_seconds(arrival_ts_ms)
        bus_info = self._get_bus_info(decoded_data)
        msg_id = bus_info['msg_id']
        source_module, target_module = BUS_LOGICAL_ROUTE_MAP.get(msg_type, ('LF_Communication', 'LF_Communication'))

        frequency = 0.0
        if msg_id > 0:
            last_time = self.last_msg_times[msg_id]
            if last_time > 0:
                delta = current_time - last_time
                if delta > 0.001:
                    instant_frequency = 1.0 / delta
                    if self.current_frequencies[msg_id] == 0:
                        self.current_frequencies[msg_id] = instant_frequency
                    else:
                        self.current_frequencies[msg_id] = (0.9 * self.current_frequencies[msg_id]) + (0.1 * instant_frequency)
            self.last_msg_times[msg_id] = current_time
            frequency = round(self.current_frequencies[msg_id], 1)

        func_name = FUNC_CODE_NAMES.get(msg_id, f'0x{msg_id:02X}' if msg_id else 'unknown')
        self.record_bus_traffic({
            'timestamp': current_time,
            'func_code': msg_id,
            'func_name': func_name,
            'msg_type': msg_type,
            'port_type': port_type,
            'msg_size': payload_size,
            'source_node': bus_info['source'],
            'target_node': bus_info['target'],
            'source_module': source_module,
            'target_module': target_module,
            'frequency': frequency,
            'latency_ms': 5.0,
            'seq_id': data.get('seq_id', ''),
        })
        self.record_function_packet(msg_id, func_name, msg_type, port_type, payload_size, data, arrival_ts_ms)

        if msg_type in {
            'fcs_pwms', 'fcs_states', 'fcs_datactrl', 'fcs_gncbus', 'avoiflag',
            'fcs_datafutaba', 'fcs_param', 'fcs_esc', 'fcs_line_aim2ab',
            'fcs_line_ab', 'fcs_datagcs',
        }:
            self.record_fcs_telemetry(msg_type, data, decoded_data)
        elif msg_type == 'planning_telemetry':
            self.record_planning_telemetry(data, decoded_data)

    def _write_session_meta(self):
        meta_path = os.path.join(self.session_directory, 'session_meta.json')
        payload = {
            'session_id': self.session_id,
            'case_id': self._build_case_id(),
            'plan_case_id': self.plan_case_id,
            'session_directory': self.session_directory,
            'start_ts': int(self.start_time * 1000) if self.start_time else None,
            'end_ts': int(self.end_time * 1000) if self.end_time else None,
            'enabled_ports': self.enabled_ports,
            'record_layout_version': 'records-only-v1',
            'record_layout': {
                'records_root': self.records_directory,
                'bus': self.bus_directory,
                'function_packets': self.function_directory,
                'fcs': self.fcs_directory,
                'planning': self.planning_directory,
                'lidar': self.lidar_directory,
                'communication': self.communication_directory,
                'camera': self.camera_directory,
            },
            'record_categories': {
                'bus': '总线通信记录',
                'function_packets': '按功能字拆分的原始包记录',
                'fcs': '飞控遥测 CSV',
                'planning': '规划遥测 CSV',
                'lidar': '从规划遥测提取出的雷达障碍物 CSV',
                'communication': '后端上下行通信日志',
                'camera': '目录保留，当前不落盘',
            },
            'enabled_record_streams': [
                key for key in ['fcs_telemetry', 'planning_telemetry', 'radar_data', 'bus_traffic', 'function_packets', 'backend_communication_log']
                if self.data_counters.get(key, 0) > 0
            ],
            'data_counters': dict(self.data_counters),
        }
        payload.update(self.session_meta_patch)
        with _OPEN(meta_path, 'w', encoding='utf-8') as meta_file:
            json.dump(payload, meta_file, ensure_ascii=False, indent=2)

    def _write_data_quality_report(self):
        report_path = os.path.join(self.session_directory, 'data_quality_report.json')
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
        with _OPEN(report_path, 'w', encoding='utf-8') as report_file:
            json.dump(report, report_file, ensure_ascii=False, indent=2)

    def get_session_info(self) -> dict:
        func_stats = []
        total_bytes = 0
        for func_code, stats in sorted(self.func_code_stats.items(), key=lambda item: item[0]):
            total_bytes += stats['total_bytes']
            func_stats.append({
                'func_code': f'0x{func_code:02X}',
                'func_code_int': func_code,
                'func_name': stats['func_name'],
                'packet_count': stats['packet_count'],
                'total_bytes': stats['total_bytes'],
                'avg_bytes': round(stats['total_bytes'] / stats['packet_count'], 2) if stats['packet_count'] else 0,
                'last_msg_type': stats['last_msg_type'],
            })
        duration = 0
        if self.start_time:
            duration = (self.end_time or time.time()) - self.start_time
        return {
            'session_id': self.session_id,
            'case_id': self._build_case_id(),
            'plan_case_id': self.plan_case_id,
            'is_recording': self.is_recording,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': duration,
            'data_directory': self.session_directory,
            'data_counters': dict(self.data_counters),
            'total_bytes': total_bytes,
            'func_stats': func_stats,
        }

    def __del__(self):
        try:
            if getattr(self, 'is_recording', False):
                self.stop_recording()
        except Exception:
            pass
