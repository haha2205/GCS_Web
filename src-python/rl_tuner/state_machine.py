from __future__ import annotations


ALLOWED_TRANSITIONS = {
    'idle': {'session_ready'},
    'session_ready': {'episode_preparing', 'session_paused', 'session_finished', 'error'},
    'episode_preparing': {'applying_params', 'rollback_pending', 'error'},
    'applying_params': {'waiting_param_echo', 'episode_running', 'rollback_pending', 'error'},
    'waiting_param_echo': {'episode_running', 'rollback_pending', 'error'},
    'episode_running': {'episode_evaluating', 'rollback_pending', 'error'},
    'episode_evaluating': {'agent_updating', 'rollback_pending', 'error'},
    'agent_updating': {'session_ready', 'error'},
    'rollback_pending': {'session_ready', 'error'},
    'session_paused': {'session_ready', 'session_finished', 'error'},
    'session_finished': set(),
    'error': set(),
}


def ensure_transition(current_state: str, next_state: str) -> None:
    if current_state == next_state:
        return

    allowed = ALLOWED_TRANSITIONS.get(current_state, set())
    if next_state not in allowed:
        raise ValueError(f'Invalid state transition: {current_state} -> {next_state}')