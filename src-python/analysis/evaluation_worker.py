from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from experiment.architecture_config_loader import ArchitectureConfigBundle, AllocationProfile


CONTRACT_VERSION = 'v1.0'


@dataclass
class EvaluationRunResult:
    success: bool
    status: str
    session_dir: str
    output_path: str
    canonical_report_path: str
    summary: dict[str, Any]
    baseline_allocation_id: str = ''
    candidate_allocation_id: str = ''
    error: str = ''
    error_code: str = ''
    request_id: str = ''
    contract_version: str = CONTRACT_VERSION
    session_id: str = ''
    worker_name: str = 'evaluation_worker'
    worker_status: str = 'waiting'
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    artifact_paths: Optional[dict[str, str]] = None
    summary_payload_type: str = 'evaluation_summary_update'
    summary_payload_path: str = ''

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['artifact_paths'] = dict(self.artifact_paths or {})
        return payload


class SessionEvaluationWorker:
    def __init__(self, thesis_workspace: Optional[str | Path] = None):
        self.thesis_workspace = Path(
            thesis_workspace or os.getenv('THESIS_WS_PATH') or 'E:/DataAnalysis/thesis_ws'
        )

    def run_for_session(
        self,
        session_dir: str | Path,
        architecture_bundle: Optional[ArchitectureConfigBundle],
        *,
        session_meta: Optional[dict[str, Any]] = None,
        baseline_profile_id: Optional[str] = None,
        candidate_profile_id: Optional[str] = None,
        trigger_source: str = 'apollo_backend',
    ) -> EvaluationRunResult:
        session_path = Path(session_dir)
        analysis_dir = session_path / 'analysis'
        analysis_dir.mkdir(parents=True, exist_ok=True)
        canonical_report_path = analysis_dir / 'evaluation_result.json'
        request_id = str(uuid.uuid4())
        started_at = time.time()
        loaded_session_meta = session_meta or self._load_session_meta(session_path)
        session_id = str((loaded_session_meta or {}).get('session_id') or session_path.name)
        figure_context = self._extract_figure_context(loaded_session_meta)

        if not session_path.exists():
            return self._build_failure(
                session_path,
                canonical_report_path,
                request_id,
                session_id,
                started_at,
                'EVAL_SESSION_MISSING',
                f'会话目录不存在: {session_path}',
            )

        if architecture_bundle is None:
            return self._build_failure(
                session_path,
                canonical_report_path,
                request_id,
                session_id,
                started_at,
                'ARCH_CONFIG_MISSING',
                '架构配置包未加载，无法执行评估',
            )

        dsm_report_path = session_path / 'analysis' / 'dsm_report.json'
        if not dsm_report_path.exists():
            return self._build_failure(
                session_path,
                canonical_report_path,
                request_id,
                session_id,
                started_at,
                'EVAL_DSM_MISSING',
                f'DSM 报告不存在: {dsm_report_path}',
            )

        baseline_profile = self._resolve_baseline_profile(architecture_bundle, baseline_profile_id)
        if baseline_profile is None:
            return self._build_failure(
                session_path,
                canonical_report_path,
                request_id,
                session_id,
                started_at,
                'ARCH_BASELINE_PROFILE_MISSING',
                '未找到 baseline allocation profile，无法执行评估',
            )

        candidate_profile = self._resolve_candidate_profile(
            architecture_bundle,
            loaded_session_meta,
            explicit_profile_id=candidate_profile_id,
        )
        if candidate_profile is None:
            requested_profile = self._extract_requested_profile_id(loaded_session_meta, candidate_profile_id)
            return self._build_failure(
                session_path,
                canonical_report_path,
                request_id,
                session_id,
                started_at,
                'ARCH_PROFILE_UNRESOLVED',
                f'无法解析候选架构 profile: {requested_profile or "<empty>"}',
                baseline_profile_id=baseline_profile.profile_id,
            )

        try:
            evaluator_cls = self._load_evaluator()
            hardware_specs = self._build_hardware_specs(architecture_bundle)
            with dsm_report_path.open('r', encoding='utf-8') as handle:
                dsm_report = json.load(handle)

            evaluator = evaluator_cls(dsm_report, hardware_specs)
            candidate_result = evaluator.evaluate_architecture(candidate_profile.assignments)
            baseline_result = evaluator.evaluate_architecture(baseline_profile.assignments)
            summary = self._build_summary(
                session_id=session_id,
                baseline_profile=baseline_profile,
                candidate_profile=candidate_profile,
                candidate_result=candidate_result,
                baseline_result=baseline_result,
                figure_context=figure_context,
            )
            finished_at = time.time()
            payload = {
                'request_id': request_id,
                'contract_version': CONTRACT_VERSION,
                'session_id': session_id,
                'worker_name': 'evaluation_worker',
                'worker_status': 'ready',
                'started_at': started_at,
                'finished_at': finished_at,
                'artifact_paths': {
                    'dsm_report': str(dsm_report_path),
                    'evaluation_result': str(canonical_report_path),
                },
                'summary_payload_type': 'evaluation_summary_update',
                'summary_payload_path': str(canonical_report_path),
                'trigger_source': trigger_source,
                'baseline_allocation_id': baseline_profile.profile_id,
                'candidate_allocation_id': candidate_profile.profile_id,
                'figure_context': figure_context,
                'summary': summary,
                'evaluation_result': candidate_result,
                'baseline_result': baseline_result,
                'error_code': '',
                'error_message': '',
            }
            with canonical_report_path.open('w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

            return EvaluationRunResult(
                success=True,
                status='ready',
                session_dir=str(session_path),
                output_path=str(canonical_report_path),
                canonical_report_path=str(canonical_report_path),
                summary=summary,
                baseline_allocation_id=baseline_profile.profile_id,
                candidate_allocation_id=candidate_profile.profile_id,
                request_id=request_id,
                session_id=session_id,
                worker_status='ready',
                started_at=started_at,
                finished_at=finished_at,
                artifact_paths=payload['artifact_paths'],
                summary_payload_path=str(canonical_report_path),
            )
        except Exception as exc:
            return self._build_failure(
                session_path,
                canonical_report_path,
                request_id,
                session_id,
                started_at,
                'EVAL_RUNTIME_ERROR',
                str(exc),
                baseline_profile_id=baseline_profile.profile_id,
                candidate_profile_id=candidate_profile.profile_id,
            )

    def _build_failure(
        self,
        session_path: Path,
        canonical_report_path: Path,
        request_id: str,
        session_id: str,
        started_at: float,
        error_code: str,
        error_message: str,
        *,
        baseline_profile_id: str = '',
        candidate_profile_id: str = '',
    ) -> EvaluationRunResult:
        finished_at = time.time()
        return EvaluationRunResult(
            success=False,
            status='failed',
            session_dir=str(session_path),
            output_path='',
            canonical_report_path=str(canonical_report_path),
            summary={},
            baseline_allocation_id=baseline_profile_id,
            candidate_allocation_id=candidate_profile_id,
            error=error_message,
            error_code=error_code,
            request_id=request_id,
            session_id=session_id,
            worker_status='failed',
            started_at=started_at,
            finished_at=finished_at,
            artifact_paths={'evaluation_result': str(canonical_report_path)},
            summary_payload_path=str(canonical_report_path),
        )

    def _load_evaluator(self):
        if not self.thesis_workspace.exists():
            raise FileNotFoundError(f'thesis_ws 不存在: {self.thesis_workspace}')

        thesis_path = str(self.thesis_workspace)
        if thesis_path not in sys.path:
            sys.path.insert(0, thesis_path)

        from data_processing.dsm.evaluation_model import ArchitectureEvaluator  # type: ignore

        return ArchitectureEvaluator

    def _build_hardware_specs(self, architecture_bundle: ArchitectureConfigBundle) -> dict[str, dict[str, Any]]:
        return {
            resource.hardware_id: {
                'type': resource.type,
                'compute_type': resource.compute_type,
                'mips': resource.mips,
                'bandwidth_mbps': resource.bandwidth_mbps,
                'safety_level': resource.safety_level,
                'power_idle_w': resource.power_idle_w,
                'power_full_w': resource.power_full_w,
                'description': resource.description,
            }
            for resource in architecture_bundle.hardware_resources.values()
        }

    def _resolve_baseline_profile(
        self,
        architecture_bundle: ArchitectureConfigBundle,
        requested_profile_id: Optional[str],
    ) -> Optional[AllocationProfile]:
        exact = self._resolve_profile_by_id(architecture_bundle, requested_profile_id)
        if exact is not None:
            return exact
        for profile in architecture_bundle.list_profiles(include_research=True):
            if profile.profile_group == 'baseline':
                return profile
        return None

    def _resolve_candidate_profile(
        self,
        architecture_bundle: ArchitectureConfigBundle,
        session_meta: Optional[dict[str, Any]],
        *,
        explicit_profile_id: Optional[str],
    ) -> Optional[AllocationProfile]:
        requested_id = self._extract_requested_profile_id(session_meta, explicit_profile_id)
        return self._resolve_profile_by_id(architecture_bundle, requested_id)

    def _extract_requested_profile_id(
        self,
        session_meta: Optional[dict[str, Any]],
        explicit_profile_id: Optional[str],
    ) -> str:
        runtime_architecture = (session_meta or {}).get('runtime_architecture', {}) or {}
        planned_case = (session_meta or {}).get('planned_case', {}) or {}
        candidates = [
            explicit_profile_id,
            (session_meta or {}).get('canonical_profile_id'),
            (session_meta or {}).get('mapping_profile'),
            runtime_architecture.get('profile_id'),
            runtime_architecture.get('canonical_profile_id'),
            runtime_architecture.get('mapping_profile'),
            planned_case.get('canonical_profile_id'),
            planned_case.get('mapping_profile'),
            (session_meta or {}).get('architecture_id'),
            runtime_architecture.get('architecture_id'),
            planned_case.get('architecture_id'),
        ]
        for value in candidates:
            if value:
                return str(value).strip()
        return ''

    def _resolve_profile_by_id(
        self,
        architecture_bundle: ArchitectureConfigBundle,
        requested_profile_id: Optional[str],
    ) -> Optional[AllocationProfile]:
        return architecture_bundle.resolve_allocation_profile(requested_profile_id)

    def _load_session_meta(self, session_path: Path) -> dict[str, Any]:
        meta_path = session_path / 'session_meta.json'
        if not meta_path.exists():
            return {}
        with meta_path.open('r', encoding='utf-8') as handle:
            return json.load(handle)

    def _extract_figure_context(self, session_meta: Optional[dict[str, Any]]) -> dict[str, Any]:
        meta = session_meta or {}
        figure_context: dict[str, Any] = {}
        for key in [
            'figure_run_id',
            'figure_batch_id',
            'figure_batch_group',
            'figure_ledger_range',
            'experiment_type',
            'chapter_target',
            'law_validation_scope',
            'analysis_run_id',
            'figure_asset_status',
            'figure_asset_ready',
            'figure_batch_manifest_path',
        ]:
            value = meta.get(key)
            if value is not None and value != '':
                figure_context[key] = value
        return figure_context

    def _build_summary(
        self,
        *,
        session_id: str,
        baseline_profile: AllocationProfile,
        candidate_profile: AllocationProfile,
        candidate_result: dict[str, Any],
        baseline_result: dict[str, Any],
        figure_context: dict[str, Any],
    ) -> dict[str, Any]:
        final_score = self._safe_number(candidate_result.get('Final_Composite_Score'))
        baseline_score = self._safe_number(baseline_result.get('Final_Composite_Score'))
        return {
            'session_id': session_id,
            'baseline_allocation_id': baseline_profile.profile_id,
            'candidate_allocation_id': candidate_profile.profile_id,
            'baseline_architecture_id': baseline_profile.profile_id,
            'candidate_architecture_ids': [candidate_profile.profile_id],
            **figure_context,
            'final_composite_score': final_score,
            'constraint_violation_count': int(self._safe_number(candidate_result.get('Constraint_Violations_Count'), 0)),
            'domain_scores': {
                'perception': {
                    'perception_latency_ms': self._safe_number(candidate_result.get('Ind_Perception_Latency')),
                    'perception_cpu_load': self._safe_number(candidate_result.get('Ind_Perception_CPU_Load')),
                    'obstacle_count': self._safe_number(candidate_result.get('Ind_Obstacle_Count')),
                },
                'decision': {
                    'planning_time_ms': self._safe_number(candidate_result.get('Ind_Planning_Time')),
                    'tracking_rmse': self._safe_number(candidate_result.get('Ind_Tracking_RMSE')),
                    'avoid_success_rate': self._safe_number(candidate_result.get('Ind_Avoid_Success')),
                },
                'control': {
                    'control_jitter_ms': self._safe_number(candidate_result.get('Ind_Control_Jitter')),
                    'attitude_overshoot_pct': self._safe_number(candidate_result.get('Ind_Attitude_Overshoot')),
                    'motor_response_ms': self._safe_number(candidate_result.get('Ind_Motor_Response')),
                },
                'communication': {
                    'downlink_loss_rate': self._safe_number(candidate_result.get('Ind_Downlink_Loss')),
                    'uplink_delay_ms': self._safe_number(candidate_result.get('Ind_Uplink_Delay')),
                    'cross_latency_ms': self._safe_number(candidate_result.get('Ind_Cross_Latency')),
                    'bus_bandwidth_util': self._safe_number(candidate_result.get('Ind_Bus_Bandwidth')),
                },
                'safety': {
                    'dal_compliance': self._safe_number(candidate_result.get('Ind_DAL_Compliance')),
                    'system_power_w': self._safe_number(candidate_result.get('Ind_System_Power')),
                    'resource_margin': self._safe_number(candidate_result.get('Ind_Resource_Margin')),
                    'mission_reliability': self._safe_number(candidate_result.get('Ind_Mission_Reliability')),
                },
            },
            'baseline_delta': {
                'final_composite_score': round(final_score - baseline_score, 6),
                'constraint_violation_count': int(self._safe_number(candidate_result.get('Constraint_Violations_Count'), 0)) - int(self._safe_number(baseline_result.get('Constraint_Violations_Count'), 0)),
                'cross_count': int(self._safe_number(candidate_result.get('Metric_Cross_Count'), 0)) - int(self._safe_number(baseline_result.get('Metric_Cross_Count'), 0)),
                'system_power_w': round(
                    self._safe_number(candidate_result.get('Ind_System_Power')) - self._safe_number(baseline_result.get('Ind_System_Power')),
                    6,
                ),
            },
            'evaluation_ready': True,
        }

    def _safe_number(self, value: Any, default: float = 0.0) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        if numeric != numeric:
            return default
        return numeric