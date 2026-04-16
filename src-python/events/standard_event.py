from __future__ import annotations

from hashlib import sha1
from typing import Any, Dict


EVENT_DESCRIPTOR_MAP = {
    'fcs_pwms': {
        'event_type': 'telemetry.flight_control.pwms',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_states': {
        'event_type': 'telemetry.flight_control.states',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_datactrl': {
        'event_type': 'telemetry.flight_control.datactrl',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_gncbus': {
        'event_type': 'telemetry.flight_control.gncbus',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'avoiflag': {
        'event_type': 'telemetry.flight_control.avoiflag',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_datafutaba': {
        'event_type': 'telemetry.flight_control.futaba',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_datagcs': {
        'event_type': 'telemetry.flight_control.datagcs',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_line_aim2ab': {
        'event_type': 'telemetry.flight_control.line_aim2ab',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_line_ab': {
        'event_type': 'telemetry.flight_control.line_ab',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_param': {
        'event_type': 'telemetry.flight_control.param',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_esc': {
        'event_type': 'telemetry.flight_control.esc',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'fcs_root': {
        'event_type': 'telemetry.flight_control.root',
        'domain': 'flight_control',
        'category': 'telemetry',
        'producer': 'fcs',
    },
    'planning_telemetry': {
        'event_type': 'telemetry.planning.state',
        'domain': 'planning',
        'category': 'telemetry',
        'producer': 'planning',
    },
    'heartbeat_ack': {
        'event_type': 'system.transport.heartbeat_ack',
        'domain': 'transport',
        'category': 'system',
        'producer': 'fcs',
    },
    'unknown': {
        'event_type': 'telemetry.unknown',
        'domain': 'unknown',
        'category': 'unknown',
        'producer': 'unknown',
    },
}

HIGH_FREQUENCY_ROUTING_KEYS = {
    'fcs_pwms',
    'fcs_states',
    'fcs_datactrl',
    'fcs_gncbus',
    'fcs_esc',
    'planning_telemetry',
}


def _normalize_port_type(port_type: Any) -> str:
    return getattr(port_type, 'name', str(port_type or 'unknown'))


def _extract_sequence(payload: Dict[str, Any]) -> Any:
    for key in ('seq_id', 'seqId', 'sequence', 'sequence_id', 'timestamp_remote'):
        if key in payload and payload.get(key) not in (None, ''):
            return payload.get(key)
    return None


def _build_event_id(msg_type: str, func_code_hex: str, occurred_at_ms: int, sequence: Any) -> str:
    fingerprint = f'{msg_type}|{func_code_hex}|{occurred_at_ms}|{sequence}'
    return sha1(fingerprint.encode('utf-8')).hexdigest()[:16]


def _infer_priority(msg_type: str) -> str:
    return 'high' if msg_type in HIGH_FREQUENCY_ROUTING_KEYS else 'normal'


def build_standard_event(message: Dict[str, Any], transport: str = 'udp') -> Dict[str, Any]:
    msg_type = str(message.get('type') or 'unknown')
    descriptor = EVENT_DESCRIPTOR_MAP.get(msg_type, EVENT_DESCRIPTOR_MAP['unknown'])
    func_code = int(message.get('func_code', 0) or 0)
    func_code_hex = str(message.get('func_code_hex') or f'0x{func_code:02X}')
    occurred_at_ms = int(message.get('timestamp', 0) or 0)
    payload = message.get('data', {}) or {}
    port_type_name = _normalize_port_type(message.get('port_type'))
    sequence = _extract_sequence(payload)

    return {
        'schema_version': 'canonical-event-v1',
        'event_id': _build_event_id(msg_type, func_code_hex, occurred_at_ms, sequence),
        'event_type': descriptor['event_type'],
        'category': descriptor['category'],
        'domain': descriptor['domain'],
        'producer': descriptor['producer'],
        'routing_key': msg_type,
        'priority': _infer_priority(msg_type),
        'occurred_at_ms': occurred_at_ms,
        'sequence': sequence,
        'source': {
            'system': 'apollo_gcs_backend',
            'transport': transport,
            'port_type': port_type_name,
            'func_code': func_code,
            'func_code_hex': func_code_hex,
            'message_type': msg_type,
        },
        'quality': {
            'payload_size': int(message.get('payload_size', 0) or 0),
            'frame_size': int(message.get('frame_size', 0) or 0),
            'skip_recording': bool(message.get('skip_recording')),
        },
        'payload': payload,
    }