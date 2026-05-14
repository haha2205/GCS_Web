from __future__ import annotations

import csv
import json
import logging
import math
import os
import time
from typing import Any, Callable, Dict, Optional

from .models import EpisodeRecord, SessionRuntime


PLOT_SERIES_KEYS = (
    'time_s',
    'vx_target',
    'vx_actual',
    'vx_error',
    'vx_target_source',
    'vx_actual_source',
    'pitch_actual',
    'pitch_actual_source',
    'pitch_rate_q',
    'pwm_mean',
    'pwm_std',
    'pwm_1',
    'pwm_2',
    'pwm_3',
    'pwm_4',
    'pwm_5',
    'pwm_6',
    'pwm_7',
    'pwm_8',
    'ctrl_vx_dX2Vx',
    'ctrl_vx_var',
    'ctrl_vx_delta',
    'ctrl_vx_p',
    'ctrl_vx_int',
    'ctrl_vx_d',
    'ctrl_ele_ffc',
    'ctrl_theta_trim',
    'ctrl_theta_var',
    'ctrl_delta_theta',
    'ctrl_theta_p',
    'ctrl_theta_d',
    'ctrl_ele_fbc',
    'ctrl_ele_law_out',
)

TRACE_TARGET_ACTIVE_MIN_ABS = 0.05
TRACE_TARGET_PLATEAU_REL_BAND = 0.2
TRACE_TARGET_PLATEAU_ABS_BAND = 0.1
TRACE_STRING_SERIES_KEYS = {'vx_target_source', 'vx_actual_source', 'pitch_actual_source'}


