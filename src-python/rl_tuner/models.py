from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParameterSpec:
    name: str
    default_value: float
    lower_bound: float
    upper_bound: float
    max_step: float
    echo_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'default_value': self.default_value,
            'lower_bound': self.lower_bound,
            'upper_bound': self.upper_bound,
            'max_step': self.max_step,
            'echo_key': self.echo_key,
        }


@dataclass
class EpisodeRecord:
    episode_id: str
    started_at_ms: int
    finished_at_ms: Optional[int] = None
    experiment_group: str = ''
    target_vx: Optional[float] = None
    base_params: Dict[str, float] = field(default_factory=dict)
    candidate_params: Dict[str, float] = field(default_factory=dict)
    latest_param_echo: Dict[str, float] = field(default_factory=dict)
    param_echo_confirmed: bool = False
    reward: Optional[float] = None
    task_success: bool = True
    protection_triggered: bool = False
    rollback_triggered: bool = False
    latest_state_vector: List[float] = field(default_factory=list)
    latest_next_state_vector: List[float] = field(default_factory=list)
    latest_action_vector: List[float] = field(default_factory=list)
    agent_metrics: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'episode_id': self.episode_id,
            'started_at_ms': self.started_at_ms,
            'finished_at_ms': self.finished_at_ms,
            'experiment_group': self.experiment_group,
            'target_vx': self.target_vx,
            'base_params': dict(self.base_params),
            'candidate_params': dict(self.candidate_params),
            'latest_param_echo': dict(self.latest_param_echo),
            'param_echo_confirmed': self.param_echo_confirmed,
            'reward': self.reward,
            'task_success': self.task_success,
            'protection_triggered': self.protection_triggered,
            'rollback_triggered': self.rollback_triggered,
            'latest_state_vector': list(self.latest_state_vector),
            'latest_next_state_vector': list(self.latest_next_state_vector),
            'latest_action_vector': list(self.latest_action_vector),
            'agent_metrics': dict(self.agent_metrics),
            'summary': dict(self.summary),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> 'EpisodeRecord':
        return cls(
            episode_id=str(payload.get('episode_id') or ''),
            started_at_ms=int(payload.get('started_at_ms') or 0),
            finished_at_ms=int(payload['finished_at_ms']) if payload.get('finished_at_ms') is not None else None,
            experiment_group=str(payload.get('experiment_group') or ''),
            target_vx=float(payload['target_vx']) if payload.get('target_vx') is not None else None,
            base_params={str(key): float(value) for key, value in dict(payload.get('base_params') or {}).items()},
            candidate_params={str(key): float(value) for key, value in dict(payload.get('candidate_params') or {}).items()},
            latest_param_echo={str(key): float(value) for key, value in dict(payload.get('latest_param_echo') or {}).items()},
            param_echo_confirmed=bool(payload.get('param_echo_confirmed', False)),
            reward=float(payload['reward']) if payload.get('reward') is not None else None,
            task_success=bool(payload.get('task_success', True)),
            protection_triggered=bool(payload.get('protection_triggered', False)),
            rollback_triggered=bool(payload.get('rollback_triggered', False)),
            latest_state_vector=[float(value) for value in list(payload.get('latest_state_vector') or [])],
            latest_next_state_vector=[float(value) for value in list(payload.get('latest_next_state_vector') or [])],
            latest_action_vector=[float(value) for value in list(payload.get('latest_action_vector') or [])],
            agent_metrics=dict(payload.get('agent_metrics') or {}),
            summary=dict(payload.get('summary') or {}),
        )


