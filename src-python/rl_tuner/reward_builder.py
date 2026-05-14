from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from .config import PROTECTION_THRESHOLDS, REWARD_NORMALIZATION, REWARD_WEIGHTS


def _pick_float(summary: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = summary.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def build_episode_reward(summary: Dict[str, Any], action_norm: float, task_success: bool = True) -> Tuple[float, dict]:
    tracking_rmse = _pick_float(summary, 'tracking_rmse', 'rmse', 'Ind_Tracking_RMSE') / REWARD_NORMALIZATION['tracking_rmse_scale']
    overshoot = _pick_float(summary, 'overshoot_pct', 'overshoot', 'Ind_Attitude_Overshoot') / REWARD_NORMALIZATION['overshoot_pct_scale']
    steady_state_error = abs(_pick_float(summary, 'steady_state_error', 'steady_error', 'Ind_Steady_State_Error')) / REWARD_NORMALIZATION['steady_state_error_scale']
    pwm_jitter = _pick_float(summary, 'pwm_jitter', 'control_jitter', 'Ind_Control_Jitter') / REWARD_NORMALIZATION['pwm_jitter_scale']

    reward = -(
        REWARD_WEIGHTS['tracking_rmse'] * tracking_rmse
        + REWARD_WEIGHTS['overshoot'] * overshoot
        + REWARD_WEIGHTS['steady_state_error'] * steady_state_error
        + REWARD_WEIGHTS['pwm_jitter'] * pwm_jitter
        + REWARD_WEIGHTS['action_penalty'] * action_norm
    )

    protection_triggered = False
    protection_reasons = []
    if not task_success:
        protection_triggered = True
        protection_reasons.append('task_failed')
        reward -= 2.0

    if overshoot * REWARD_NORMALIZATION['overshoot_pct_scale'] > PROTECTION_THRESHOLDS['overshoot_max']:
        protection_triggered = True
        protection_reasons.append('overshoot_exceeded')
        reward -= 1.0

    if pwm_jitter * REWARD_NORMALIZATION['pwm_jitter_scale'] > PROTECTION_THRESHOLDS['pwm_jitter_max']:
        protection_triggered = True
        protection_reasons.append('pwm_jitter_exceeded')
        reward -= 1.0

    return reward, {
        'tracking_rmse_norm': tracking_rmse,
        'overshoot_norm': overshoot,
        'steady_state_error_abs': steady_state_error,
        'pwm_jitter_norm': pwm_jitter,
        'action_norm': action_norm,
        'protection_triggered': protection_triggered,
        'protection_reasons': protection_reasons,
        'task_success': task_success,
    }


def l2_action_norm(base_params: Dict[str, float], candidate_params: Dict[str, float]) -> float:
    values = []
    for key, candidate_value in candidate_params.items():
        values.append(float(candidate_value) - float(base_params.get(key, 0.0)))
    return math.sqrt(sum(value * value for value in values))