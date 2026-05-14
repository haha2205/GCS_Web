from __future__ import annotations

import asyncio
import math
import logging
import os
import shutil
import time
from typing import Any, Awaitable, Callable, Dict, Optional

import numpy as np
import torch

from .action_projector import project_candidate_params
from .config import DEFAULT_ACTION_PATTERNS, DEFAULT_PARAMETER_KEYS, DEFAULT_PARAMETER_SPECS, EPISODE_VALIDATION, PROTECTION_THRESHOLDS, SAC_DEFAULTS
from .experiment_logger import RLTuningExperimentLogger
from .models import EpisodeRecord, SessionRuntime
from .replay_buffer import ReplayBuffer
from .reward_builder import build_episode_reward
from .sac_agent import LightweightSACAgent
from .state_builder import build_state_vector
from .state_machine import ensure_transition


SAC_RUNTIME_MODE = 'torch_sac'


TRACE_SAMPLE_MESSAGE_TYPES = {'fcs_states', 'fcs_gncbus', 'fcs_pwms', 'fcs_datactrl'}
TRACE_SAMPLE_MIN_INTERVAL_MS = 50
TRACE_SYNC_MAX_SKEW_MS = 80
TRACE_TARGET_ACTIVE_MIN_ABS = 0.05
TRACE_TARGET_PLATEAU_REL_BAND = 0.2
TRACE_TARGET_PLATEAU_ABS_BAND = 0.1
TRACE_SOURCE_MAP = {
    'vx_target': 'fcs_gncbus.data.GNCBus_CmdValue_Vx_cmd',
    'vx_actual': 'fcs_states.data.states_Vx_GS',
    'vx_error': 'fcs_gncbus.data.GNCBus_CmdValue_Vx_cmd - fcs_states.data.states_Vx_GS',
    'vx_target_source': 'gncbus_cmd | datactrl_ref_vx_fallback',
    'vx_actual_source': 'states_vx_gs | datactrl_est_vx_fallback',
    'pitch_actual': 'fcs_states.data.states_theta',
    'pitch_actual_source': 'states_theta | datactrl_est_theta_fallback',
    'pitch_rate_q': 'fcs_states.data.states_q',
    'pwm_mean': 'fcs_pwms.data.pwms[0:8]',
    'pwm_std': 'fcs_pwms.data.pwms[0:8]',
    'pwm_1': 'fcs_pwms.data.pwms[0]',
    'pwm_2': 'fcs_pwms.data.pwms[1]',
    'pwm_3': 'fcs_pwms.data.pwms[2]',
    'pwm_4': 'fcs_pwms.data.pwms[3]',
    'pwm_5': 'fcs_pwms.data.pwms[4]',
    'pwm_6': 'fcs_pwms.data.pwms[5]',
    'pwm_7': 'fcs_pwms.data.pwms[6]',
    'pwm_8': 'fcs_pwms.data.pwms[7]',
    'ctrl_vx_dX2Vx': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_Vx_dX2Vx',
    'ctrl_vx_var': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_Vx_var',
    'ctrl_vx_delta': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_Vx_delta',
    'ctrl_vx_p': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_Vx_P',
    'ctrl_vx_int': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_Vx_Int',
    'ctrl_vx_d': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_Vx_D',
    'ctrl_ele_ffc': 'fcs_datactrl.data.dataCtrl_n_eleOutLoop_ele_ffc',
    'ctrl_theta_trim': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_theta_trim',
    'ctrl_theta_var': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_theta_var',
    'ctrl_delta_theta': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_delta_theta',
    'ctrl_theta_p': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_theta_P',
    'ctrl_theta_d': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_theta_D',
    'ctrl_ele_fbc': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_ele_fbc',
    'ctrl_ele_law_out': 'fcs_datactrl.data.dataCtrl_n_EleInLoop_ele_law_out',
}
TRACE_UNITS = {
    'vx_target': 'm/s',
    'vx_actual': 'm/s',
    'vx_error': 'm/s',
    'vx_target_source': 'source_flag',
    'vx_actual_source': 'source_flag',
    'pitch_actual': 'fcs_native_angle',
    'pitch_actual_source': 'source_flag',
    'pitch_rate_q': 'fcs_native_rate',
    'pwm_mean': 'fcs_native_pwm',
    'pwm_std': 'fcs_native_pwm',
    'pwm_1': 'fcs_native_pwm',
    'pwm_2': 'fcs_native_pwm',
    'pwm_3': 'fcs_native_pwm',
    'pwm_4': 'fcs_native_pwm',
    'pwm_5': 'fcs_native_pwm',
    'pwm_6': 'fcs_native_pwm',
    'pwm_7': 'fcs_native_pwm',
    'pwm_8': 'fcs_native_pwm',
    'ctrl_vx_dX2Vx': 'fcs_native_control',
    'ctrl_vx_var': 'fcs_native_control',
    'ctrl_vx_delta': 'fcs_native_control',
    'ctrl_vx_p': 'fcs_native_control',
    'ctrl_vx_int': 'fcs_native_control',
    'ctrl_vx_d': 'fcs_native_control',
    'ctrl_ele_ffc': 'fcs_native_control',
    'ctrl_theta_trim': 'fcs_native_control',
    'ctrl_theta_var': 'fcs_native_control',
    'ctrl_delta_theta': 'fcs_native_control',
    'ctrl_theta_p': 'fcs_native_control',
    'ctrl_theta_d': 'fcs_native_control',
    'ctrl_ele_fbc': 'fcs_native_control',
    'ctrl_ele_law_out': 'fcs_native_control',
}
TRACE_METADATA_DEFAULTS = {
    'sync_required_types': sorted(TRACE_SAMPLE_MESSAGE_TYPES),
    'sync_max_skew_ms': TRACE_SYNC_MAX_SKEW_MS,
}