class RLTuningExperimentLogger:
    def __init__(
        self,
        *,
        artifact_root: str,
        logger: Optional[logging.Logger] = None,
        recording_context_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self._artifact_root = artifact_root or os.getcwd()
        self._logger = logger or logging.getLogger(__name__)
        self._recording_context_provider = recording_context_provider

    def build_session_artifact_dir(self, session_id: str) -> str:
        safe_session_id = ''.join(char if char.isalnum() or char in ('-', '_') else '_' for char in session_id)
        return os.path.join(self._artifact_root, 'rl_tuning', safe_session_id)

    def ensure_session_artifact_layout(self, session: SessionRuntime) -> None:
        os.makedirs(session.artifact_dir, exist_ok=True)
        os.makedirs(os.path.join(session.artifact_dir, 'episodes'), exist_ok=True)
        os.makedirs(os.path.join(session.artifact_dir, 'checkpoints'), exist_ok=True)

    @staticmethod
    def _safe_event_name(event: str) -> str:
        raw = ''.join(char if char.isalnum() or char in ('-', '_') else '_' for char in str(event or 'event'))
        return raw or 'event'

    def persist_episode_record(self, session: SessionRuntime, record: EpisodeRecord) -> None:
        self.ensure_session_artifact_layout(session)
        episode_path = os.path.join(session.artifact_dir, 'episodes', f'{record.episode_id}.json')
        history_jsonl_path = os.path.join(session.artifact_dir, 'history.jsonl')

        with open(episode_path, 'w', encoding='utf-8') as file_handle:
            json.dump(record.to_dict(), file_handle, ensure_ascii=False, indent=2)

        with open(history_jsonl_path, 'a', encoding='utf-8') as file_handle:
            file_handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')

        self._persist_plot_bundle_csv(session, record)
        self._persist_offline_transition(session, record)

    def build_checkpoint_path(self, session: SessionRuntime) -> str:
        self.ensure_session_artifact_layout(session)
        return os.path.join(session.artifact_dir, 'checkpoints', 'agent_latest.pt')

    def build_versioned_checkpoint_path(self, session: SessionRuntime, *, event: str, timestamp_ms: int) -> str:
        self.ensure_session_artifact_layout(session)
        event_name = self._safe_event_name(event)
        episode_index = max(0, int(session.current_episode_index or 0))
        filename = f'agent_ep{episode_index:03d}_{timestamp_ms}_{event_name}.pt'
        return os.path.join(session.artifact_dir, 'checkpoints', filename)

    def append_checkpoint_manifest(self, session: SessionRuntime, payload: Dict[str, Any]) -> None:
        self.ensure_session_artifact_layout(session)
        manifest_jsonl_path = os.path.join(session.artifact_dir, 'checkpoints', 'checkpoint_manifest.jsonl')
        with open(manifest_jsonl_path, 'a', encoding='utf-8') as file_handle:
            file_handle.write(json.dumps(payload, ensure_ascii=False) + '\n')

        latest_manifest_path = os.path.join(session.artifact_dir, 'checkpoints', 'checkpoint_latest.json')
        with open(latest_manifest_path, 'w', encoding='utf-8') as file_handle:
            json.dump(payload, file_handle, ensure_ascii=False, indent=2)

    def persist_session_snapshot(self, session: SessionRuntime, *, event: str, checkpoint_metadata: Optional[Dict[str, Any]] = None) -> None:
        self.ensure_session_artifact_layout(session)
        snapshot = {
            'event': event,
            'timestamp': int(time.time() * 1000),
            'session': session.to_status_dict(),
            'checkpoint': dict(checkpoint_metadata or {}),
            'recording_context': self.get_recording_context(),
            'history': [record.to_dict() for record in session.history],
        }
        snapshot_path = os.path.join(session.artifact_dir, 'session_status.json')
        with open(snapshot_path, 'w', encoding='utf-8') as file_handle:
            json.dump(snapshot, file_handle, ensure_ascii=False, indent=2)

    @staticmethod
    def load_session_snapshot(artifact_dir: str) -> Dict[str, Any]:
        snapshot_path = os.path.join(artifact_dir, 'session_status.json')
        with open(snapshot_path, 'r', encoding='utf-8') as file_handle:
            return json.load(file_handle)

    def get_recording_context(self) -> Dict[str, Any]:
        if self._recording_context_provider is None:
            return {}
        try:
            context = self._recording_context_provider() or {}
            return context if isinstance(context, dict) else {}
        except Exception as exc:
            self._logger.warning('获取录制上下文失败: %s', exc)
            return {}

    def normalize_episode_summary(
        self,
        summary: Dict[str, Any],
        *,
        task_type: str,
        target_vx: Optional[float],
    ) -> Dict[str, Any]:
        normalized = dict(summary or {})
        normalized['summary_schema_version'] = 2
        normalized['task_type'] = normalized.get('task_type') or task_type
        normalized['experiment_group'] = str(normalized.get('experiment_group') or '')
        normalized['target_vx'] = target_vx if target_vx is not None else normalized.get('target_vx')
        normalized['recording_context'] = normalized.get('recording_context') or self.get_recording_context()
        normalized['plot_bundle'] = self._normalize_plot_bundle(normalized.get('plot_bundle') or {})
        normalized['metric_bundle'] = self._build_metric_bundle(normalized)
        for key, value in normalized['metric_bundle'].items():
            if normalized.get(key) is None and value is not None:
                normalized[key] = value
        return normalized

    @staticmethod
    def _representative_target_value(values: list[float]) -> Optional[float]:
        numeric_values = []
        active_values = []
        for value in values:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            numeric_values.append(numeric_value)
            if abs(numeric_value) >= TRACE_TARGET_ACTIVE_MIN_ABS:
                active_values.append(numeric_value)

        candidates = active_values or numeric_values
        if not candidates:
            return None
        return float(max(candidates, key=lambda item: abs(item)))

    @staticmethod
    def _select_representative_tracking_pairs(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
        numeric_pairs = []
        for target, actual in pairs:
            try:
                numeric_pairs.append((float(target), float(actual)))
            except (TypeError, ValueError):
                continue

        if not numeric_pairs:
            return []

        active_pairs = [pair for pair in numeric_pairs if abs(pair[0]) >= TRACE_TARGET_ACTIVE_MIN_ABS]
        base_pairs = active_pairs or numeric_pairs
        target_ref = RLTuningExperimentLogger._representative_target_value([target for target, _ in base_pairs])
        if target_ref is None:
            return base_pairs

        band = max(TRACE_TARGET_PLATEAU_ABS_BAND, abs(target_ref) * TRACE_TARGET_PLATEAU_REL_BAND)
        plateau_pairs = [pair for pair in base_pairs if abs(pair[0] - target_ref) <= band]
        return plateau_pairs or base_pairs

    @staticmethod
    def _normalize_plot_bundle(plot_bundle: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {
            'schema_version': 2,
            'sample_period_ms': None,
            'sample_count': 0,
            'source_map': {},
            'units': {},
        }
        for key in PLOT_SERIES_KEYS:
            normalized[key] = []

        if not isinstance(plot_bundle, dict):
            return normalized

        for key in PLOT_SERIES_KEYS:
            values = plot_bundle.get(key, [])
            if not isinstance(values, list):
                normalized[key] = []
                continue
            if key in TRACE_STRING_SERIES_KEYS:
                normalized[key] = [str(value) for value in values if value is not None]
                continue
            numeric_values = []
            for value in values:
                try:
                    numeric_values.append(float(value))
                except (TypeError, ValueError):
                    continue
            normalized[key] = numeric_values

        raw_source_map = plot_bundle.get('source_map')
        if isinstance(raw_source_map, dict):
            normalized['source_map'] = {str(key): str(value) for key, value in raw_source_map.items()}

        raw_units = plot_bundle.get('units')
        if isinstance(raw_units, dict):
            normalized['units'] = {str(key): str(value) for key, value in raw_units.items()}

        sample_period = plot_bundle.get('sample_period_ms')
        try:
            normalized['sample_period_ms'] = int(float(sample_period)) if sample_period is not None else None
        except (TypeError, ValueError):
            normalized['sample_period_ms'] = None

        normalized['sample_count'] = len(normalized['time_s'])
        return normalized

    @staticmethod
    def _build_metric_bundle(summary: Dict[str, Any]) -> Dict[str, Any]:
        plot_bundle = summary.get('plot_bundle') if isinstance(summary.get('plot_bundle'), dict) else {}

        def pick_float(*keys: str) -> Optional[float]:
            for key in keys:
                value = summary.get(key)
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
            return None

        def numeric_series(key: str) -> list[float]:
            values = plot_bundle.get(key, [])
            if not isinstance(values, list):
                return []
            numeric_values = []
            for value in values:
                try:
                    numeric_values.append(float(value))
                except (TypeError, ValueError):
                    continue
            return numeric_values

        def pair_series(x_key: str, y_key: str) -> list[tuple[float, float]]:
            x_values = numeric_series(x_key)
            y_values = numeric_series(y_key)
            length = min(len(x_values), len(y_values))
            return [(x_values[index], y_values[index]) for index in range(length)]

        tracking_pairs = pair_series('vx_target', 'vx_actual')
        representative_pairs = RLTuningExperimentLogger._select_representative_tracking_pairs(tracking_pairs)
        representative_target = RLTuningExperimentLogger._representative_target_value([target for target, _ in representative_pairs])

        def derive_tracking_rmse() -> Optional[float]:
            if not representative_pairs:
                return None
            mse = sum((target - actual) ** 2 for target, actual in representative_pairs) / len(representative_pairs)
            return math.sqrt(mse)

        def derive_steady_state_error() -> Optional[float]:
            if not representative_pairs:
                return None
            window = max(3, len(representative_pairs) // 5)
            tail = representative_pairs[-window:]
            return sum(actual - target for target, actual in tail) / len(tail)

        def derive_overshoot_pct() -> Optional[float]:
            if not representative_pairs or representative_target is None:
                return None
            if abs(representative_target) < TRACE_TARGET_ACTIVE_MIN_ABS:
                return None
            response_peak = max(actual for _, actual in representative_pairs)
            if representative_target < 0.0:
                response_peak = min(actual for _, actual in representative_pairs)
            overshoot_raw = (response_peak - representative_target) / abs(representative_target) * 100.0
            return max(0.0, overshoot_raw if representative_target > 0.0 else -overshoot_raw)

        def derive_pwm_jitter() -> Optional[float]:
            per_channel_jitters = []
            for channel_index in range(1, 9):
                channel_values = numeric_series(f'pwm_{channel_index}')
                if len(channel_values) < 2:
                    continue
                deltas = [channel_values[index] - channel_values[index - 1] for index in range(1, len(channel_values))]
                if deltas:
                    per_channel_jitters.append(math.sqrt(sum(delta * delta for delta in deltas) / len(deltas) - (sum(deltas) / len(deltas)) ** 2))

            if per_channel_jitters:
                return sum(per_channel_jitters) / len(per_channel_jitters)

            pwm_mean_values = numeric_series('pwm_mean')
            if len(pwm_mean_values) >= 2:
                deltas = [pwm_mean_values[index] - pwm_mean_values[index - 1] for index in range(1, len(pwm_mean_values))]
                if deltas:
                    mean_delta = sum(deltas) / len(deltas)
                    variance = sum((delta - mean_delta) ** 2 for delta in deltas) / len(deltas)
                    return math.sqrt(variance)

            pwm_std_values = numeric_series('pwm_std')
            if pwm_std_values:
                return sum(abs(value) for value in pwm_std_values) / len(pwm_std_values)

            return None

        tracking_rmse = pick_float('tracking_rmse', 'rmse', 'Ind_Tracking_RMSE')
        overshoot_pct = pick_float('overshoot_pct', 'overshoot', 'Ind_Attitude_Overshoot')
        steady_state_error = pick_float('steady_state_error', 'steady_error', 'Ind_Steady_State_Error')
        pwm_jitter = pick_float('pwm_jitter', 'control_jitter', 'Ind_Control_Jitter')

        return {
            'tracking_rmse': tracking_rmse if tracking_rmse is not None else derive_tracking_rmse(),
            'overshoot_pct': overshoot_pct if overshoot_pct is not None else derive_overshoot_pct(),
            'steady_state_error': steady_state_error if steady_state_error is not None else derive_steady_state_error(),
            'pwm_jitter': pwm_jitter if pwm_jitter is not None else derive_pwm_jitter(),
        }

    def _persist_plot_bundle_csv(self, session: SessionRuntime, record: EpisodeRecord) -> None:
        plot_bundle = record.summary.get('plot_bundle') if isinstance(record.summary, dict) else None
        if not isinstance(plot_bundle, dict):
            return

        max_length = max((len(plot_bundle.get(key, [])) for key in PLOT_SERIES_KEYS if isinstance(plot_bundle.get(key), list)), default=0)
        if max_length <= 0:
            return

        traces_dir = os.path.join(session.artifact_dir, 'traces')
        os.makedirs(traces_dir, exist_ok=True)
        csv_path = os.path.join(traces_dir, f'{record.episode_id}.csv')

        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as file_handle:
            writer = csv.DictWriter(file_handle, fieldnames=list(PLOT_SERIES_KEYS))
            writer.writeheader()
            for index in range(max_length):
                row = {}
                for key in PLOT_SERIES_KEYS:
                    values = plot_bundle.get(key, [])
                    row[key] = values[index] if isinstance(values, list) and index < len(values) else ''
                writer.writerow(row)

    def _persist_offline_transition(self, session: SessionRuntime, record: EpisodeRecord) -> None:
        transitions_dir = os.path.join(session.artifact_dir, 'offline_training')
        os.makedirs(transitions_dir, exist_ok=True)

        payload = {
            'session_id': session.session_id,
            'episode_id': record.episode_id,
            'experiment_group': record.experiment_group,
            'target_vx': record.target_vx,
            'state': list(record.latest_state_vector),
            'action': list(record.latest_action_vector),
            'reward': record.reward,
            'next_state': list(record.latest_next_state_vector),
            'done': True,
            'task_success': record.task_success,
            'param_echo_confirmed': record.param_echo_confirmed,
            'protection_triggered': record.protection_triggered,
            'rollback_triggered': record.rollback_triggered,
            'valid_for_learning': bool((record.summary or {}).get('valid_for_learning', True)),
            'invalid_reasons': list((record.summary or {}).get('invalid_reasons') or []),
            'protection_reasons': list((record.summary or {}).get('protection_reasons') or []),
            'candidate_params': dict(record.candidate_params),
            'base_params': dict(record.base_params),
            'agent_metrics': dict(record.agent_metrics),
            'metric_bundle': dict((record.summary or {}).get('metric_bundle') or {}),
        }

        transition_path = os.path.join(transitions_dir, f'{record.episode_id}.json')
        with open(transition_path, 'w', encoding='utf-8') as file_handle:
            json.dump(payload, file_handle, ensure_ascii=False, indent=2)

        jsonl_path = os.path.join(transitions_dir, 'offline_transitions.jsonl')
        with open(jsonl_path, 'a', encoding='utf-8') as file_handle:
            file_handle.write(json.dumps(payload, ensure_ascii=False) + '\n')