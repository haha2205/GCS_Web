from __future__ import annotations

from typing import Dict, List

from .models import ParameterSpec


DEFAULT_PARAMETER_SPECS: Dict[str, ParameterSpec] = {
    'fKeVx': ParameterSpec(
        name='fKeVx',
        default_value=2.0,
        lower_bound=1.2,
        upper_bound=2.8,
        max_step=0.15,
        echo_key='ParamEle_F_KeVx',
    ),
    'fIeVx': ParameterSpec(
        name='fIeVx',
        default_value=0.4,
        lower_bound=0.15,
        upper_bound=0.65,
        max_step=0.04,
        echo_key='ParamEle_F_IeVx',
    ),
    'fKeAx': ParameterSpec(
        name='fKeAx',
        default_value=0.55,
        lower_bound=0.30,
        upper_bound=0.75,
        max_step=0.05,
        echo_key='ParamEle_F_KeAx',
    ),
}

DEFAULT_PARAMETER_KEYS: List[str] = ['fKeVx', 'fIeVx', 'fKeAx']

REWARD_WEIGHTS = {
    'tracking_rmse': 0.40,
    'overshoot': 0.20,
    'steady_state_error': 0.20,
    'pwm_jitter': 0.15,
    'action_penalty': 0.05,
}

REWARD_NORMALIZATION = {
    'tracking_rmse_scale': 5.0,
    'overshoot_pct_scale': 25.0,
    'steady_state_error_scale': 5.0,
    'pwm_jitter_scale': 20.0,
}

PROTECTION_THRESHOLDS = {
    'overshoot_max': 35.0,
    'pwm_jitter_max': 25.0,
    'param_echo_timeout_s': 2.0,
}

EPISODE_VALIDATION = {
    'require_param_echo_confirmed': True,
    'require_trace_sync_ready': True,
    'min_trace_samples': 12,
    'min_trace_metric_samples': 8,
    'min_active_target_abs': 0.05,
}

DEFAULT_ACTION_PATTERNS = [
    {'fKeVx': 0.00, 'fIeVx': 0.00, 'fKeAx': 0.00},
    {'fKeVx': 0.10, 'fIeVx': 0.00, 'fKeAx': -0.02},
    {'fKeVx': -0.10, 'fIeVx': 0.02, 'fKeAx': 0.02},
    {'fKeVx': 0.05, 'fIeVx': -0.02, 'fKeAx': 0.00},
    {'fKeVx': -0.05, 'fIeVx': 0.00, 'fKeAx': -0.03},
]

SAC_DEFAULTS = {
    'gamma': 0.95,
    'tau': 0.02,
    'actor_lr': 0.003,
    'critic_lr': 0.005,
    'alpha_lr': 0.001,
    'init_alpha': 0.2,
    'batch_size': 8,
    'replay_capacity': 2048,
    'warmup_pattern_episodes': 4,
}