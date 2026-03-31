import csv
import json
import tempfile
from pathlib import Path

from recorder.data_recorder import (
    BUS_TRAFFIC_HEADERS,
    LIDAR_TELEMETRY_HEADERS,
    PLANNING_TELEMETRY_HEADERS,
    RawDataRecorder,
    _get_fcs_onboard_headers,
)


def _read_header(path: Path):
    with path.open('r', encoding='utf-8', newline='') as handle:
        return next(csv.reader(handle))


def _read_rows(path: Path):
    with path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.reader(handle)
        next(reader)
        return list(reader)


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix='apollo-records-only-') as temp_dir:
        recorder = RawDataRecorder(
            session_id='20260330_235959',
            base_directory=temp_dir,
            session_meta_patch={
                'scenario_id': 'scenario_local_validation',
                'cmd_idx': 17,
                'cmd_mission': 24,
            },
        )
        recorder.start_recording()

        recorder.record_decoded_packet({
            'type': 'fcs_pwms',
            'func_code': 0x41,
            'port_type': 'RECEIVE_EXTY',
            'timestamp': 1711814400000,
            'data': {
                'pwm1': 1100,
                'pwm2': 1200,
                'pwm3': 1300,
                'pwm4': 1400,
            },
        })
        recorder.record_decoded_packet({
            'type': 'fcs_states',
            'func_code': 0x42,
            'port_type': 'RECEIVE_EXTY',
            'timestamp': 1711814400010,
            'data': {
                'lat': 31.123,
                'lon': 121.456,
                'height': 50.5,
                'psi': 15.0,
            },
        })
        recorder.record_decoded_packet({
            'type': 'fcs_root',
            'func_code': 0x4B,
            'port_type': 'RECEIVE_EXTY',
            'timestamp': 1711814400015,
            'data': {
                'YaccLMT': 1.2,
                'XaccLMT': 2.3,
                'Hground': 10.0,
                'AutoTakeoffHcmd': 30.0,
                'ftb_intterrupt_plan': 0,
            },
        })
        recorder.record_decoded_packet({
            'type': 'fcs_esc',
            'func_code': 0x4A,
            'port_type': 'RECEIVE_EXTY',
            'timestamp': 1711814400018,
            'data': {
                'esc1_error_count': 1,
                'esc1_voltage': 44.4,
                'esc1_current': 8.2,
                'esc1_temperature': 35.0,
                'esc1_rpm': 3200,
                'esc1_power_rating_pct': 56,
            },
        })
        recorder.record_decoded_packet({
            'type': 'fcs_param',
            'func_code': 0x49,
            'port_type': 'RECEIVE_EXTY',
            'timestamp': 1711814400020,
            'data': {
                'ParamAil_F_KaPHI': 0.8,
                'ParamAil_YaccLMT': 1.2,
                'ParamEle_XaccLMT': 2.3,
                'ParamGuide_Hground': 10.0,
                'ParamGuide_AutoTakeoffHcmd': 35.0,
            },
        })
        recorder.record_decoded_packet({
            'type': 'planning_telemetry',
            'func_code': 0x71,
            'port_type': 'PLANNING',
            'timestamp': 1711814400100,
            'data': {
                'seq_id': 5,
                'timestamp': 1711814400.1,
                'current_pos_x': 100.0,
                'current_pos_y': 20.0,
                'current_pos_z': 50.0,
                'current_vel': 12.5,
                'update_flags': 0b111,
                'status': 1,
                'global_path': [
                    {'x': 0, 'y': 0, 'z': 10},
                    {'x': 10, 'y': 0, 'z': 12},
                ],
                'local_path': [
                    {'x': 1, 'y': 1, 'z': 10.5},
                    {'x': 2, 'y': 1.5, 'z': 10.8},
                ],
                'obstacles': [
                    {
                        'center': {'x': 50.0, 'y': 10.0, 'z': 52.0},
                        'size': {'x': 5.0, 'y': 6.0, 'z': 3.0},
                        'velocity': {'x': 1.2, 'y': 0.0, 'z': -0.1},
                    },
                    {
                        'center': {'x': 80.0, 'y': -4.0, 'z': 55.0},
                        'size': {'x': 4.0, 'y': 4.5, 'z': 2.5},
                        'velocity': {'x': 0.0, 'y': 0.5, 'z': 0.0},
                    },
                ],
            },
        })

        recorder.stop_recording()

        session_dir = Path(temp_dir) / '20260330_235959'
        records_dir = session_dir / 'records'
        fcs_file = records_dir / 'fcs' / 'fcs_telemetry.csv'
        planning_file = records_dir / 'planning' / 'planning_telemetry.csv'
        lidar_file = records_dir / 'lidar' / 'radar_data.csv'
        bus_file = records_dir / 'bus' / 'bus_traffic.csv'
        camera_dir = records_dir / 'camera'
        function_dir = records_dir / 'function_packets'
        session_meta_file = session_dir / 'session_meta.json'
        quality_report_file = session_dir / 'data_quality_report.json'

        for path in [
            fcs_file,
            planning_file,
            lidar_file,
            bus_file,
            session_meta_file,
            quality_report_file,
        ]:
            _assert(path.exists(), f'missing expected output: {path}')

        _assert(camera_dir.exists() and camera_dir.is_dir(), 'camera directory must exist')
        _assert((session_dir / 'analysis').exists() is False, 'analysis directory should not exist')
        _assert((session_dir / 'runtime').exists() is False, 'runtime directory should not exist')
        _assert((session_dir / 'raw').exists() is False, 'raw directory should not exist')

        _assert(_read_header(planning_file) == PLANNING_TELEMETRY_HEADERS, 'planning header mismatch')
        _assert(_read_header(lidar_file) == LIDAR_TELEMETRY_HEADERS, 'lidar header mismatch')
        _assert(_read_header(bus_file) == BUS_TRAFFIC_HEADERS, 'bus header mismatch')

        fcs_header = _read_header(fcs_file)
        expected_fcs_header = _get_fcs_onboard_headers()
        _assert(fcs_header == expected_fcs_header, 'fcs header mismatch')

        _assert(len(_read_rows(fcs_file)) == 2, 'expected two fcs telemetry rows')
        _assert(len(_read_rows(planning_file)) == 1, 'expected one planning row')
        planning_rows = _read_rows(planning_file)
        lidar_rows = _read_rows(lidar_file)
        _assert(len(planning_rows) == 1, 'expected one planning row')
        _assert(len(lidar_rows) == 2, 'expected two lidar rows')
        _assert(len(_read_rows(bus_file)) == 6, 'expected six bus rows')

        function_files = sorted(function_dir.glob('*.csv'))
        _assert(len(function_files) == 6, 'expected six function packet files')

        planning_row = planning_rows[0]
        _assert(planning_row[3:7] == ['100.0', '20.0', '50.0', '12.5'], 'planning fixed fields mismatch')
        _assert(planning_row[8:11] == ['1', '1', '1'], 'planning update flags mismatch')
        _assert(planning_row[13].startswith('[{"x":0.0,"y":0.0,"z":10.0}'), 'global path json mismatch')
        _assert(planning_row[15].startswith('[{"x":1.0,"y":1.0,"z":10.5}'), 'local traj json mismatch')
        _assert(lidar_rows[0][5:14] == ['50.0', '10.0', '52.0', '5.0', '6.0', '3.0', '1.2', '0.0', '-0.1'], 'first lidar row mismatch')
        _assert(lidar_rows[1][5:14] == ['80.0', '-4.0', '55.0', '4.0', '4.5', '2.5', '0.0', '0.5', '0.0'], 'second lidar row mismatch')

        session_meta = json.loads(session_meta_file.read_text(encoding='utf-8'))
        _assert(session_meta['record_layout_version'] == 'records-only-v1', 'record layout version mismatch')
        _assert('analysis_runtime' not in json.dumps(session_meta, ensure_ascii=False), 'obsolete analysis metadata still present')

        print(json.dumps({
            'session_directory': str(session_dir),
            'generated_function_files': [path.name for path in function_files],
            'bus_rows': len(_read_rows(bus_file)),
            'radar_rows': len(lidar_rows),
            'validated_outputs': [
                'records/fcs/fcs_telemetry.csv',
                'records/planning/planning_telemetry.csv',
                'records/lidar/radar_data.csv',
                'records/bus/bus_traffic.csv',
                'records/function_packets/*.csv',
                'records/camera/',
            ],
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()