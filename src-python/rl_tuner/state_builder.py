from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def _pick_float(container: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = container.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _task_phase_code(state_name: str) -> float:
    mapping = {
        'session_ready': 0.0,
        'episode_preparing': 0.2,
        'applying_params': 0.3,
        'waiting_param_echo': 0.4,
        'episode_running': 0.6,
        'episode_evaluating': 0.8,
        'agent_updating': 1.0,
    }
    return mapping.get(state_name, 0.0)


def build_state_vector(
    *,
    tracked_messages: Dict[str, dict],
    summary: Dict[str, Any],
    current_params: Dict[str, float],
    task_phase: str,
) -> np.ndarray:
    fcs_states = (tracked_messages.get('fcs_states') or {}).get('data', {})
    fcs_gncbus = (tracked_messages.get('fcs_gncbus') or {}).get('data', {})
    fcs_pwms = (tracked_messages.get('fcs_pwms') or {}).get('data', {})

    if isinstance(fcs_pwms, dict):
        pwm_values = fcs_pwms.get('pwms') or []
    elif isinstance(fcs_pwms, list):
        pwm_values = fcs_pwms
    else:
        pwm_values = []

    normalized_pwm_values = []
    for value in pwm_values[:6]:
        try:
            normalized_pwm_values.append(float(value))
        except (TypeError, ValueError):
            continue

    pwm_mean = float(np.mean(normalized_pwm_values)) if normalized_pwm_values else 0.0
    pwm_std = float(np.std(normalized_pwm_values)) if normalized_pwm_values else 0.0

    vx_cmd = _pick_float(fcs_gncbus, 'GNCBus_CmdValue_Vx_cmd')
    vx = _pick_float(fcs_states, 'states_Vx_GS')

    vector: List[float] = [
        vx_cmd,
        vx,
        vx_cmd - vx,
        _pick_float(summary, 'error_rate', 'de_vx', default=0.0),
        _pick_float(summary, 'tracking_rmse', 'rmse', 'Ind_Tracking_RMSE', default=0.0),
        abs(_pick_float(summary, 'steady_state_error', 'steady_error', default=0.0)),
        _pick_float(summary, 'overshoot_pct', 'overshoot', default=0.0),
        _pick_float(summary, 'pwm_jitter', 'control_jitter', default=pwm_std),
        pwm_mean,
        pwm_std,
        float(current_params.get('fKeVx', 0.0)),
        float(current_params.get('fIeVx', 0.0)),
        float(current_params.get('fKeAx', 0.0)),
        _pick_float(summary, 'voltage', 'battery_voltage', default=0.0),
        _task_phase_code(task_phase),
    ]
    return np.asarray(vector, dtype=np.float64)