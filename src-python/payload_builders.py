import time
from typing import Any, Dict, Optional


def normalize_log_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (int, bool)) or value is None:
        return value
    return value


def build_command_log_params(command_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
        normalized = {
            key: normalize_log_value(params[key])
            for key in sorted(params.keys())
        }
        normalized['param_count'] = len(params)
        return normalized
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


def build_ws_payload(
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


def build_recording_status_payload(
    is_active: bool,
    session_id: Optional[str],
    session_info: Optional[dict] = None,
) -> dict:
    session_info = session_info or {}
    duration_sec = 0.0
    if is_active and session_info.get('start_time'):
        duration_sec = max(0.0, time.time() - float(session_info.get('start_time')))
    elif session_info.get('duration') is not None:
        duration_sec = float(session_info.get('duration') or 0.0)

    return build_ws_payload(
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


def build_online_analysis_config_payload(
    enabled: bool,
    mode: str,
    base_url: str,
    project_root: str,
    timeout_ms: int,
) -> dict:
    return build_ws_payload(
        'online_analysis_config',
        data={
            'enabled': enabled,
            'mode': mode,
            'base_url': base_url,
            'project_root': project_root,
            'timeout_ms': timeout_ms,
        },
    )


def build_udp_status_payload(
    is_connected: bool,
    connection_config: Any,
    backend_http_access_host: str,
    backend_http_port: int,
) -> dict:
    return {
        'type': 'udp_status_change',
        'status': 'connected' if is_connected else 'disconnected',
        'config': connection_config.dict(),
        'primary_receive_port': connection_config.hostPort,
        'flight_telemetry_primary_port': connection_config.hostPort,
        'flight_telemetry_fallback_port': connection_config.sendOnlyPort,
        'planning_telemetry_port': connection_config.planningRecvPort,
        'backend_http_url': f'http://{backend_http_access_host}:{backend_http_port}',
        'timestamp': int(time.time() * 1000),
    }


def build_empty_recent_traffic_snapshot(window_seconds: int = 10) -> dict:
    return {
        'window_seconds': window_seconds,
        'overall': {
            'packets': 0,
            'payload_bytes': 0,
            'frame_bytes': 0,
            'pps': 0.0,
            'payload_kbps': 0.0,
            'frame_kbps': 0.0,
        },
        'by_key': {},
    }