from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def cache_ws_snapshot(manager: Any, payload: dict, cache_key: str) -> dict:
    manager.cache_message(payload, cache_key)
    return payload


def get_pipeline_status(
    packet_processing_queue: Any,
    recording_queue: Any,
    online_analysis_queue: Any,
    pending_latest_packets: dict,
    pending_online_analysis_packets: dict,
    packet_drop_counters: dict,
) -> dict:
    return {
        'packet_queue_size': packet_processing_queue.qsize() if packet_processing_queue else 0,
        'recording_queue_size': recording_queue.qsize() if recording_queue else 0,
        'online_analysis_queue_size': online_analysis_queue.qsize() if online_analysis_queue else 0,
        'pending_latest_packet_types': len(pending_latest_packets),
        'pending_online_analysis_packet_types': len(pending_online_analysis_packets),
        'drop_counters': dict(packet_drop_counters),
    }


def get_transport_runtime_stats(udp_handler: Any, empty_recent_snapshot: dict) -> dict:
    if not udp_handler:
        recent = empty_recent_snapshot
        return {
            'is_running': False,
            'listening_ports': [],
            'window_seconds': recent['window_seconds'],
            'rx_datagrams': {
                'packets_total': 0,
                'payload_bytes_total': 0,
                'recent': recent,
                'by_port_total': {},
            },
            'tx_packets': {
                'packets_total': 0,
                'payload_bytes_total': 0,
                'recent': recent,
                'by_source_port_total': {},
                'by_target_total': {},
            },
            'parsed_messages': {
                'messages_total': 0,
                'payload_bytes_total': 0,
                'frame_bytes_total': 0,
                'recent': recent,
                'by_type_total': {},
            },
            'parser_rejections': {
                'total': 0,
                'by_reason_total': {},
                'recent': recent,
            },
            'parser_issues': {
                'total': 0,
                'by_reason_total': {},
                'recent': recent,
            },
        }
    return udp_handler.get_runtime_stats()


def resolve_command_channel(command_type: str) -> Optional[str]:
    if command_type in {'cmd_idx', 'cmd_mission', 'set_pids'}:
        return 'flight_control'
    if command_type in {'gcs_command', 'waypoints_upload'}:
        return 'planning'
    return None


def build_default_session_id(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime('%Y%m%d_%H%M%S')