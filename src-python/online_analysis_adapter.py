import json
import os
import sys
import urllib.request
from typing import Any, Optional

from events import build_standard_event


def is_online_analysis_embedded(enabled: bool, mode: str) -> bool:
    return enabled and mode == 'embedded'


def is_online_analysis_sidecar(enabled: bool, mode: str) -> bool:
    return enabled and mode == 'sidecar'


def create_embedded_online_analysis_service(
    *,
    enabled: bool,
    mode: str,
    project_root: str,
    logger: Any,
) -> Optional[Any]:
    if not is_online_analysis_embedded(enabled, mode):
        return None

    if not os.path.isdir(project_root):
        logger.warning('OnlineAnalysis embedded 模式不可用，目录不存在: %s', project_root)
        return None

    embedded_src_root = os.path.join(project_root, 'src')
    for candidate_path in (project_root, embedded_src_root):
        if candidate_path and candidate_path not in sys.path:
            sys.path.insert(0, candidate_path)

    try:
        from ground_online import GroundOnlineAnalysisService

        return GroundOnlineAnalysisService(deployment_mode='embedded')
    except Exception as exc:
        logger.warning('OnlineAnalysis embedded 模式初始化失败: %s', exc)
        return None


def should_forward_to_online_analysis(enabled: bool, msg_type: str, forward_types: set[str]) -> bool:
    return enabled and msg_type in forward_types


def get_standard_event_from_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    standard_event = envelope.get('standard_event')
    if isinstance(standard_event, dict):
        return standard_event

    raw_message = envelope.get('data')
    if isinstance(raw_message, dict):
        return build_standard_event(raw_message)

    return {}


def get_online_analysis_routing_key(envelope: dict[str, Any]) -> str:
    standard_event = get_standard_event_from_envelope(envelope)
    routing_key = standard_event.get('routing_key') if isinstance(standard_event, dict) else None
    if routing_key:
        return str(routing_key)
    return str((envelope.get('data') or {}).get('type') or '')


def build_online_analysis_ingest_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    standard_event = get_standard_event_from_envelope(envelope)
    raw_message = envelope.get('data') if isinstance(envelope.get('data'), dict) else {}
    return {
        'type': 'apollo_ingest_event',
        'schema_version': 'apollo-ingest-v2',
        'timestamp': envelope.get('timestamp'),
        'session_id': envelope.get('session_id'),
        'case_id': envelope.get('case_id'),
        'source': envelope.get('source', 'apollo_backend'),
        'standard_event': standard_event,
        'data': raw_message,
    }


def post_online_analysis_ingest_sync(base_url: str, timeout_ms: int, envelope: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(envelope, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        f'{base_url}/ingest/apollo',
        data=body,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=timeout_ms / 1000.0) as response:
        payload = response.read().decode('utf-8')
    return json.loads(payload) if payload else {}


def ingest_online_analysis_sync(
    *,
    envelope: dict[str, Any],
    enabled: bool,
    mode: str,
    base_url: str,
    timeout_ms: int,
    service: Optional[Any],
) -> dict[str, Any]:
    ingest_envelope = build_online_analysis_ingest_envelope(envelope)

    if is_online_analysis_embedded(enabled, mode):
        if service is None:
            raise RuntimeError('OnlineAnalysis embedded service unavailable')
        return service.ingest_apollo_message(ingest_envelope)

    if is_online_analysis_sidecar(enabled, mode):
        return post_online_analysis_ingest_sync(base_url, timeout_ms, ingest_envelope)

    return {}