class PIDTuningService:
    def __init__(
        self,
        *,
        send_pid_params_handler: Callable[[dict], Awaitable[dict]],
        cached_pid_params: Dict[str, float],
        baseline_pid_params: Optional[Dict[str, float]] = None,
        broadcast_handler: Optional[Callable[[dict], Awaitable[None]]] = None,
        logger: Optional[logging.Logger] = None,
        artifact_root: str = '',
        recording_context_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self._send_pid_params_handler = send_pid_params_handler
        self._cached_pid_params = cached_pid_params
        self._baseline_pid_params = {
            str(key): float(value)
            for key, value in dict(baseline_pid_params or cached_pid_params).items()
        }
        self._broadcast_handler = broadcast_handler
        self._logger = logger or logging.getLogger(__name__)
        self._artifact_logger = RLTuningExperimentLogger(
            artifact_root=artifact_root,
            logger=self._logger,
            recording_context_provider=recording_context_provider,
        )
        self._parameter_specs = DEFAULT_PARAMETER_SPECS
        self._session: Optional[SessionRuntime] = None
        self._latest_messages: Dict[str, dict] = {}
        self._pending_echo_deadline_monotonic: float = 0.0
        self._replay_buffer = ReplayBuffer(capacity=SAC_DEFAULTS['replay_capacity'])
        self._sac_agent: Optional[LightweightSACAgent] = None

    def _resolve_strategy_mode(self, strategy_mode: str) -> str:
        return SAC_RUNTIME_MODE

    def _default_agent_metrics(self) -> Dict[str, Any]:
        return {
            'mode': SAC_RUNTIME_MODE,
            'actor_loss': None,
            'critic1_loss': None,
            'critic2_loss': None,
            'alpha': SAC_DEFAULTS['init_alpha'],
            'avg_q': None,
            'avg_log_prob': None,
            'policy_mean': [],
            'policy_std': [],
            'policy_log_prob': None,
            'last_episode_valid_for_learning': None,
            'last_invalid_reasons': [],
        }

    def _create_agent(self, *, state_dim: int, action_dim: int) -> LightweightSACAgent:
        return LightweightSACAgent(
            state_dim=state_dim,
            action_dim=action_dim,
            gamma=SAC_DEFAULTS['gamma'],
            tau=SAC_DEFAULTS['tau'],
            actor_lr=SAC_DEFAULTS['actor_lr'],
            critic_lr=SAC_DEFAULTS['critic_lr'],
            alpha_lr=SAC_DEFAULTS['alpha_lr'],
            init_alpha=SAC_DEFAULTS['init_alpha'],
            batch_size=SAC_DEFAULTS['batch_size'],
        )

    def _resolve_default_pid_value(self, key: str) -> float:
        if key in self._baseline_pid_params:
            return float(self._baseline_pid_params[key])
        if key in self._cached_pid_params:
            return float(self._cached_pid_params[key])
        return float(self._parameter_specs[key].default_value)

    def _expand_pid_payload(self, tuned_params: Dict[str, Any]) -> Dict[str, float]:
        payload = {
            str(key): float(value)
            for key, value in self._baseline_pid_params.items()
        }
        for key, value in dict(tuned_params or {}).items():
            try:
                payload[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return payload

    def _save_checkpoint(self, session: SessionRuntime, *, event: str) -> Dict[str, Any]:
        if self._sac_agent is None:
            return {}

        timestamp = int(time.time() * 1000)
        checkpoint_path = self._artifact_logger.build_checkpoint_path(session)
        versioned_checkpoint_path = self._artifact_logger.build_versioned_checkpoint_path(session, event=event, timestamp_ms=timestamp)
        payload = {
            'event': event,
            'timestamp': timestamp,
            'session_id': session.session_id,
            'strategy_mode': session.strategy_mode,
            'parameter_keys': list(session.parameter_keys),
            'agent_state': self._sac_agent.state_dict(),
            'replay_buffer': self._replay_buffer.state_dict(),
        }
        torch.save(payload, checkpoint_path)
        shutil.copy2(checkpoint_path, versioned_checkpoint_path)
        session.checkpoint_path = checkpoint_path
        session.checkpoint_updated_at_ms = timestamp
        session.replay_size = len(self._replay_buffer)
        metadata = {
            'path': checkpoint_path,
            'versioned_path': versioned_checkpoint_path,
            'updated_at_ms': timestamp,
            'event': event,
            'episode_index': int(session.current_episode_index or 0),
            'replay_size': len(self._replay_buffer),
        }
        self._artifact_logger.append_checkpoint_manifest(session, metadata)
        return metadata

    def _persist_runtime_snapshot(self, session: SessionRuntime, *, event: str) -> None:
        checkpoint_metadata = self._save_checkpoint(session, event=event)
        self._artifact_logger.persist_session_snapshot(session, event=event, checkpoint_metadata=checkpoint_metadata)

    def _rebuild_replay_buffer_from_history(self, history: list[EpisodeRecord]) -> ReplayBuffer:
        replay_buffer = ReplayBuffer(capacity=SAC_DEFAULTS['replay_capacity'])
        for record in history:
            if not bool((record.summary or {}).get('valid_for_learning', True)):
                continue
            if not record.latest_state_vector or not record.latest_action_vector or record.reward is None or not record.latest_next_state_vector:
                continue
            replay_buffer.append(
                np.asarray(record.latest_state_vector, dtype=np.float64),
                np.asarray(record.latest_action_vector, dtype=np.float64),
                float(record.reward),
                np.asarray(record.latest_next_state_vector, dtype=np.float64),
                True,
            )
        return replay_buffer

    def _sanitize_restored_session(self, session: SessionRuntime, *, restored_from_artifact: str) -> None:
        restorable_state = session.state if session.state in {'session_ready', 'session_paused', 'session_finished', 'error'} else 'session_ready'
        session.state = restorable_state
        session.current_episode_id = ''
        session.current_episode_started_at_ms = 0
        session.candidate_params = {}
        session.episode_base_params = {}
        session.param_echo_confirmed = False
        session.rollback_triggered = False
        session.current_episode_trace = self._empty_episode_trace()
        session.current_episode_trace_started_at_ms = 0
        session.current_episode_last_trace_at_ms = 0
        session.tracked_messages = {}
        session.strategy_mode = self._resolve_strategy_mode(session.strategy_mode)
        session.restored_from_artifact = restored_from_artifact
        if not session.current_params:
            session.current_params = dict(session.safe_params)
        if not session.safe_params:
            session.safe_params = dict(session.current_params)
        if not session.latest_param_echo:
            session.latest_param_echo = dict(session.current_params)
        if not session.latest_state_vector:
            session.latest_state_vector = self._build_runtime_state(session).tolist()
        session.agent_metrics = {
            **self._default_agent_metrics(),
            **dict(session.agent_metrics or {}),
            'mode': SAC_RUNTIME_MODE,
        }

    async def restore_session(self, *, session_id: str = '', artifact_dir: str = '') -> dict:
        if self._session and self._session.state not in {'session_finished', 'error'}:
            return self._response('error', '已有调参会话正在运行', self.get_status())

        resolved_session_id = (session_id or '').strip()
        resolved_artifact_dir = (artifact_dir or '').strip() or self._artifact_logger.build_session_artifact_dir(resolved_session_id)
        if not resolved_artifact_dir or not os.path.exists(resolved_artifact_dir):
            return self._response('error', '未找到可恢复的调参产物目录', {'artifact_dir': resolved_artifact_dir})

        try:
            snapshot = self._artifact_logger.load_session_snapshot(resolved_artifact_dir)
        except FileNotFoundError:
            return self._response('error', '未找到 session_status.json，无法恢复会话', {'artifact_dir': resolved_artifact_dir})

        session_payload = dict(snapshot.get('session') or {})
        history = [
            EpisodeRecord.from_dict(item)
            for item in list(snapshot.get('history') or [])
            if isinstance(item, dict)
        ]
        restored_session = SessionRuntime.from_snapshot(session_payload, history)
        restored_session.artifact_dir = resolved_artifact_dir
        restored_session.session_id = restored_session.session_id or resolved_session_id or os.path.basename(resolved_artifact_dir)
        self._sanitize_restored_session(restored_session, restored_from_artifact=resolved_artifact_dir)

        self._session = restored_session
        self._latest_messages = {}
        self._replay_buffer = self._rebuild_replay_buffer_from_history(restored_session.history)

        state_dim = len(restored_session.latest_state_vector)
        action_dim = len(restored_session.parameter_keys)
        self._sac_agent = self._create_agent(state_dim=state_dim, action_dim=action_dim)

        checkpoint_path = restored_session.checkpoint_path or self._artifact_logger.build_checkpoint_path(restored_session)
        if os.path.exists(checkpoint_path):
            checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
            agent_state = checkpoint.get('agent_state')
            if agent_state:
                self._sac_agent.load_state_dict(agent_state)
            replay_buffer_state = checkpoint.get('replay_buffer')
            if replay_buffer_state:
                self._replay_buffer.load_state_dict(replay_buffer_state)
            restored_session.checkpoint_path = checkpoint_path
            restored_session.checkpoint_updated_at_ms = int(checkpoint.get('timestamp') or restored_session.checkpoint_updated_at_ms or 0)

        restored_session.replay_size = len(self._replay_buffer)
        self._persist_runtime_snapshot(restored_session, event='session_restored')
        await self._broadcast_status()
        return self._response('success', '调参会话已从产物目录恢复', self.get_status())

    def ingest_udp_message(self, message: dict) -> None:
        msg_type = str(message.get('type') or 'unknown')
        self._latest_messages[msg_type] = dict(message)

        if self._session is None:
            return

        self._session.tracked_messages[msg_type] = dict(message)
        if msg_type in TRACE_SAMPLE_MESSAGE_TYPES:
            self._capture_episode_trace_sample(self._session, message)
        if msg_type != 'fcs_param':
            return

        param_echo = self._extract_param_echo(message.get('data') or {})
        self._session.latest_param_echo = param_echo

        if self._matches_candidate(param_echo):
            self._session.param_echo_confirmed = True
            self._session.episode_param_echo_confirmed_once = True
            if self._session.state == 'waiting_param_echo':
                self._transition_session('episode_running')
            self._schedule_broadcast()

    async def start_session(
        self,
        *,
        task_type: str,
        parameter_keys: list[str],
        initial_params: Dict[str, Any],
        max_episodes: int,
        strategy_mode: str,
        session_id: str = '',
    ) -> dict:
        if self._session and self._session.state not in {'session_finished', 'error'}:
            return self._response('error', '已有调参会话正在运行', self.get_status())

        effective_keys = [key for key in parameter_keys if key in self._parameter_specs] or list(DEFAULT_PARAMETER_KEYS)
        resolved_strategy_mode = self._resolve_strategy_mode(strategy_mode)
        tuned_initial_params = {
            key: float(initial_params.get(key, self._resolve_default_pid_value(key)))
            for key in effective_keys
        }
        current_params = self._expand_pid_payload(tuned_initial_params)

        now_ms = int(time.time() * 1000)
        self._session = SessionRuntime(
            session_id=session_id.strip() or f'rl_tuning_{now_ms}',
            task_type=task_type or 'velocity_tracking',
            parameter_keys=effective_keys,
            strategy_mode=resolved_strategy_mode,
            max_episodes=max(1, int(max_episodes or 20)),
            created_at_ms=now_ms,
            state='session_ready',
            current_params=dict(current_params),
            safe_params=dict(current_params),
            artifact_dir=self._artifact_logger.build_session_artifact_dir(session_id.strip() or f'rl_tuning_{now_ms}'),
        )
        self._session.latest_param_echo = dict(current_params)
        self._session.latest_state_vector = self._build_runtime_state(self._session).tolist()
        self._session.agent_metrics = self._default_agent_metrics()
        self._replay_buffer = ReplayBuffer(capacity=SAC_DEFAULTS['replay_capacity'])
        self._sac_agent = self._create_agent(state_dim=len(self._session.latest_state_vector), action_dim=len(effective_keys))
        self._artifact_logger.ensure_session_artifact_layout(self._session)
        self._persist_runtime_snapshot(self._session, event='session_started')
        await self._broadcast_status()
        return self._response('success', '调参会话已创建', self.get_status())

    async def stop_session(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        self._transition_session('session_finished')
        self._persist_runtime_snapshot(session, event='session_finished')
        await self._broadcast_status()
        return self._response('success', '调参会话已结束', session.to_status_dict())

    async def pause_session(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        if session.state == 'episode_running':
            return self._response('error', '任务执行中不允许暂停为可改参状态，请先结束当前任务回合', session.to_status_dict())
        self._transition_session('session_paused')
        self._persist_runtime_snapshot(session, event='session_paused')
        await self._broadcast_status()
        return self._response('success', '调参会话已暂停', session.to_status_dict())

    async def resume_session(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        self._transition_session('session_ready')
        self._persist_runtime_snapshot(session, event='session_resumed')
        await self._broadcast_status()
        return self._response('success', '调参会话已恢复', session.to_status_dict())

    async def start_episode(self, session_id: str, episode_id: str = '') -> dict:
        session = self._require_session(session_id)
        if session.current_episode_index >= session.max_episodes:
            return self._response('error', '已达到最大回合数', session.to_status_dict())
        if session.state not in {'session_ready'}:
            return self._response('error', '当前状态不允许开始新任务回合，必须先处于 session_ready', session.to_status_dict())

        next_episode_index = session.current_episode_index + 1
        next_episode_id = episode_id.strip() or f'episode_{next_episode_index:03d}'

        self._transition_session('episode_preparing')
        tuned_candidate_params = self._propose_candidate_params(session)
        candidate_params = self._expand_pid_payload(tuned_candidate_params)
        session.episode_base_params = dict(session.current_params)
        session.candidate_params = dict(candidate_params)
        session.latest_state_vector = self._build_runtime_state(session).tolist()
        session.param_echo_confirmed = False
        session.episode_param_echo_confirmed_once = False
        session.rollback_triggered = False

        self._transition_session('applying_params')
        send_result = await self._send_pid_params_handler(candidate_params)
        if str(send_result.get('status')) != 'success':
            session.candidate_params = {}
            session.episode_base_params = {}
            session.current_episode_trace = self._empty_episode_trace()
            session.current_episode_trace_started_at_ms = 0
            session.current_episode_last_trace_at_ms = 0
            self._transition_session('error')
            await self._broadcast_status()
            return self._response('error', '候选参数下发失败', {'send_result': send_result, **session.to_status_dict()})

        session.current_episode_index = next_episode_index
        session.current_episode_id = next_episode_id
        session.current_episode_started_at_ms = int(time.time() * 1000)
        session.current_episode_trace = self._empty_episode_trace()
        session.current_episode_trace_started_at_ms = 0
        session.current_episode_last_trace_at_ms = 0

        self._transition_session('waiting_param_echo')
        self._pending_echo_deadline_monotonic = time.monotonic() + PROTECTION_THRESHOLDS['param_echo_timeout_s']
        await self._broadcast_status()
        return self._response('success', '参数已下发，等待回读确认后允许启动任务', {'send_result': send_result, **session.to_status_dict()})

    async def finish_episode(self, session_id: str, episode_id: str, summary: Dict[str, Any], task_success: bool = True) -> dict:
        session = self._require_session(session_id)
        if session.current_episode_id and episode_id and episode_id != session.current_episode_id:
            return self._response('error', '回合编号不匹配', session.to_status_dict())

        if session.state not in {'episode_running', 'waiting_param_echo'}:
            return self._response('error', '当前状态不允许结束回合', session.to_status_dict())

        if session.state == 'waiting_param_echo':
            session.param_echo_confirmed = bool(
                session.episode_param_echo_confirmed_once or self._matches_candidate(session.latest_param_echo)
            )
        else:
            session.param_echo_confirmed = bool(
                session.param_echo_confirmed or session.episode_param_echo_confirmed_once
            )

        self._transition_session('episode_evaluating')
        frontend_summary = dict(summary or {})
        backend_summary = self._build_backend_episode_summary(session, frontend_summary)
        raw_summary = {
            **backend_summary,
            'frontend_summary': frontend_summary,
        }
        if frontend_summary.get('experiment_group') is not None:
            raw_summary['experiment_group'] = frontend_summary.get('experiment_group')
        if frontend_summary.get('recording_context') is not None:
            raw_summary['recording_context'] = frontend_summary.get('recording_context')
        raw_summary['plot_bundle'] = backend_summary.get('plot_bundle') or {}
        normalized_summary = self._artifact_logger.normalize_episode_summary(
            raw_summary,
            task_type=session.task_type,
            target_vx=self._extract_target_vx(backend_summary, session.tracked_messages),
        )
        action_vector = self._normalize_action_vector(session.episode_base_params, session.candidate_params)
        action_norm = float(np.linalg.norm(action_vector) / max(math.sqrt(len(action_vector)), 1.0)) if len(action_vector) else 0.0
        reward, reward_details = build_episode_reward(normalized_summary, action_norm, task_success=task_success)
        normalized_summary = {
            **normalized_summary,
            **reward_details,
        }
        valid_for_learning, invalid_reasons = self._evaluate_learning_sample_quality(
            session,
            normalized_summary,
            task_success=task_success,
        )
        normalized_summary['valid_for_learning'] = valid_for_learning
        normalized_summary['invalid_reasons'] = list(invalid_reasons)
        protection_triggered = bool(reward_details.get('protection_triggered'))
        session.latest_action_vector = action_vector.tolist()
        if valid_for_learning and not protection_triggered and (session.best_reward is None or reward >= session.best_reward):
            session.best_reward = reward
            session.safe_params = dict(session.candidate_params)
            session.current_params = dict(session.candidate_params)
        elif protection_triggered or not valid_for_learning:
            session.rollback_triggered = True
            self._transition_session('rollback_pending')
            rollback_result = await self._send_pid_params_handler(self._expand_pid_payload(session.safe_params))
            if str(rollback_result.get('status')) == 'success':
                session.current_params = dict(session.safe_params)
        else:
            session.current_params = dict(session.candidate_params)

        next_state_vector = build_state_vector(
            tracked_messages=session.tracked_messages,
            summary=normalized_summary,
            current_params=session.current_params,
            task_phase='episode_evaluating',
        )

        record = EpisodeRecord(
            episode_id=session.current_episode_id or episode_id or f'episode_{session.current_episode_index:03d}',
            started_at_ms=session.current_episode_started_at_ms,
            finished_at_ms=int(time.time() * 1000),
            experiment_group=str(normalized_summary.get('experiment_group') or ''),
            target_vx=self._extract_target_vx(normalized_summary, session.tracked_messages),
            base_params=dict(session.episode_base_params),
            candidate_params=dict(session.candidate_params),
            latest_param_echo=dict(session.latest_param_echo),
            param_echo_confirmed=session.param_echo_confirmed,
            reward=reward,
            task_success=task_success,
            protection_triggered=protection_triggered,
            rollback_triggered=session.rollback_triggered,
            latest_state_vector=list(session.latest_state_vector),
            latest_next_state_vector=next_state_vector.tolist(),
            latest_action_vector=list(action_vector.tolist()),
            agent_metrics=dict(session.agent_metrics),
            summary=dict(normalized_summary),
        )
        session.history.append(record)
        session.last_reward = reward
        session.last_summary = dict(record.summary)
        session.latest_next_state_vector = next_state_vector.tolist()

        if valid_for_learning:
            self._replay_buffer.append(
                np.asarray(session.latest_state_vector, dtype=np.float64),
                action_vector,
                reward,
                next_state_vector,
                done=True,
            )
        session.replay_size = len(self._replay_buffer)
        session.agent_metrics = {
            **session.agent_metrics,
            'last_episode_valid_for_learning': valid_for_learning,
            'last_invalid_reasons': list(invalid_reasons),
        }

        if valid_for_learning and self._sac_agent is not None:
            metrics = self._sac_agent.update(self._replay_buffer)
            if metrics:
                session.agent_metrics = {
                    **session.agent_metrics,
                    **metrics,
                    'mode': SAC_RUNTIME_MODE,
                }

        self._transition_session('agent_updating' if session.state != 'rollback_pending' else 'rollback_pending')
        if session.state == 'agent_updating':
            self._transition_session('session_ready')
        else:
            self._transition_session('session_ready')

        session.current_episode_id = ''
        session.current_episode_started_at_ms = 0
        session.candidate_params = {}
        session.episode_base_params = {}
        session.episode_param_echo_confirmed_once = False
        session.latest_state_vector = next_state_vector.tolist()
        session.current_episode_trace = self._empty_episode_trace()
        session.current_episode_trace_started_at_ms = 0
        session.current_episode_last_trace_at_ms = 0
        self._artifact_logger.persist_episode_record(session, record)
        self._persist_runtime_snapshot(session, event='episode_finished')
        await self._broadcast_status()
        return self._response('success', '回合结果已记录', session.to_status_dict())

    async def apply_params(self, params: Dict[str, Any]) -> dict:
        if self._session and self._session.state in {'episode_running', 'episode_evaluating', 'agent_updating', 'waiting_param_echo', 'applying_params', 'episode_preparing'}:
            return self._response(
                'error',
                '当前任务窗口不允许改参。新参数只能在新任务开始前下发并确认生效。',
                self.get_status(),
            )

        filtered = {key: float(value) for key, value in params.items() if key in self._parameter_specs}
        if not filtered:
            return self._response('error', '未提供受支持的参数键', self.get_status())

        base_params = self._session.current_params if self._session else {
            key: float(self._resolve_default_pid_value(key))
            for key in filtered.keys()
        }
        delta_params = {
            key: float(filtered[key]) - float(base_params.get(key, self._parameter_specs[key].default_value))
            for key in filtered.keys()
        }
        candidate = project_candidate_params(base_params, delta_params, {key: self._parameter_specs[key] for key in filtered.keys()})
        expanded_candidate = self._expand_pid_payload(candidate)
        send_result = await self._send_pid_params_handler(expanded_candidate)
        if self._session:
            self._session.candidate_params = dict(expanded_candidate)
            self._session.param_echo_confirmed = False
            self._session.episode_param_echo_confirmed_once = False
        await self._broadcast_status()
        return self._response('success', '参数已发送', {'send_result': send_result, 'candidate_params': expanded_candidate, **self.get_status()})

    async def rollback(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        self._transition_session('rollback_pending')
        result = await self._send_pid_params_handler(self._expand_pid_payload(session.safe_params))
        session.current_params = dict(session.safe_params)
        session.candidate_params = {}
        session.param_echo_confirmed = False
        session.episode_param_echo_confirmed_once = False
        session.rollback_triggered = True
        self._transition_session('session_ready')
        self._persist_runtime_snapshot(session, event='rollback')
        await self._broadcast_status()
        return self._response('success', '已回退到最近安全参数', {'send_result': result, **session.to_status_dict()})

    def get_status(self) -> dict:
        session_status = self._session.to_status_dict() if self._session else {
            'state': 'idle',
            'session_id': '',
            'current_episode_id': '',
            'current_episode_index': 0,
            'parameter_keys': list(DEFAULT_PARAMETER_KEYS),
            'current_params': {},
            'safe_params': {},
            'candidate_params': {},
            'param_echo_confirmed': False,
            'rollback_triggered': False,
            'last_reward': None,
            'best_reward': None,
            'latest_state_vector': [],
            'latest_next_state_vector': [],
            'latest_action_vector': [],
            'agent_metrics': {},
            'replay_size': 0,
            'artifact_dir': '',
            'checkpoint_path': '',
            'checkpoint_updated_at_ms': 0,
            'restored_from_artifact': '',
            'history_size': 0,
        }
        return {
            **session_status,
            'parameter_specs': {key: spec.to_dict() for key, spec in self._parameter_specs.items()},
            'task_start_allowed': bool(
                self._session
                and self._session.state == 'episode_running'
                and self._session.param_echo_confirmed
            ),
            'parameter_update_allowed': bool((self._session is None) or self._session.state in {'session_ready', 'session_paused', 'session_finished', 'error'}),
        }

    def get_history(self, session_id: str) -> dict:
        session = self._require_session(session_id)
        return {
            'session_id': session.session_id,
            'history': [record.to_dict() for record in session.history],
        }

    def _require_session(self, session_id: str) -> SessionRuntime:
        if self._session is None:
            raise ValueError('No active RL tuning session')
        if session_id and self._session.session_id != session_id:
            raise ValueError('RL tuning session id mismatch')
        return self._session

    def _propose_candidate_params(self, session: SessionRuntime) -> Dict[str, float]:
        base_params = session.safe_params if session.safe_params else session.current_params
        scoped_specs = {key: self._parameter_specs[key] for key in session.parameter_keys}
        valid_history_count = self._count_valid_learning_records(session.history)
        has_trained_policy = bool(self._sac_agent is not None and session.agent_metrics.get('actor_loss') is not None)
        if self._sac_agent is None or not has_trained_policy or valid_history_count < int(SAC_DEFAULTS['warmup_pattern_episodes']):
            pattern = DEFAULT_ACTION_PATTERNS[valid_history_count % len(DEFAULT_ACTION_PATTERNS)]
            scoped_pattern = {key: float(pattern.get(key, 0.0)) for key in session.parameter_keys}
            return project_candidate_params(base_params, scoped_pattern, scoped_specs)

        runtime_state = self._build_runtime_state(session)
        deterministic = valid_history_count < int(SAC_DEFAULTS['warmup_pattern_episodes'])
        action, info = self._sac_agent.select_action(runtime_state, deterministic=deterministic)
        delta_params = {
            key: float(action[index]) * float(scoped_specs[key].max_step)
            for index, key in enumerate(session.parameter_keys)
        }
        session.agent_metrics = {
            **session.agent_metrics,
            'policy_mean': info.get('mean', []),
            'policy_std': info.get('std', []),
            'policy_log_prob': info.get('log_prob'),
            'mode': SAC_RUNTIME_MODE,
        }
        return project_candidate_params(base_params, delta_params, scoped_specs)

    def _build_runtime_state(self, session: SessionRuntime) -> np.ndarray:
        return build_state_vector(
            tracked_messages=session.tracked_messages,
            summary=session.last_summary,
            current_params=session.current_params,
            task_phase=session.state,
        )

    def _normalize_action_vector(self, base_params: Dict[str, float], candidate_params: Dict[str, float]) -> np.ndarray:
        values = []
        session_keys = self._session.parameter_keys if self._session else list(DEFAULT_PARAMETER_KEYS)
        for key in session_keys:
            spec = self._parameter_specs[key]
            delta = float(candidate_params.get(key, spec.default_value)) - float(base_params.get(key, spec.default_value))
            values.append(delta / max(spec.max_step, 1e-6))
        return np.asarray(values, dtype=np.float64)

    @staticmethod
    def _count_valid_learning_records(history: list[EpisodeRecord]) -> int:
        count = 0
        for record in history:
            if bool((record.summary or {}).get('valid_for_learning', True)):
                count += 1
        return count

    @staticmethod
    def _is_active_target_value(value: Optional[float]) -> bool:
        return value is not None and math.isfinite(float(value)) and abs(float(value)) >= EPISODE_VALIDATION['min_active_target_abs']

    def _evaluate_learning_sample_quality(
        self,
        session: SessionRuntime,
        summary: Dict[str, Any],
        *,
        task_success: bool,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        trace_sample_count = int(summary.get('trace_sample_count') or 0)
        trace_metric_sample_count = int(summary.get('trace_metric_sample_count') or 0)

        if EPISODE_VALIDATION['require_param_echo_confirmed'] and not session.param_echo_confirmed:
            reasons.append('param_echo_unconfirmed')
        if EPISODE_VALIDATION['require_trace_sync_ready'] and not bool(summary.get('trace_sync_ready')) and trace_sample_count <= 0:
            reasons.append('trace_sync_not_ready')

        if trace_sample_count < int(EPISODE_VALIDATION['min_trace_samples']):
            reasons.append('insufficient_trace_samples')

        if trace_metric_sample_count < int(EPISODE_VALIDATION['min_trace_metric_samples']):
            reasons.append('insufficient_metric_samples')

        target_vx = self._extract_target_vx(summary, session.tracked_messages)
        if target_vx is None:
            reasons.append('target_vx_missing')
        elif not self._is_active_target_value(target_vx):
            reasons.append('target_vx_inactive')

        for key in ('tracking_rmse', 'steady_state_error', 'pwm_jitter'):
            value = summary.get(key)
            if value is None or not math.isfinite(float(value)):
                reasons.append(f'{key}_invalid')

        overshoot = summary.get('overshoot_pct')
        if self._is_active_target_value(target_vx) and (overshoot is None or not math.isfinite(float(overshoot))):
            reasons.append('overshoot_invalid')

        return len(reasons) == 0, reasons

    def _capture_episode_trace_sample(self, session: SessionRuntime, message: dict) -> None:
        if not session.current_episode_id or session.state not in {'episode_running', 'episode_evaluating'}:
            return

        message_ts = int(message.get('timestamp') or time.time() * 1000)
        if session.current_episode_last_trace_at_ms and message_ts - session.current_episode_last_trace_at_ms < TRACE_SAMPLE_MIN_INTERVAL_MS:
            return

        sync_info = self._compute_trace_sync_info(session)
        trace = session.current_episode_trace or self._empty_episode_trace()
        trace['last_packet_skew_ms'] = sync_info['packet_skew_ms']
        trace['sync_ready'] = sync_info['ready']
        trace['missing_types'] = list(sync_info['missing_types'])
        if sync_info['packet_skew_ms'] is not None:
            trace['max_packet_skew_ms_seen'] = max(
                float(trace.get('max_packet_skew_ms_seen') or 0.0),
                float(sync_info['packet_skew_ms']),
            )
        session.current_episode_trace = trace
        if not sync_info['ready']:
            return

        sample = self._build_episode_trace_sample(session)
        if sample is None:
            return

        if session.current_episode_trace_started_at_ms <= 0:
            session.current_episode_trace_started_at_ms = message_ts

        trace['time_s'].append((message_ts - session.current_episode_trace_started_at_ms) / 1000.0)
        for key, value in sample.items():
            trace[key].append(value)
        trace['source_map'] = dict(TRACE_SOURCE_MAP)
        trace['units'] = dict(TRACE_UNITS)
        trace['sample_period_ms'] = TRACE_SAMPLE_MIN_INTERVAL_MS
        trace['sample_count'] = len(trace['time_s'])
        trace['sync_required_types'] = list(TRACE_METADATA_DEFAULTS['sync_required_types'])
        trace['sync_max_skew_ms'] = TRACE_SYNC_MAX_SKEW_MS
        session.current_episode_trace = trace
        session.current_episode_last_trace_at_ms = message_ts

    def _compute_trace_sync_info(self, session: SessionRuntime) -> Dict[str, Any]:
        timestamps: Dict[str, int] = {}
        missing_types = []
        for msg_type in TRACE_SAMPLE_MESSAGE_TYPES:
            message = session.tracked_messages.get(msg_type) or {}
            timestamp = message.get('timestamp')
            if timestamp is None:
                missing_types.append(msg_type)
                continue
            try:
                timestamps[msg_type] = int(timestamp)
            except (TypeError, ValueError):
                missing_types.append(msg_type)

        if missing_types:
            return {
                'ready': False,
                'missing_types': missing_types,
                'packet_skew_ms': None,
            }

        skew_ms = max(timestamps.values()) - min(timestamps.values())
        return {
            'ready': skew_ms <= TRACE_SYNC_MAX_SKEW_MS,
            'missing_types': [],
            'packet_skew_ms': int(skew_ms),
        }

    def _build_episode_trace_sample(self, session: SessionRuntime) -> Optional[Dict[str, Any]]:
        fcs_states = (session.tracked_messages.get('fcs_states') or {}).get('data', {})
        fcs_gncbus = (session.tracked_messages.get('fcs_gncbus') or {}).get('data', {})
        fcs_pwms = (session.tracked_messages.get('fcs_pwms') or {}).get('data', {})
        fcs_datactrl = (session.tracked_messages.get('fcs_datactrl') or {}).get('data', {})

        ele_out = fcs_datactrl.get('eleOutLoop') if isinstance(fcs_datactrl.get('eleOutLoop'), dict) else {}
        ele_in = fcs_datactrl.get('EleInLoop') if isinstance(fcs_datactrl.get('EleInLoop'), dict) else {}

        control_ref_vx = self._pick_float(
            fcs_datactrl,
            'ref_vx',
            default=self._pick_float(
                ele_out,
                'ref_vx',
                default=(
                    float(ele_out.get('Vx_var', 0.0)) + float(ele_out.get('Vx_delta', 0.0))
                    if ele_out.get('Vx_var') is not None or ele_out.get('Vx_delta') is not None
                    else self._pick_float(
                        fcs_datactrl,
                        'dataCtrl_n_eleOutLoop_Vx_dX2Vx',
                        'dataCtrl_n_eleOutLoop_Vx_var',
                        default=None,
                    )
                ),
            ),
        )
        control_est_vx = self._pick_float(
            fcs_datactrl,
            'est_vx',
            default=self._pick_float(
                ele_out,
                'est_vx',
                'Vx_var',
                default=self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_var', default=None),
            ),
        )
        control_pitch = self._pick_float(
            fcs_datactrl,
            'est_theta',
            default=self._pick_float(
                ele_in,
                'est_theta',
                'theta_var',
                default=self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_theta_var', default=None),
            ),
        )

        vx_target = self._pick_float(fcs_gncbus, 'GNCBus_CmdValue_Vx_cmd')
        vx_target_source = 'gncbus_cmd'
        if (vx_target is None or abs(vx_target) <= 1e-6) and control_ref_vx is not None:
            vx_target = control_ref_vx
            vx_target_source = 'datactrl_ref_vx_fallback'

        vx_actual = self._pick_float(fcs_states, 'states_Vx_GS')
        vx_actual_source = 'states_vx_gs'
        if (vx_actual is None or abs(vx_actual) <= 1e-6) and control_est_vx is not None:
            vx_actual = control_est_vx
            vx_actual_source = 'datactrl_est_vx_fallback'

        pitch_actual = self._pick_float(fcs_states, 'states_theta')
        pitch_actual_source = 'states_theta'
        if (pitch_actual is None or abs(pitch_actual) <= 1e-6) and control_pitch is not None:
            pitch_actual = control_pitch
            pitch_actual_source = 'datactrl_est_theta_fallback'

        pitch_rate_q = self._pick_float(fcs_states, 'states_q')
        pwm_values = self._extract_pwm_values(fcs_pwms)
        if vx_target is None or vx_actual is None or pitch_actual is None or not pwm_values:
            return None

        pwm_mean = float(np.mean(pwm_values))
        pwm_std = float(np.std(pwm_values))
        padded_pwm_values = pwm_values[:8] + [0.0] * max(0, 8 - len(pwm_values[:8]))

        return {
            'vx_target': vx_target,
            'vx_actual': vx_actual,
            'vx_error': vx_target - vx_actual,
            'vx_target_source': vx_target_source,
            'vx_actual_source': vx_actual_source,
            'pitch_actual': pitch_actual,
            'pitch_actual_source': pitch_actual_source,
            'pitch_rate_q': pitch_rate_q if pitch_rate_q is not None else 0.0,
            'pwm_mean': pwm_mean,
            'pwm_std': pwm_std,
            'pwm_1': padded_pwm_values[0],
            'pwm_2': padded_pwm_values[1],
            'pwm_3': padded_pwm_values[2],
            'pwm_4': padded_pwm_values[3],
            'pwm_5': padded_pwm_values[4],
            'pwm_6': padded_pwm_values[5],
            'pwm_7': padded_pwm_values[6],
            'pwm_8': padded_pwm_values[7],
            'ctrl_vx_dX2Vx': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_dX2Vx', default=0.0),
            'ctrl_vx_var': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_var', default=self._pick_float(ele_out, 'Vx_var', default=0.0)),
            'ctrl_vx_delta': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_delta', default=self._pick_float(ele_out, 'Vx_delta', default=0.0)),
            'ctrl_vx_p': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_P', default=0.0),
            'ctrl_vx_int': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_Int', default=0.0),
            'ctrl_vx_d': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_Vx_D', default=0.0),
            'ctrl_ele_ffc': self._pick_float(fcs_datactrl, 'dataCtrl_n_eleOutLoop_ele_ffc', default=0.0),
            'ctrl_theta_trim': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_theta_trim', default=self._pick_float(ele_in, 'theta_trim', default=0.0)),
            'ctrl_theta_var': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_theta_var', default=self._pick_float(ele_in, 'theta_var', default=0.0)),
            'ctrl_delta_theta': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_delta_theta', default=self._pick_float(ele_in, 'delta_theta', default=0.0)),
            'ctrl_theta_p': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_theta_P', default=0.0),
            'ctrl_theta_d': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_theta_D', default=0.0),
            'ctrl_ele_fbc': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_ele_fbc', default=0.0),
            'ctrl_ele_law_out': self._pick_float(fcs_datactrl, 'dataCtrl_n_EleInLoop_ele_law_out', default=0.0),
        }

    def _build_episode_plot_bundle(self, session: SessionRuntime) -> Dict[str, Any]:
        trace = dict(session.current_episode_trace or self._empty_episode_trace())
        trace['source_map'] = dict(TRACE_SOURCE_MAP)
        trace['units'] = dict(TRACE_UNITS)
        trace['sample_period_ms'] = TRACE_SAMPLE_MIN_INTERVAL_MS
        trace['sample_count'] = len(trace.get('time_s', []))
        trace['sync_required_types'] = list(TRACE_METADATA_DEFAULTS['sync_required_types'])
        trace['sync_max_skew_ms'] = TRACE_SYNC_MAX_SKEW_MS
        return trace

    def _build_backend_episode_summary(self, session: SessionRuntime, frontend_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        plot_bundle = self._build_episode_plot_bundle(session)
        frontend_summary = dict(frontend_summary or {})

        def numeric_series(key: str) -> list[float]:
            values = plot_bundle.get(key, [])
            if not isinstance(values, list):
                return []
            numbers = []
            for value in values:
                try:
                    numbers.append(float(value))
                except (TypeError, ValueError):
                    continue
            return numbers

        def pair_series(key_a: str, key_b: str) -> list[tuple[float, float]]:
            values_a = numeric_series(key_a)
            values_b = numeric_series(key_b)
            length = min(len(values_a), len(values_b))
            return [(values_a[index], values_b[index]) for index in range(length)]

        def derive_pwm_jitter() -> Optional[float]:
            per_channel_jitters = []
            for channel_index in range(1, 9):
                channel_values = numeric_series(f'pwm_{channel_index}')
                if len(channel_values) < 2:
                    continue
                deltas = [channel_values[index] - channel_values[index - 1] for index in range(1, len(channel_values))]
                if deltas:
                    per_channel_jitters.append(float(np.std(deltas)))

            if per_channel_jitters:
                return float(sum(per_channel_jitters) / len(per_channel_jitters))

            pwm_mean_values = numeric_series('pwm_mean')
            if len(pwm_mean_values) >= 2:
                deltas = [pwm_mean_values[index] - pwm_mean_values[index - 1] for index in range(1, len(pwm_mean_values))]
                if deltas:
                    return float(np.std(deltas))

            pwm_std_values = numeric_series('pwm_std')
            if pwm_std_values:
                return float(sum(abs(value) for value in pwm_std_values) / len(pwm_std_values))

            return None

        def last_meaningful(values: list[float]) -> Optional[float]:
            for value in reversed(values):
                if abs(float(value)) > 1e-6:
                    return float(value)
            return float(values[-1]) if values else None

        tracking_pairs = pair_series('vx_target', 'vx_actual')
        representative_pairs = self._select_representative_tracking_pairs(tracking_pairs)
        representative_target = self._representative_target_value([target for target, _ in representative_pairs])
        tracking_rmse = None
        steady_state_error = None
        overshoot_pct = None
        current_vx = None
        if representative_pairs:
            mse = sum((target - actual) ** 2 for target, actual in representative_pairs) / len(representative_pairs)
            tracking_rmse = float(np.sqrt(max(mse, 0.0)))
            window = max(3, len(representative_pairs) // 5)
            tail_pairs = representative_pairs[-window:]
            steady_state_error = sum(actual - target for target, actual in tail_pairs) / len(tail_pairs)
            current_vx = sum(actual for _, actual in tail_pairs) / len(tail_pairs)
            if representative_target is not None and abs(representative_target) >= TRACE_TARGET_ACTIVE_MIN_ABS:
                response_peak = max(actual for _, actual in representative_pairs)
                if representative_target < 0.0:
                    response_peak = min(actual for _, actual in representative_pairs)
                overshoot_raw = (response_peak - representative_target) / abs(representative_target) * 100.0
                overshoot_pct = max(0.0, overshoot_raw if representative_target > 0.0 else -overshoot_raw)

        pwm_jitter = derive_pwm_jitter()

        vx_target = representative_target or last_meaningful(numeric_series('vx_target'))
        if vx_target is None:
            vx_target = self._extract_target_vx(frontend_summary, session.tracked_messages)
        if current_vx is None:
            current_vx = self._pick_float((session.tracked_messages.get('fcs_states') or {}).get('data', {}), 'states_Vx_GS', default=0.0)

        return {
            'summary_source': 'backend_tracked_messages',
            'tracking_rmse': tracking_rmse,
            'steady_state_error': steady_state_error,
            'overshoot_pct': overshoot_pct,
            'pwm_jitter': pwm_jitter,
            'target_vx': vx_target,
            'current_vx': current_vx,
            'trace_sample_count': len(plot_bundle.get('time_s', [])),
            'trace_metric_sample_count': len(representative_pairs),
            'trace_sync_ready': bool((session.current_episode_trace or {}).get('sync_ready')),
            'trace_missing_types': list((session.current_episode_trace or {}).get('missing_types') or []),
            'plot_bundle': plot_bundle,
        }

    @staticmethod
    def _merge_plot_bundle(base_plot_bundle: Dict[str, Any], recorded_plot_bundle: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base_plot_bundle) if isinstance(base_plot_bundle, dict) else {}
        for key, value in recorded_plot_bundle.items():
            if key in {'source_map', 'units'}:
                existing = merged.get(key)
                merged[key] = {**existing, **value} if isinstance(existing, dict) and isinstance(value, dict) else dict(value)
                continue
            if key == 'sample_period_ms':
                merged[key] = value
                continue
            if key == 'sample_count':
                merged[key] = value
                continue
            if isinstance(value, list) and value:
                merged[key] = list(value)
            elif key not in merged:
                merged[key] = value
        return merged

    @staticmethod
    def _empty_episode_trace() -> Dict[str, Any]:
        trace: Dict[str, Any] = {
            'schema_version': 2,
            'sample_period_ms': TRACE_SAMPLE_MIN_INTERVAL_MS,
            'sample_count': 0,
            'source_map': dict(TRACE_SOURCE_MAP),
            'units': dict(TRACE_UNITS),
            'sync_required_types': list(TRACE_METADATA_DEFAULTS['sync_required_types']),
            'sync_max_skew_ms': TRACE_SYNC_MAX_SKEW_MS,
            'sync_ready': False,
            'missing_types': list(TRACE_SAMPLE_MESSAGE_TYPES),
            'last_packet_skew_ms': None,
            'max_packet_skew_ms_seen': 0.0,
        }
        for key in TRACE_SOURCE_MAP.keys():
            trace[key] = []
        trace['time_s'] = []
        return trace

    @staticmethod
    def _pick_float(container: Dict[str, Any], *keys: str, default: Optional[float] = None) -> Optional[float]:
        for key in keys:
            value = container.get(key) if isinstance(container, dict) else None
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return default

    @staticmethod
    def _extract_pwm_values(container: Any) -> list[float]:
        raw_values = []
        if isinstance(container, dict):
            raw_values = container.get('pwms') or []
        elif isinstance(container, list):
            raw_values = container

        pwm_values = []
        for value in raw_values[:8]:
            try:
                pwm_values.append(float(value))
            except (TypeError, ValueError):
                continue
        return pwm_values

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
        target_ref = PIDTuningService._representative_target_value([target for target, _ in base_pairs])
        if target_ref is None:
            return base_pairs

        band = max(TRACE_TARGET_PLATEAU_ABS_BAND, abs(target_ref) * TRACE_TARGET_PLATEAU_REL_BAND)
        plateau_pairs = [pair for pair in base_pairs if abs(pair[0] - target_ref) <= band]
        return plateau_pairs or base_pairs

    @staticmethod
    def _extract_target_vx(summary: Dict[str, Any], tracked_messages: Dict[str, dict]) -> Optional[float]:
        def active_or_none(value: Any) -> Optional[float]:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                return None
            if abs(numeric_value) < EPISODE_VALIDATION['min_active_target_abs']:
                return None
            return numeric_value

        plot_bundle = summary.get('plot_bundle') if isinstance(summary.get('plot_bundle'), dict) else {}
        trace_target = PIDTuningService._representative_target_value(plot_bundle.get('vx_target', []))
        if active_or_none(trace_target) is not None:
            return trace_target

        gncbus_data = (tracked_messages.get('fcs_gncbus') or {}).get('data', {})
        gncbus_target = active_or_none(gncbus_data.get('GNCBus_CmdValue_Vx_cmd'))
        if gncbus_target is not None:
            return gncbus_target

        summary_candidates = (
            summary.get('target_vx'),
            summary.get('vx_cmd'),
            summary.get('command_vx'),
        )
        for value in summary_candidates:
            active_value = active_or_none(value)
            if active_value is not None:
                return active_value
        return None

    def _extract_param_echo(self, raw_data: Dict[str, Any]) -> Dict[str, float]:
        echo: Dict[str, float] = {}
        for key, spec in self._parameter_specs.items():
            value = raw_data.get(spec.echo_key, raw_data.get(key, self._cached_pid_params.get(key, spec.default_value)))
            try:
                echo[key] = float(value)
            except (TypeError, ValueError):
                echo[key] = float(self._cached_pid_params.get(key, spec.default_value))
        return echo

    def _matches_candidate(self, param_echo: Dict[str, float]) -> bool:
        if self._session is None or not self._session.candidate_params:
            return False

        compared_keys = list(self._session.parameter_keys or [])
        if not compared_keys:
            compared_keys = list(self._session.candidate_params.keys())

        for key in compared_keys:
            if key not in self._session.candidate_params:
                continue
            candidate_value = self._session.candidate_params[key]
            echo_value = float(param_echo.get(key, 0.0))
            if abs(echo_value - float(candidate_value)) > 1e-2:
                return False
        return True

    def _transition_session(self, next_state: str) -> None:
        if self._session is None:
            return
        ensure_transition(self._session.state, next_state)
        self._session.state = next_state

    def _schedule_broadcast(self) -> None:
        if self._broadcast_handler is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._broadcast_status())

    async def _broadcast_status(self) -> None:
        if self._broadcast_handler is None:
            return
        await self._broadcast_handler({
            'type': 'rl_tuning_status',
            'data': self.get_status(),
            'timestamp': int(time.time() * 1000),
        })

    @staticmethod
    def _response(status: str, message: str, data: dict) -> dict:
        return {
            'type': 'rl_tuning_response',
            'status': status,
            'message': message,
            'data': data,
            'timestamp': int(time.time() * 1000),
        }