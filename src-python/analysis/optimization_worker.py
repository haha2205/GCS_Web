from __future__ import annotations

import csv
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
class OptimizationRunResult:
    success: bool
    status: str
    session_dir: str
    output_path: str
    canonical_report_path: str
    summary: dict[str, Any]
    baseline_allocation_id: str = ''
    current_allocation_id: str = ''
    recommended_allocation_id: str = ''
    error: str = ''
    error_code: str = ''
    request_id: str = ''
    contract_version: str = CONTRACT_VERSION
    session_id: str = ''
    worker_name: str = 'optimization_worker'
    worker_status: str = 'waiting'
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    artifact_paths: Optional[dict[str, str]] = None
    summary_payload_type: str = 'architecture_recommendation_update'
    summary_payload_path: str = ''

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['artifact_paths'] = dict(self.artifact_paths or {})
        return payload


class SessionOptimizationWorker:
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
        current_profile_id: Optional[str] = None,
        pop_size: int = 40,
        n_gen: int = 40,
        seed: int = 42,
        trigger_source: str = 'apollo_backend',
    ) -> OptimizationRunResult:
        session_path = Path(session_dir)
        analysis_dir = session_path / 'analysis'
        analysis_dir.mkdir(parents=True, exist_ok=True)
        canonical_report_path = analysis_dir / 'optimization_result.json'
        request_id = str(uuid.uuid4())
        started_at = time.time()
        loaded_session_meta = session_meta or self._load_session_meta(session_path)
        session_id = str((loaded_session_meta or {}).get('session_id') or session_path.name)
        figure_context = self._extract_figure_context(loaded_session_meta)

        if not session_path.exists():
            return self._build_failure(session_path, canonical_report_path, request_id, session_id, started_at, 'OPT_SESSION_MISSING', f'会话目录不存在: {session_path}')
        if architecture_bundle is None:
            return self._build_failure(session_path, canonical_report_path, request_id, session_id, started_at, 'ARCH_CONFIG_MISSING', '架构配置包未加载，无法执行优化')

        dsm_report_path = session_path / 'analysis' / 'dsm_report.json'
        evaluation_result_path = session_path / 'analysis' / 'evaluation_result.json'
        if not dsm_report_path.exists():
            return self._build_failure(session_path, canonical_report_path, request_id, session_id, started_at, 'OPT_DSM_MISSING', f'DSM 报告不存在: {dsm_report_path}')
        if not evaluation_result_path.exists():
            return self._build_failure(session_path, canonical_report_path, request_id, session_id, started_at, 'OPT_EVAL_MISSING', f'Evaluation 结果不存在: {evaluation_result_path}')

        baseline_profile = self._resolve_baseline_profile(architecture_bundle, baseline_profile_id)
        if baseline_profile is None:
            return self._build_failure(session_path, canonical_report_path, request_id, session_id, started_at, 'ARCH_BASELINE_PROFILE_MISSING', '未找到 baseline allocation profile，无法执行优化')

        current_profile = self._resolve_current_profile(architecture_bundle, loaded_session_meta, explicit_profile_id=current_profile_id) or baseline_profile

        try:
            run_nsga2 = self._load_optimizer()
            output_path = Path(
                run_nsga2(
                    str(dsm_report_path),
                    self._build_hardware_specs(architecture_bundle),
                    pop_size=pop_size,
                    n_gen=n_gen,
                    seed=seed,
                    baseline_allocation=baseline_profile.assignments,
                )
            )
            candidate_summaries = self._load_candidate_summaries(output_path, architecture_bundle)
            evaluation_payload = self._load_json_if_exists(evaluation_result_path)
            evaluation_summary = (evaluation_payload or {}).get('summary', {}) or {}
            recommended_candidate = self._select_recommended_candidate(candidate_summaries)
            comparison_path = analysis_dir / 'optimization_comparison.json'
            comparison_payload = self._build_comparison_payload(
                session_id=session_id,
                baseline_profile=baseline_profile,
                current_profile=current_profile,
                evaluation_summary=evaluation_summary,
                recommended_candidate=recommended_candidate,
                candidate_summaries=candidate_summaries,
                figure_context=figure_context,
            )
            with comparison_path.open('w', encoding='utf-8') as handle:
                json.dump(comparison_payload, handle, ensure_ascii=False, indent=2)
            summary = self._build_summary(
                session_id=session_id,
                baseline_profile=baseline_profile,
                current_profile=current_profile,
                evaluation_summary=evaluation_summary,
                recommended_candidate=recommended_candidate,
                candidate_summaries=candidate_summaries,
                comparison=self._load_json_if_exists(comparison_path),
                figure_context=figure_context,
            )
            finished_at = time.time()
            payload = {
                'request_id': request_id,
                'contract_version': CONTRACT_VERSION,
                'session_id': session_id,
                'worker_name': 'optimization_worker',
                'worker_status': 'ready',
                'started_at': started_at,
                'finished_at': finished_at,
                'artifact_paths': {
                    'dsm_report': str(dsm_report_path),
                    'evaluation_result': str(evaluation_result_path),
                    'pareto_front': str(output_path),
                    'optimization_comparison': str(comparison_path),
                    'optimization_result': str(canonical_report_path),
                },
                'summary_payload_type': 'architecture_recommendation_update',
                'summary_payload_path': str(canonical_report_path),
                'trigger_source': trigger_source,
                'baseline_allocation_id': baseline_profile.profile_id,
                'current_allocation_id': current_profile.profile_id,
                'recommended_allocation_id': summary.get('recommended_architecture', {}).get('profile_id', ''),
                'figure_context': figure_context,
                'summary': summary,
                'error_code': '',
                'error_message': '',
            }
            with canonical_report_path.open('w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)

            return OptimizationRunResult(
                success=True,
                status='ready',
                session_dir=str(session_path),
                output_path=str(output_path),
                canonical_report_path=str(canonical_report_path),
                summary=summary,
                baseline_allocation_id=baseline_profile.profile_id,
                current_allocation_id=current_profile.profile_id,
                recommended_allocation_id=summary.get('recommended_architecture', {}).get('profile_id', ''),
                request_id=request_id,
                session_id=session_id,
                worker_status='ready',
                started_at=started_at,
                finished_at=finished_at,
                artifact_paths=payload['artifact_paths'],
                summary_payload_path=str(canonical_report_path),
            )
        except Exception as exc:
            return self._build_failure(session_path, canonical_report_path, request_id, session_id, started_at, 'OPT_RUNTIME_ERROR', str(exc), baseline_profile_id=baseline_profile.profile_id, current_profile_id=current_profile.profile_id)

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
        current_profile_id: str = '',
    ) -> OptimizationRunResult:
        finished_at = time.time()
        return OptimizationRunResult(
            success=False,
            status='failed',
            session_dir=str(session_path),
            output_path='',
            canonical_report_path=str(canonical_report_path),
            summary={},
            baseline_allocation_id=baseline_profile_id,
            current_allocation_id=current_profile_id,
            error=error_message,
            error_code=error_code,
            request_id=request_id,
            session_id=session_id,
            worker_status='failed',
            started_at=started_at,
            finished_at=finished_at,
            artifact_paths={'optimization_result': str(canonical_report_path)},
            summary_payload_path=str(canonical_report_path),
        )

    def _load_optimizer(self):
        if not self.thesis_workspace.exists():
            raise FileNotFoundError(f'thesis_ws 不存在: {self.thesis_workspace}')

        thesis_path = str(self.thesis_workspace)
        if thesis_path not in sys.path:
            sys.path.insert(0, thesis_path)

        from data_processing.optimization import run_nsga2  # type: ignore

        return run_nsga2

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

    def _resolve_baseline_profile(self, architecture_bundle: ArchitectureConfigBundle, requested_profile_id: Optional[str]) -> Optional[AllocationProfile]:
        exact = architecture_bundle.resolve_allocation_profile(requested_profile_id)
        if exact is not None:
            return exact
        for profile in architecture_bundle.list_profiles(include_research=True):
            if profile.profile_group == 'baseline':
                return profile
        return None

    def _resolve_current_profile(
        self,
        architecture_bundle: ArchitectureConfigBundle,
        session_meta: Optional[dict[str, Any]],
        *,
        explicit_profile_id: Optional[str],
    ) -> Optional[AllocationProfile]:
        runtime_architecture = (session_meta or {}).get('runtime_architecture', {}) or {}
        planned_case = (session_meta or {}).get('planned_case', {}) or {}
        for value in [
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
        ]:
            profile = architecture_bundle.resolve_allocation_profile(value)
            if profile is not None:
                return profile
        return None

    def _load_candidate_summaries(self, pareto_front_path: Path, architecture_bundle: ArchitectureConfigBundle) -> list[dict[str, Any]]:
        if not pareto_front_path.exists():
            return []

        candidate_summaries: list[dict[str, Any]] = []
        with pareto_front_path.open('r', encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                allocation = self._parse_allocation(row.get('allocation', ''))
                matched_profile = architecture_bundle.find_profile_by_assignments(allocation)
                score = self._safe_float(row.get('score'))
                candidate_summaries.append({
                    'solution_id': int(self._safe_float(row.get('solution_id'))),
                    'solution_type': row.get('solution_type', 'Balanced'),
                    'profile_id': matched_profile.profile_id if matched_profile else '',
                    'profile_name': matched_profile.profile_name if matched_profile else row.get('solution_type', 'Candidate'),
                    'score': score,
                    'cross_count': int(self._safe_float(row.get('cross_count'))),
                    'power_w': self._safe_float(row.get('power_w')),
                    'cpu_margin': self._safe_float(row.get('cpu_margin')),
                    'nav_rmse': self._safe_float(row.get('nav_rmse')),
                    'jitter_ms': self._safe_float(row.get('jitter_ms')),
                    'safety_score': self._safe_float(row.get('safety_score')),
                    'arch_type': row.get('arch_type', ''),
                    'constraint_pass': score > 0,
                    'allocation': allocation,
                })
        return candidate_summaries

    def _select_recommended_candidate(self, candidate_summaries: list[dict[str, Any]]) -> dict[str, Any]:
        valid = [item for item in candidate_summaries if item.get('constraint_pass')]
        if not valid:
            return candidate_summaries[0] if candidate_summaries else {}

        balanced = [item for item in valid if item.get('solution_type') == 'Balanced']
        pool = balanced or valid
        return max(pool, key=lambda item: (item.get('score', 0.0), -item.get('power_w', 0.0)))

    def _build_summary(
        self,
        *,
        session_id: str,
        baseline_profile: AllocationProfile,
        current_profile: AllocationProfile,
        evaluation_summary: dict[str, Any],
        recommended_candidate: dict[str, Any],
        candidate_summaries: list[dict[str, Any]],
        comparison: dict[str, Any],
        figure_context: dict[str, Any],
    ) -> dict[str, Any]:
        current_score = self._safe_float(evaluation_summary.get('final_composite_score'))
        current_cross = int(self._safe_float((evaluation_summary.get('baseline_delta') or {}).get('cross_count'), 0))
        current_power = self._safe_float((evaluation_summary.get('domain_scores') or {}).get('safety', {}).get('system_power_w'))
        return {
            'session_id': session_id,
            'baseline_allocation_id': baseline_profile.profile_id,
            'baseline_architecture_id': baseline_profile.profile_id,
            'candidate_architecture_ids': [item.get('profile_id') for item in candidate_summaries if item.get('profile_id')],
            **figure_context,
            'current_architecture': {
                'profile_id': current_profile.profile_id,
                'profile_name': current_profile.profile_name,
                'score': current_score,
                'cross_count': current_cross,
                'power_w': current_power,
                'constraint_pass': True,
            },
            'recommended_architecture': {
                'profile_id': recommended_candidate.get('profile_id', ''),
                'profile_name': recommended_candidate.get('profile_name', ''),
                'solution_type': recommended_candidate.get('solution_type', ''),
                'score': recommended_candidate.get('score'),
                'cross_count': recommended_candidate.get('cross_count'),
                'power_w': recommended_candidate.get('power_w'),
                'constraint_pass': recommended_candidate.get('constraint_pass', False),
            },
            'all_candidate_summaries': candidate_summaries,
            'predicted_score_delta': round(self._safe_float(recommended_candidate.get('score')) - current_score, 6),
            'predicted_cross_count_delta': int(self._safe_float(recommended_candidate.get('cross_count')) - current_cross),
            'predicted_power_delta': round(self._safe_float(recommended_candidate.get('power_w')) - current_power, 6),
            'constraint_pass': bool(recommended_candidate.get('constraint_pass', False)),
            'comparison': comparison,
            'optimization_ready': True,
        }

    def _build_comparison_payload(
        self,
        *,
        session_id: str,
        baseline_profile: AllocationProfile,
        current_profile: AllocationProfile,
        evaluation_summary: dict[str, Any],
        recommended_candidate: dict[str, Any],
        candidate_summaries: list[dict[str, Any]],
        figure_context: dict[str, Any],
    ) -> dict[str, Any]:
        current_score = self._safe_float(evaluation_summary.get('final_composite_score'))
        current_cross = int(self._safe_float((evaluation_summary.get('baseline_delta') or {}).get('cross_count'), 0))
        current_power = self._safe_float((evaluation_summary.get('domain_scores') or {}).get('safety', {}).get('system_power_w'))
        return {
            'session_id': session_id,
            'baseline_architecture_id': baseline_profile.profile_id,
            'current_architecture_id': current_profile.profile_id,
            'recommended_architecture_id': recommended_candidate.get('profile_id', ''),
            'candidate_architecture_ids': [item.get('profile_id') for item in candidate_summaries if item.get('profile_id')],
            **figure_context,
            'current_architecture': {
                'profile_id': current_profile.profile_id,
                'profile_name': current_profile.profile_name,
                'score': current_score,
                'cross_count': current_cross,
                'power_w': current_power,
            },
            'recommended_architecture': recommended_candidate,
            'predicted_score_delta': round(self._safe_float(recommended_candidate.get('score')) - current_score, 6),
            'predicted_cross_count_delta': int(self._safe_float(recommended_candidate.get('cross_count')) - current_cross),
            'predicted_power_delta': round(self._safe_float(recommended_candidate.get('power_w')) - current_power, 6),
            'constraint_pass': bool(recommended_candidate.get('constraint_pass', False)),
            'all_candidate_summaries': candidate_summaries,
            'generated_at': time.time(),
        }

    def _load_json_if_exists(self, file_path: Path) -> dict[str, Any]:
        if not file_path.exists():
            return {}
        with file_path.open('r', encoding='utf-8') as handle:
            return json.load(handle)

    def _parse_allocation(self, raw_value: str) -> dict[str, str]:
        try:
            payload = json.loads(raw_value or '{}')
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items() if key and value}

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

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        if numeric != numeric:
            return default
        return numeric