from __future__ import annotations

from typing import Dict

from .models import ParameterSpec


def project_candidate_params(
    base_params: Dict[str, float],
    delta_params: Dict[str, float],
    parameter_specs: Dict[str, ParameterSpec],
) -> Dict[str, float]:
    projected: Dict[str, float] = {}

    for key, spec in parameter_specs.items():
        base_value = float(base_params.get(key, spec.default_value))
        requested_delta = float(delta_params.get(key, 0.0))
        bounded_delta = max(-spec.max_step, min(spec.max_step, requested_delta))
        candidate = base_value + bounded_delta
        projected[key] = max(spec.lower_bound, min(spec.upper_bound, candidate))

    return projected