@dataclass
class SessionRuntime:
    session_id: str
    task_type: str
    parameter_keys: List[str]
    strategy_mode: str
    max_episodes: int
    created_at_ms: int
    state: str = 'session_ready'
    current_episode_index: int = 0
    current_episode_id: str = ''
    current_episode_started_at_ms: int = 0
    current_params: Dict[str, float] = field(default_factory=dict)
    safe_params: Dict[str, float] = field(default_factory=dict)
    candidate_params: Dict[str, float] = field(default_factory=dict)
    episode_base_params: Dict[str, float] = field(default_factory=dict)
    latest_param_echo: Dict[str, float] = field(default_factory=dict)
    tracked_messages: Dict[str, dict] = field(default_factory=dict)
    param_echo_confirmed: bool = False
    episode_param_echo_confirmed_once: bool = False
    rollback_triggered: bool = False
    last_reward: Optional[float] = None
    best_reward: Optional[float] = None
    last_summary: Dict[str, Any] = field(default_factory=dict)
    latest_state_vector: List[float] = field(default_factory=list)
    latest_next_state_vector: List[float] = field(default_factory=list)
    latest_action_vector: List[float] = field(default_factory=list)
    agent_metrics: Dict[str, Any] = field(default_factory=dict)
    replay_size: int = 0
    artifact_dir: str = ''
    checkpoint_path: str = ''
    checkpoint_updated_at_ms: int = 0
    restored_from_artifact: str = ''
    current_episode_trace: Dict[str, Any] = field(default_factory=dict)
    current_episode_trace_started_at_ms: int = 0
    current_episode_last_trace_at_ms: int = 0
    history: List[EpisodeRecord] = field(default_factory=list)

    def to_status_dict(self) -> dict[str, Any]:
        return {
            'session_id': self.session_id,
            'task_type': self.task_type,
            'parameter_keys': list(self.parameter_keys),
            'strategy_mode': self.strategy_mode,
            'max_episodes': self.max_episodes,
            'created_at_ms': self.created_at_ms,
            'state': self.state,
            'current_episode_index': self.current_episode_index,
            'current_episode_id': self.current_episode_id,
            'current_params': dict(self.current_params),
            'safe_params': dict(self.safe_params),
            'candidate_params': dict(self.candidate_params),
            'latest_param_echo': dict(self.latest_param_echo),
            'param_echo_confirmed': self.param_echo_confirmed,
            'episode_param_echo_confirmed_once': self.episode_param_echo_confirmed_once,
            'rollback_triggered': self.rollback_triggered,
            'last_reward': self.last_reward,
            'best_reward': self.best_reward,
            'last_summary': dict(self.last_summary),
            'latest_state_vector': list(self.latest_state_vector),
            'latest_next_state_vector': list(self.latest_next_state_vector),
            'latest_action_vector': list(self.latest_action_vector),
            'agent_metrics': dict(self.agent_metrics),
            'replay_size': self.replay_size,
            'artifact_dir': self.artifact_dir,
            'checkpoint_path': self.checkpoint_path,
            'checkpoint_updated_at_ms': self.checkpoint_updated_at_ms,
            'restored_from_artifact': self.restored_from_artifact,
            'current_trace_samples': len((self.current_episode_trace or {}).get('time_s', [])),
            'history_size': len(self.history),
        }

    @classmethod
    def from_snapshot(cls, payload: Dict[str, Any], history: List[EpisodeRecord]) -> 'SessionRuntime':
        return cls(
            session_id=str(payload.get('session_id') or ''),
            task_type=str(payload.get('task_type') or 'velocity_tracking'),
            parameter_keys=[str(value) for value in list(payload.get('parameter_keys') or [])],
            strategy_mode=str(payload.get('strategy_mode') or ''),
            max_episodes=int(payload.get('max_episodes') or 20),
            created_at_ms=int(payload.get('created_at_ms') or 0),
            state=str(payload.get('state') or 'session_ready'),
            current_episode_index=int(payload.get('current_episode_index') or 0),
            current_episode_id=str(payload.get('current_episode_id') or ''),
            current_episode_started_at_ms=int(payload.get('current_episode_started_at_ms') or 0),
            current_params={str(key): float(value) for key, value in dict(payload.get('current_params') or {}).items()},
            safe_params={str(key): float(value) for key, value in dict(payload.get('safe_params') or {}).items()},
            candidate_params={str(key): float(value) for key, value in dict(payload.get('candidate_params') or {}).items()},
            episode_base_params={str(key): float(value) for key, value in dict(payload.get('episode_base_params') or {}).items()},
            latest_param_echo={str(key): float(value) for key, value in dict(payload.get('latest_param_echo') or {}).items()},
            tracked_messages=dict(payload.get('tracked_messages') or {}),
            param_echo_confirmed=bool(payload.get('param_echo_confirmed', False)),
            episode_param_echo_confirmed_once=bool(payload.get('episode_param_echo_confirmed_once', False)),
            rollback_triggered=bool(payload.get('rollback_triggered', False)),
            last_reward=float(payload['last_reward']) if payload.get('last_reward') is not None else None,
            best_reward=float(payload['best_reward']) if payload.get('best_reward') is not None else None,
            last_summary=dict(payload.get('last_summary') or {}),
            latest_state_vector=[float(value) for value in list(payload.get('latest_state_vector') or [])],
            latest_next_state_vector=[float(value) for value in list(payload.get('latest_next_state_vector') or [])],
            latest_action_vector=[float(value) for value in list(payload.get('latest_action_vector') or [])],
            agent_metrics=dict(payload.get('agent_metrics') or {}),
            replay_size=int(payload.get('replay_size') or 0),
            artifact_dir=str(payload.get('artifact_dir') or ''),
            checkpoint_path=str(payload.get('checkpoint_path') or ''),
            checkpoint_updated_at_ms=int(payload.get('checkpoint_updated_at_ms') or 0),
            restored_from_artifact=str(payload.get('restored_from_artifact') or ''),
            current_episode_trace=dict(payload.get('current_episode_trace') or {}),
            current_episode_trace_started_at_ms=int(payload.get('current_episode_trace_started_at_ms') or 0),
            current_episode_last_trace_at_ms=int(payload.get('current_episode_last_trace_at_ms') or 0),
            history=list(history),
        )