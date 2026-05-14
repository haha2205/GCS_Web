import sys
import os
from unittest.mock import MagicMock

# Mock torch before importing anything that might use it
sys.modules['torch'] = MagicMock()
sys.modules['torch.nn'] = MagicMock()
sys.modules['torch.optim'] = MagicMock()

import math
from typing import Any, Dict, Optional, List

# Add src-python to sys.path
sys.path.append(os.path.join(os.getcwd(), 'src-python'))

# We want to avoid running rl_tuner/__init__.py if possible or ensure its dependencies are met
# Since we already mocked torch, let's try importing.
from rl_tuner.experiment_logger import RLTuningExperimentLogger, PLOT_SERIES_KEYS, TRACE_STRING_SERIES_KEYS

def run_test():
    # Input data
    raw_plot_bundle = {
        'time_s': [0, 1, 2],
        'vx_target': [1, 1, 1],
        'vx_actual': [0.8, 1.1, 1.0],
        'vx_target_source': ['gncbus_cmd', 'gncbus_cmd', 'gncbus_cmd'],
        'vx_actual_source': ['states_vx_gs', 'states_vx_gs', 'states_vx_gs'],
        'pitch_actual_source': ['states_theta', 'states_theta', 'states_theta'],
        'pwm_std': [0.1, 0.2, 0.3]
    }
    
    # Initialize other keys with empty lists
    for key in PLOT_SERIES_KEYS:
        if key not in raw_plot_bundle:
            raw_plot_bundle[key] = []

    # 1. Normalize
    # RLTuningExperimentLogger is the class
    normalized_bundle = RLTuningExperimentLogger._normalize_plot_bundle(raw_plot_bundle)

    # 2. Metric Bundle
    summary = {'plot_bundle': normalized_bundle}
    metrics = RLTuningExperimentLogger._build_metric_bundle(summary)

    # Validations
    expected_sources = {
        'vx_target_source': ['gncbus_cmd']*3,
        'vx_actual_source': ['states_vx_gs']*3,
        'pitch_actual_source': ['states_theta']*3
    }
    
    preserved = True
    for key, expected in expected_sources.items():
        if normalized_bundle[key] != expected:
            print(f"Mismatch in {key}: expected {expected}, got {normalized_bundle[key]}")
            preserved = False
    
    print(f"Source flag lists preserved: {preserved}")
    print(f"steady_state_error: {metrics.get('steady_state_error')}")

if __name__ == '__main__':
    run_test()
