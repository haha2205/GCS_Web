from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from recorder import normalize_session_meta_for_thesis
from recorder.csv_helper_full import get_full_header
from recorder.data_recorder import _rename_fcs_onboard_header


def _build_thesis_fcs_onboard_headers() -> List[str]:
    headers: List[str] = []
    for header_name in get_full_header().split(','):
        if header_name.startswith('esc'):
            continue
        renamed = _rename_fcs_onboard_header(header_name)
        headers.append(renamed)
        if header_name == 'ParamAil_F_KaAy':
            headers.append('ParamAil_YaccLMT')
        if header_name == 'ParamEle_F_KeAx':
            headers.append('ParamEle_XaccLMT')
    headers.extend([
        'ParamGuide_Hground',
        'ParamGuide_AutoTakeoffHcmd',
        'ftb_intterrupt_plan',
        'TimeStamp',
        'receive_time',
    ])
    return headers


@dataclass
class SessionStandardizationResult:
    session_dir: str
    success: bool
    standard_files: Dict[str, str]
    file_status: Dict[str, str]
    file_details: Dict[str, Dict[str, Any]]
    generated_files: List[str]
    missing_inputs: List[str]
    notes: List[str]
    required_files: List[str]
    optional_files: List[str]
    configured_input_weights: Dict[str, float]
    effective_input_weights: Dict[str, float]


class SessionStandardizer:
    REQUIRED_FILES = ['fcs_telemetry', 'planning_telemetry', 'radar_data', 'bus_traffic']
    OPTIONAL_FILES = ['camera_data']
    REPORT_PATH = Path('analysis') / 'standardization_report.json'

    STANDARD_FILES = {
        'fcs_telemetry': 'fcs_telemetry.csv',
        'planning_telemetry': 'planning_telemetry.csv',
        'radar_data': 'radar_data.csv',
        'bus_traffic': 'bus_traffic.csv',
        'camera_data': 'camera_data.csv',
    }

    SOURCE_FILES = {
        'fcs_telemetry': [('records', 'fcs', 'fcs_telemetry.csv'), ('fcs_telemetry.csv'), ('analysis', 'standardized', 'fcs_telemetry.csv')],
        'planning_telemetry': [('records', 'planning', 'planning_telemetry.csv'), ('planning_telemetry.csv'), ('analysis', 'standardized', 'planning_telemetry.csv')],
        'radar_data': [('records', 'lidar', 'radar_data.csv'), ('radar_data.csv'), ('analysis', 'standardized', 'radar_data.csv')],
        'bus_traffic': [('records', 'bus', 'bus_traffic.csv'), ('bus_traffic.csv'), ('analysis', 'standardized', 'bus_traffic.csv')],
        'camera_data': [('records', 'camera', 'camera_data.csv'), ('camera_data.csv'), ('analysis', 'standardized', 'camera_data.csv')],
    }

    CONFIGURED_INPUT_WEIGHTS = {
        'fcs_telemetry': 1.0,
        'planning_telemetry': 1.0,
        'radar_data': 1.0,
        'bus_traffic': 1.0,
        'camera_data': 0.0,
    }

    FCS_TRAILING_HEADERS = [
        'timestamp',
        'pwm1', 'pwm2', 'pwm3', 'pwm4', 'pwm5', 'pwm6',
        'esc1_power_rating_pct', 'esc2_power_rating_pct', 'esc3_power_rating_pct',
        'esc4_power_rating_pct', 'esc5_power_rating_pct', 'esc6_power_rating_pct',
        'esc1_rpm', 'esc1_error_count',
        'esc2_rpm', 'esc2_error_count',
        'esc3_rpm', 'esc3_error_count',
        'esc4_rpm', 'esc4_error_count',
        'esc5_rpm', 'esc5_error_count',
        'esc6_rpm', 'esc6_error_count',
        'proc_time_ms', 'scenario', 'cmd_idx', 'cmd_mission', 'gncbus_cmd_phi',
    ]

    STANDARD_HEADERS = {
        'fcs_telemetry': _build_thesis_fcs_onboard_headers() + FCS_TRAILING_HEADERS,
        'planning_telemetry': [
            'timestamp_local', 'seq_id', 'timestamp_remote', 'scenario', 'cpu_usage', 'waypoint_idx',
            'planning_mode', 'global_path_count', 'local_traj_count', 'obstacle_count', 'status', 'cmd_idx', 'cmd_mission',
        ],
        'radar_data': [
            'timestamp_local', 'scenario', 'cmd_idx', 'cmd_mission', 'msg_type', 'frame_id', 'timestamp_sec',
            'proc_time_ms', 'fps', 'points_in', 'points_out', 'is_running', 'lidar_connected',
            'error_code', 'obstacles_json', 'performance_json', 'obs_count', 'obs_density',
        ],
        'camera_data': [
            'timestamp_local', 'scenario', 'cmd_idx', 'cmd_mission', 'frame_id', 'timestamp_sec',
            'proc_time_ms', 'fps', 'is_running', 'camera_connected', 'error_code', 'objects_json', 'performance_json',
            'obj_count', 'obs_density',
        ],
        'bus_traffic': [
            'timestamp', 'msg_id', 'msg_size', 'source_node', 'target_node', 'frequency', 'latency_ms',
        ],
    }

    def __init__(self, session_dir: str | Path):
        self.session_dir = Path(session_dir)
        self.output_dir = self.session_dir / 'records'
        self.report_path = self.session_dir / self.REPORT_PATH
        self.session_meta = self._load_session_meta()

    def export(self) -> SessionStandardizationResult:
        standard_files: Dict[str, str] = {}
        file_status: Dict[str, str] = {}
        file_details: Dict[str, Dict[str, Any]] = {}
        generated_files: List[str] = []
        missing_inputs: List[str] = []
        notes: List[str] = []
        effective_input_weights = dict(self.CONFIGURED_INPUT_WEIGHTS)

        self._cleanup_redundant_standardized_outputs()

        for key in self.STANDARD_FILES:
            source_path = self._resolve_source_path(key)
            rows = self._read_csv_rows(source_path)
            artifact = self._inspect_existing_input(key, source_path, rows)

            standard_files[key] = str(source_path) if source_path else ''
            file_status[key] = artifact['status']
            file_details[key] = {
                'status': artifact['status'],
                'output_path': self._relative_path(source_path) if source_path else '',
                'source_kind': artifact.get('source_kind', ''),
                'source_path': artifact.get('source_path', ''),
                'rows_written': artifact.get('rows_written', 0),
                'placeholder': bool(artifact.get('placeholder', False)),
                'notes': list(artifact.get('notes', [])),
            }
            missing_inputs.extend(artifact.get('missing_inputs', []))
            notes.extend(f"{self.STANDARD_FILES[key]}: {note}" for note in artifact.get('notes', []))
            if artifact['status'] != 'ready':
                effective_input_weights[key] = 0.0

        required_ready = all(file_status.get(key) == 'ready' for key in self.REQUIRED_FILES)
        any_real_input_ready = any(file_status.get(key) == 'ready' for key in self.STANDARD_FILES)
        any_failed = any(status == 'failed' for status in file_status.values())
        optional_empty = [key for key in self.OPTIONAL_FILES if file_status.get(key) != 'ready']
        if optional_empty:
            notes.append('optional modalities downgraded with zero weight: ' + ', '.join(sorted(optional_empty)))

        generated_files.append(self._relative_path(self.report_path))
        result = SessionStandardizationResult(
            session_dir=str(self.session_dir),
            success=any_real_input_ready and not any_failed and all(status in {'ready', 'empty', 'failed'} for status in file_status.values()),
            standard_files=standard_files,
            file_status=file_status,
            file_details=file_details,
            generated_files=sorted(dict.fromkeys(generated_files)),
            missing_inputs=sorted(dict.fromkeys(missing_inputs)),
            notes=notes,
            required_files=list(self.REQUIRED_FILES),
            optional_files=list(self.OPTIONAL_FILES),
            configured_input_weights=dict(self.CONFIGURED_INPUT_WEIGHTS),
            effective_input_weights=effective_input_weights,
        )

        self._write_standardization_report(result)
        self._update_session_meta(result)
        return result

    def _inspect_existing_input(self, key: str, source_path: Optional[Path], rows: List[dict[str, Any]]) -> dict[str, Any]:
        if key == 'camera_data' and source_path is None:
            return {
                'status': 'empty',
                'rows_written': 0,
                'placeholder': False,
                'source_kind': 'recording_disabled',
                'source_path': '',
                'missing_inputs': [],
                'notes': ['camera recording disabled in current recorder layout'],
            }

        if source_path is None:
            return {
                'status': 'empty',
                'rows_written': 0,
                'placeholder': False,
                'source_kind': 'missing_records_input',
                'source_path': '',
                'missing_inputs': [self._relative_expected_path(key)],
                'notes': ['expected records input file is missing'],
            }

        if not rows:
            return {
                'status': 'empty',
                'rows_written': 0,
                'placeholder': False,
                'source_kind': 'records_input_empty',
                'source_path': str(source_path),
                'missing_inputs': [],
                'notes': ['records input exists but contains no data rows'],
            }

        return {
            'status': 'ready',
            'rows_written': len(rows),
            'placeholder': False,
            'source_kind': 'records_input',
            'source_path': str(source_path),
            'missing_inputs': [],
            'notes': [],
        }

    def _build_fcs_telemetry(self, output_path: Path) -> dict[str, Any]:
        source_path = self._resolve_source_path('fcs_telemetry')
        rows = self._read_csv_rows(source_path)
        if not rows:
            self._write_csv(output_path, self.STANDARD_HEADERS['fcs_telemetry'], [])
            return self._empty_artifact(source_path, 'raw_missing_or_empty')

        output_rows: List[dict[str, Any]] = []
        onboard_headers = _build_thesis_fcs_onboard_headers()
        for row in rows:
            output_row = {
                header: self._resolve_fcs_onboard_value(row, header)
                for header in onboard_headers
            }
            output_row.update({
                'timestamp': self._first_defined(row, ['timestamp', 'device_ts', 'arrival_ts']),
                'pwm1': row.get('pwm1', ''),
                'pwm2': row.get('pwm2', ''),
                'pwm3': row.get('pwm3', ''),
                'pwm4': row.get('pwm4', ''),
                'pwm5': row.get('pwm5', ''),
                'pwm6': row.get('pwm6', ''),
                'esc1_power_rating_pct': row.get('esc1_power_rating_pct', ''),
                'esc2_power_rating_pct': row.get('esc2_power_rating_pct', ''),
                'esc3_power_rating_pct': row.get('esc3_power_rating_pct', ''),
                'esc4_power_rating_pct': row.get('esc4_power_rating_pct', ''),
                'esc5_power_rating_pct': row.get('esc5_power_rating_pct', ''),
                'esc6_power_rating_pct': row.get('esc6_power_rating_pct', ''),
                'esc1_rpm': row.get('esc1_rpm', ''),
                'esc1_error_count': row.get('esc1_error_count', ''),
                'esc2_rpm': row.get('esc2_rpm', ''),
                'esc2_error_count': row.get('esc2_error_count', ''),
                'esc3_rpm': row.get('esc3_rpm', ''),
                'esc3_error_count': row.get('esc3_error_count', ''),
                'esc4_rpm': row.get('esc4_rpm', ''),
                'esc4_error_count': row.get('esc4_error_count', ''),
                'esc5_rpm': row.get('esc5_rpm', ''),
                'esc5_error_count': row.get('esc5_error_count', ''),
                'esc6_rpm': row.get('esc6_rpm', ''),
                'esc6_error_count': row.get('esc6_error_count', ''),
                'proc_time_ms': row.get('proc_time_ms', ''),
                'scenario': self._resolve_scenario(row),
                'cmd_idx': self._resolve_cmd_idx(row),
                'cmd_mission': self._resolve_cmd_mission(row),
                'gncbus_cmd_phi': self._first_defined(row, ['gncbus_cmd_phi', 'GNCBus_CmdValue_phi_cmd']),
            })
            output_rows.append(output_row)

        self._write_csv(output_path, self.STANDARD_HEADERS['fcs_telemetry'], output_rows)
        return self._ready_artifact(source_path, 'flight_control_raw', len(output_rows))

    def _build_planning_telemetry(self, output_path: Path) -> dict[str, Any]:
        source_path = self._resolve_source_path('planning_telemetry')
        rows = self._read_csv_rows(source_path)
        if not rows:
            self._write_csv(output_path, self.STANDARD_HEADERS['planning_telemetry'], [])
            return self._empty_artifact(source_path, 'raw_missing_or_empty')

        output_rows: List[dict[str, Any]] = []
        for row in rows:
            obstacle_count = self._first_defined(row, ['obstacle_count', 'obs_count'], default='0')
            output_rows.append({
                'timestamp_local': self._first_defined(row, ['timestamp_local', 'timestamp_remote', 'device_ts', 'arrival_ts', 'timestamp']),
                'seq_id': row.get('seq_id', ''),
                'timestamp_remote': self._first_defined(row, ['timestamp_remote', 'timestamp_local', 'device_ts', 'arrival_ts']),
                'scenario': self._resolve_scenario(row),
                'cpu_usage': row.get('cpu_usage', ''),
                'waypoint_idx': self._first_defined(row, ['waypoint_idx', 'current_waypoint_idx']),
                'planning_mode': self._first_defined(row, ['planning_mode', 'update_flags', 'status']),
                'global_path_count': row.get('global_path_count', ''),
                'local_traj_count': row.get('local_traj_count', ''),
                'obstacle_count': obstacle_count,
                'status': row.get('status', ''),
                'cmd_idx': self._resolve_cmd_idx(row),
                'cmd_mission': self._resolve_cmd_mission(row),
            })

        self._write_csv(output_path, self.STANDARD_HEADERS['planning_telemetry'], output_rows)
        return self._ready_artifact(source_path, 'planning_raw', len(output_rows))

    def _build_radar_data(self, output_path: Path) -> dict[str, Any]:
        source_path = self._resolve_source_path('radar_data')
        rows = self._read_csv_rows(source_path)
        if rows:
            output_rows = [self._map_radar_row(row) for row in rows]
            self._write_csv(output_path, self.STANDARD_HEADERS['radar_data'], output_rows)
            return self._ready_artifact(source_path, 'radar_raw', len(output_rows))

        planning_source = self._resolve_source_path('planning_telemetry')
        planning_rows = self._read_csv_rows(planning_source)
        if planning_rows:
            output_rows = [self._map_planning_row_to_radar(row, index) for index, row in enumerate(planning_rows, start=1)]
            self._write_csv(output_path, self.STANDARD_HEADERS['radar_data'], output_rows)
            return {
                'status': 'ready',
                'rows_written': len(output_rows),
                'placeholder': False,
                'source_kind': 'planning_derived_obstacle_flow',
                'source_path': str(planning_source) if planning_source else '',
                'missing_inputs': [str(source_path)] if source_path else [],
                'notes': ['native radar stream unavailable; used planning-derived obstacle flow'],
            }

        placeholder_row = self._build_placeholder_radar_row()
        self._write_csv(output_path, self.STANDARD_HEADERS['radar_data'], [placeholder_row])
        return {
            'status': 'empty',
            'rows_written': 1,
            'placeholder': True,
            'source_kind': 'explicit_placeholder',
            'source_path': '',
            'missing_inputs': [path for path in [str(source_path) if source_path else '', str(planning_source) if planning_source else ''] if path],
            'notes': ['no radar source available; emitted explicit placeholder row with stage-1 semantics'],
        }

    def _build_camera_data(self, output_path: Path) -> dict[str, Any]:
        source_path = self._resolve_source_path('camera_data')
        rows = self._read_csv_rows(source_path)
        meaningful_rows = [self._map_camera_row(row) for row in rows if self._camera_row_has_signal(row)]
        if meaningful_rows:
            self._write_csv(output_path, self.STANDARD_HEADERS['camera_data'], meaningful_rows)
            return {
                'status': 'ready',
                'rows_written': len(meaningful_rows),
                'placeholder': False,
                'source_kind': 'perception_raw',
                'source_path': str(source_path) if source_path else '',
                'missing_inputs': [],
                'notes': [],
            }

        placeholder_row = self._build_placeholder_camera_row()
        self._write_csv(output_path, self.STANDARD_HEADERS['camera_data'], [placeholder_row])
        return {
            'status': 'empty',
            'rows_written': 1,
            'placeholder': True,
            'source_kind': 'explicit_zero_weight_placeholder',
            'source_path': str(source_path) if source_path else '',
            'missing_inputs': [str(source_path)] if source_path else [],
            'notes': ['perception source unavailable or schema-sparse; emitted explicit placeholder row'],
        }

    def _build_bus_traffic(self, output_path: Path) -> dict[str, Any]:
        source_path = self._resolve_source_path('bus_traffic')
        rows = self._read_csv_rows(source_path)
        if not rows:
            self._write_csv(output_path, self.STANDARD_HEADERS['bus_traffic'], [])
            return self._empty_artifact(source_path, 'raw_missing_or_empty')

        output_rows: List[dict[str, Any]] = []
        for row in rows:
            output_rows.append({
                'timestamp': self._first_defined(row, ['timestamp', 'arrival_ts', 'device_ts']),
                'msg_id': self._normalize_numeric_string(self._first_defined(row, ['msg_id', 'func_code'])),
                'msg_size': self._normalize_numeric_string(self._first_defined(row, ['msg_size', 'payload_size_bytes'])),
                'frequency': self._normalize_numeric_string(self._first_defined(row, ['frequency', 'frequency_hz'], default='0')),
                'latency_ms': self._normalize_numeric_string(self._first_defined(row, ['latency_ms'], default='0')),
                'source_node': self._first_defined(row, ['source_node', 'source_module', 'func_name']),
                'target_node': self._first_defined(row, ['target_node', 'interface_name', 'port_type']),
                'func_code': self._normalize_numeric_string(self._first_defined(row, ['func_code', 'msg_id'])),
            })

        self._write_csv(output_path, self.STANDARD_HEADERS['bus_traffic'], output_rows)
        return self._ready_artifact(source_path, 'bus_traffic', len(output_rows))

    def _map_radar_row(self, row: dict[str, Any]) -> dict[str, Any]:
        obs_count = self._first_defined(row, ['obs_count', 'obstacle_count'], default='0')
        points_in = self._normalize_numeric_string(self._first_defined(row, ['points_in', 'input_points'], default='0'))
        points_out = self._normalize_numeric_string(self._first_defined(row, ['points_out', 'filtered_points'], default='0'))
        performance = {
            'stage1_source': 'radar_raw',
            'input_points': points_in,
            'filtered_points': points_out,
            'proc_time_ms': self._first_defined(row, ['proc_time_ms', 'processing_time_ms'], default='0'),
            'fps': self._first_defined(row, ['fps', 'frame_rate'], default='0'),
        }
        return {
            'timestamp_local': self._first_defined(row, ['timestamp_local', 'timestamp_sec', 'device_ts', 'arrival_ts', 'timestamp']),
            'scenario': self._resolve_scenario(row),
            'cmd_idx': self._resolve_cmd_idx(row),
            'cmd_mission': self._resolve_cmd_mission(row),
            'msg_type': row.get('msg_type', ''),
            'frame_id': row.get('frame_id', ''),
            'timestamp_sec': self._first_defined(row, ['timestamp_sec', 'timestamp_local']),
            'proc_time_ms': self._first_defined(row, ['proc_time_ms', 'processing_time_ms'], default='0'),
            'fps': self._first_defined(row, ['fps', 'frame_rate'], default='0'),
            'points_in': points_in,
            'points_out': points_out,
            'is_running': self._normalize_booleanish(row.get('is_running', '')),
            'lidar_connected': self._normalize_booleanish(self._first_defined(row, ['lidar_connected', 'obstacle_input_connected', 'is_running'], default='0')),
            'error_code': row.get('error_code', ''),
            'obstacles_json': self._first_defined(row, ['obstacles_json', 'payload_json']),
            'performance_json': json.dumps(performance, ensure_ascii=False),
            'obs_count': obs_count,
            'obs_density': self._derive_density(obs_count, points_in),
        }

    def _map_planning_row_to_radar(self, row: dict[str, Any], index: int) -> dict[str, Any]:
        obs_count = self._first_defined(row, ['obs_count', 'obstacle_count'], default='0')
        performance = {
            'stage1_source': 'planning_raw',
            'derived_from': 'planning obstacle stream',
            'placeholder_metrics': True,
        }
        return {
            'timestamp_local': self._first_defined(row, ['timestamp_local', 'timestamp_remote', 'device_ts', 'arrival_ts', 'timestamp']),
            'scenario': self._resolve_scenario(row),
            'cmd_idx': self._resolve_cmd_idx(row),
            'cmd_mission': self._resolve_cmd_mission(row),
            'msg_type': self._first_defined(row, ['msg_type'], default='planning_obstacle_flow'),
            'frame_id': row.get('frame_id', str(index)),
            'timestamp_sec': self._first_defined(row, ['timestamp_remote', 'timestamp_local', 'device_ts', 'arrival_ts']),
            'proc_time_ms': self._first_defined(row, ['proc_time_ms', 'processing_time_ms'], default='0'),
            'fps': self._first_defined(row, ['fps', 'frame_rate'], default='0'),
            'points_in': '',
            'points_out': '',
            'is_running': '1',
            'lidar_connected': '1',
            'error_code': '',
            'obstacles_json': row.get('obstacles_json', ''),
            'performance_json': json.dumps(performance, ensure_ascii=False),
            'obs_count': obs_count,
            'obs_density': self._derive_density(obs_count, ''),
        }

    def _map_camera_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = self._parse_json_object(row.get('payload_json'))
        obj_count = self._first_defined_from_payload(payload, ['obj_count', 'object_count', 'obstacle_count'], default='0')
        proc_time_ms = self._first_defined_from_payload(payload, ['proc_time_ms', 'processing_time_ms'], default='0')
        fps = self._first_defined_from_payload(payload, ['fps', 'frame_rate'], default='0')
        timestamp_sec = self._first_defined_from_payload(payload, ['timestamp_sec', 'timestamp'], default='')
        frame_id = self._first_defined_from_payload(payload, ['frame_id'], default='')
        is_running = self._first_defined_from_payload(payload, ['is_running'], default='')
        error_code = self._first_defined_from_payload(payload, ['error_code'], default='')
        objects_json = self._first_defined_from_payload(payload, ['objects_json', 'detections', 'payload_json'], default=row.get('payload_json', ''))
        performance = {
            'stage1_source': 'perception_raw',
            'payload_sparse': not bool(payload),
        }
        return {
            'timestamp_local': self._first_defined(row, ['timestamp_local', 'device_ts', 'arrival_ts', 'timestamp']),
            'scenario': self._resolve_scenario(row),
            'cmd_idx': self._resolve_cmd_idx(row),
            'cmd_mission': self._resolve_cmd_mission(row),
            'frame_id': frame_id,
            'timestamp_sec': timestamp_sec,
            'proc_time_ms': proc_time_ms,
            'fps': fps,
            'is_running': self._normalize_booleanish(is_running),
            'camera_connected': self._normalize_booleanish(self._first_defined_from_payload(payload, ['camera_connected', 'is_running'], default='1')),
            'error_code': error_code,
            'objects_json': self._stringify_json_value(objects_json),
            'performance_json': json.dumps(performance, ensure_ascii=False),
            'obj_count': obj_count,
            'obs_density': self._first_defined_from_payload(payload, ['obs_density', 'object_density'], default=self._derive_density(obj_count, '')),
        }

    def _build_placeholder_radar_row(self) -> dict[str, Any]:
        performance = {
            'placeholder': True,
            'stage1_source': 'none',
            'explanation': 'radar stream unavailable for this session',
        }
        return {
            'timestamp_local': '',
            'scenario': self._default_scenario(),
            'cmd_idx': self._default_cmd_idx(),
            'cmd_mission': self._default_cmd_mission(),
            'msg_type': 'placeholder',
            'frame_id': '',
            'timestamp_sec': '',
            'proc_time_ms': '0',
            'fps': '0',
            'points_in': '0',
            'points_out': '0',
            'is_running': '0',
            'lidar_connected': '0',
            'error_code': 'PLACEHOLDER',
            'obstacles_json': '[]',
            'performance_json': json.dumps(performance, ensure_ascii=False),
            'obs_count': '0',
            'obs_density': '0',
        }

    def _build_placeholder_camera_row(self) -> dict[str, Any]:
        performance = {
            'placeholder': True,
            'zero_weight_semantics': True,
            'stage1_source': 'none',
            'explanation': 'camera/perception stream unavailable for this session',
        }
        return {
            'timestamp_local': '',
            'scenario': self._default_scenario(),
            'cmd_idx': self._default_cmd_idx(),
            'cmd_mission': self._default_cmd_mission(),
            'frame_id': '',
            'timestamp_sec': '',
            'proc_time_ms': '0',
            'fps': '0',
            'is_running': '0',
            'camera_connected': '0',
            'error_code': 'PLACEHOLDER',
            'objects_json': '[]',
            'performance_json': json.dumps(performance, ensure_ascii=False),
            'obj_count': '0',
            'obs_density': '0',
        }

    def _write_csv(self, output_path: Path, headers: List[str], rows: List[dict[str, Any]]) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8', newline='') as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({header: row.get(header, '') for header in headers})

    def _cleanup_redundant_standardized_outputs(self) -> None:
        stale_directories = [
            self.session_dir / 'standard',
            self.session_dir / 'analysis' / 'standardized',
        ]
        for stale_dir in stale_directories:
            for file_name in self.STANDARD_FILES.values():
                stale_path = stale_dir / file_name
                if stale_path.exists():
                    stale_path.unlink()
            if stale_dir.exists() and not any(stale_dir.iterdir()):
                stale_dir.rmdir()

        dsm_inputs_dir = self.session_dir / 'analysis' / 'dsm_inputs'
        if dsm_inputs_dir.exists():
            for stale_path in dsm_inputs_dir.iterdir():
                if stale_path.is_file():
                    stale_path.unlink()
            if not any(dsm_inputs_dir.iterdir()):
                dsm_inputs_dir.rmdir()

    def _write_standardization_report(self, result: SessionStandardizationResult) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        with self.report_path.open('w', encoding='utf-8') as report_file:
            json.dump(asdict(result), report_file, ensure_ascii=False, indent=2)

    def _update_session_meta(self, result: SessionStandardizationResult) -> None:
        meta_path = self.session_dir / 'session_meta.json'
        payload: Dict[str, Any] = {}
        if meta_path.exists():
            with meta_path.open('r', encoding='utf-8') as meta_file:
                payload = json.load(meta_file)

        record_layout = payload.setdefault('record_layout', {})
        record_layout['dsm_record_inputs_root'] = str(self.output_dir)
        record_layout.pop('analysis_standardized', None)
        record_layout.pop('standard', None)
        record_layout.pop('thesis_delivery_root', None)

        payload['standardization'] = {
            'success': result.success,
            'file_status': result.file_status,
            'file_details': result.file_details,
            'generated_files': result.generated_files,
            'missing_inputs': result.missing_inputs,
            'notes': result.notes,
            'output_directory': str(self.output_dir),
            'report_path': str(self.report_path),
            'required_files': result.required_files,
            'optional_files': result.optional_files,
            'configured_input_weights': result.configured_input_weights,
            'effective_input_weights': result.effective_input_weights,
        }

        payload['session_directory'] = str(self.session_dir)
        payload = normalize_session_meta_for_thesis(payload)

        with meta_path.open('w', encoding='utf-8') as meta_file:
            json.dump(payload, meta_file, ensure_ascii=False, indent=2)

    def _resolve_source_path(self, key: str) -> Optional[Path]:
        candidates = [self.session_dir.joinpath(*parts) for parts in self.SOURCE_FILES[key]]
        return next((candidate for candidate in candidates if candidate.exists()), None)

    def _relative_expected_path(self, key: str) -> str:
        expected_parts = self.SOURCE_FILES[key][0]
        return str(Path(*expected_parts)).replace('\\', '/')

    def _read_csv_rows(self, file_path: Optional[Path]) -> List[dict[str, Any]]:
        if file_path is None or not file_path.exists():
            return []
        with file_path.open('r', encoding='utf-8', newline='') as csv_file:
            reader = csv.DictReader(csv_file)
            return [row for row in reader if row]

    def _load_session_meta(self) -> dict[str, Any]:
        meta_path = self.session_dir / 'session_meta.json'
        if not meta_path.exists():
            return {}
        with meta_path.open('r', encoding='utf-8') as meta_file:
            return json.load(meta_file)

    def _default_scenario(self) -> str:
        planned_case = self.session_meta.get('planned_case') or {}
        return (
            self.session_meta.get('scenario_id')
            or planned_case.get('scenario_id')
            or self.session_meta.get('case_id')
            or self.session_dir.name
        )

    def _default_cmd_idx(self) -> Any:
        planned_case = self.session_meta.get('planned_case') or {}
        return planned_case.get('cmd_idx', self.session_meta.get('cmd_idx', ''))

    def _default_cmd_mission(self) -> Any:
        planned_case = self.session_meta.get('planned_case') or {}
        return planned_case.get('mission_id', self.session_meta.get('cmd_mission', ''))

    def _resolve_fcs_onboard_value(self, row: dict[str, Any], header: str) -> Any:
        if header == 'time':
            return self._first_defined(row, ['time', 'timestamp'])
        if header == 'receive_time':
            return self._first_defined(row, ['receive_time', 'arrival_ts'])
        if header == 'TimeStamp':
            return self._first_defined(row, ['TimeStamp', 'device_ts'])
        source_key = header
        if header.startswith('pwms_'):
            suffix = header.split('_', 1)[1]
            if suffix.isdigit():
                source_key = f'pwm{int(suffix) + 1}'
        elif header == 'time':
            source_key = 'timestamp'
        else:
            source_key = header
        return row.get(source_key, '')

    def _resolve_scenario(self, row: dict[str, Any]) -> Any:
        return self._first_defined(row, ['scenario'], default=self._default_scenario())

    def _resolve_cmd_idx(self, row: dict[str, Any]) -> Any:
        return self._first_defined(row, ['cmd_idx', 'Tele_GCS_CmdIdx'], default=self._default_cmd_idx())

    def _resolve_cmd_mission(self, row: dict[str, Any]) -> Any:
        return self._first_defined(row, ['cmd_mission', 'Tele_GCS_Mission'], default=self._default_cmd_mission())

    def _relative_path(self, path: Path) -> str:
        return str(path.relative_to(self.session_dir)).replace('\\', '/')

    def _empty_artifact(self, source_path: Optional[Path], source_kind: str) -> dict[str, Any]:
        missing_inputs = [str(source_path)] if source_path is not None else []
        return {
            'status': 'empty',
            'rows_written': 0,
            'placeholder': False,
            'source_kind': source_kind,
            'source_path': str(source_path) if source_path else '',
            'missing_inputs': missing_inputs,
            'notes': ['source missing or contains no data rows'],
        }

    def _ready_artifact(self, source_path: Optional[Path], source_kind: str, rows_written: int) -> dict[str, Any]:
        return {
            'status': 'ready',
            'rows_written': rows_written,
            'placeholder': False,
            'source_kind': source_kind,
            'source_path': str(source_path) if source_path else '',
            'missing_inputs': [],
            'notes': [],
        }

    def _first_defined(self, row: dict[str, Any], keys: List[str], default: Any = '') -> Any:
        for key in keys:
            value = row.get(key)
            if value not in (None, ''):
                return value
        return default

    def _parse_json_object(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value in (None, ''):
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _first_defined_from_payload(self, payload: dict[str, Any], keys: List[str], default: Any = '') -> Any:
        for key in keys:
            value = self._find_nested_value(payload, key)
            if value not in (None, ''):
                return value
        return default

    def _find_nested_value(self, value: Any, target_key: str) -> Any:
        if isinstance(value, dict):
            if target_key in value and value[target_key] not in (None, ''):
                return value[target_key]
            for nested_value in value.values():
                found = self._find_nested_value(nested_value, target_key)
                if found not in (None, ''):
                    return found
        if isinstance(value, list):
            for item in value:
                found = self._find_nested_value(item, target_key)
                if found not in (None, ''):
                    return found
        return ''

    def _derive_density(self, count_value: Any, reference_value: Any) -> str:
        count = self._to_float(count_value)
        reference = self._to_float(reference_value)
        if reference > 0:
            return self._normalize_numeric_string(count / reference)
        if count > 0:
            return self._normalize_numeric_string(count)
        return '0'

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _normalize_numeric_string(self, value: Any) -> str:
        if value in (None, ''):
            return ''
        if isinstance(value, str) and value.strip().lower().startswith('0x'):
            return str(int(value, 16))
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        if number.is_integer():
            return str(int(number))
        return str(round(number, 6))

    def _normalize_booleanish(self, value: Any) -> str:
        if isinstance(value, bool):
            return '1' if value else '0'
        if value in (None, ''):
            return ''
        text = str(value).strip().lower()
        if text in {'1', 'true', 'yes', 'on'}:
            return '1'
        if text in {'0', 'false', 'no', 'off'}:
            return '0'
        return str(value)

    def _stringify_json_value(self, value: Any) -> str:
        if value in (None, ''):
            return ''
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def _camera_row_has_signal(self, row: dict[str, Any]) -> bool:
        payload = self._parse_json_object(row.get('payload_json'))
        return bool(payload) or any(
            row.get(key) not in (None, '')
            for key in ['msg_type', 'device_ts', 'arrival_ts']
        )