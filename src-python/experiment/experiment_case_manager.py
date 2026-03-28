from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .apollo_online_experiment_runtime import (
    OnlineExperimentCase,
    build_case_lookup,
    build_runtime_panel_payload,
    derive_figure_semantics,
    load_experiment_plan,
)
from .apollo_scenario_context import RuntimeScenarioContext, build_session_meta_patch
from .apollo_task_context import TaskSnapshot
from .architecture_config_loader import ArchitectureConfigBundle, load_architecture_config_bundle


class ExperimentCaseManager:
    def __init__(self, plan_path: str | Path, architecture_config_dir: str | Path):
        self.plan_path = Path(plan_path)
        self.architecture_config_dir = Path(architecture_config_dir)
        self.cases: List[OnlineExperimentCase] = []
        self.case_lookup: Dict[str, OnlineExperimentCase] = {}
        self.selected_case_id: Optional[str] = None
        self.architecture_bundle: Optional[ArchitectureConfigBundle] = None

    def reload(self) -> None:
        self.cases = load_experiment_plan(self.plan_path)
        self.case_lookup = build_case_lookup(self.cases)
        self.architecture_bundle = load_architecture_config_bundle(self.architecture_config_dir)

    def find_case(self, case_id: Optional[str] = None) -> Optional[OnlineExperimentCase]:
        lookup_key = str(case_id or self.selected_case_id or '').strip().upper()
        if not lookup_key:
            return None
        return self.case_lookup.get(lookup_key)

    def select_case(self, case_id: str) -> OnlineExperimentCase:
        planned_case = self.find_case(case_id)
        if planned_case is None:
            raise KeyError(case_id)
        self.selected_case_id = planned_case.case_id
        return planned_case

    def serialize_case(self, planned_case: OnlineExperimentCase) -> dict:
        return planned_case.as_dict()

    def list_architecture_profiles(self) -> dict:
        if self.architecture_bundle is None:
            return {
                'baseline_profiles': [],
                'candidate_profiles': [],
                'research_profiles': [],
            }

        def _serialize(profile):
            return {
                'profile_id': profile.profile_id,
                'profile_name': profile.profile_name,
                'profile_group': profile.profile_group,
                'research_only': profile.research_only,
                'description': profile.description,
                'assignments': profile.assignments,
            }

        baseline_profiles = []
        candidate_profiles = []
        research_profiles = []
        for profile in self.architecture_bundle.list_profiles(include_research=True):
            payload = _serialize(profile)
            if profile.research_only:
                research_profiles.append(payload)
            elif profile.profile_group == 'baseline':
                baseline_profiles.append(payload)
            else:
                candidate_profiles.append(payload)
        return {
            'baseline_profiles': baseline_profiles,
            'candidate_profiles': candidate_profiles,
            'research_profiles': research_profiles,
        }

    def build_runtime_payload(
        self,
        planned_case: OnlineExperimentCase,
        task_snapshot: TaskSnapshot,
        scenario_context: RuntimeScenarioContext,
        *,
        recording_case_id: Optional[str] = None,
    ) -> dict:
        runtime_payload = build_runtime_panel_payload(planned_case, task_snapshot, scenario_context)
        runtime_payload['case']['recording_case_id'] = recording_case_id
        runtime_payload['architecture_profiles'] = self.list_architecture_profiles()
        return runtime_payload

    def build_recording_meta_patch(
        self,
        planned_case: Optional[OnlineExperimentCase] = None,
        *,
        case_id: Optional[str] = None,
        repeat_index: Optional[int] = None,
        scenario_id: Optional[str] = None,
        notes: str = '',
        experiment_type: Optional[str] = None,
        figure_run_id: Optional[str] = None,
        figure_batch_id: Optional[str] = None,
        figure_batch_group: Optional[str] = None,
        chapter_target: Optional[str] = None,
        law_validation_scope: Optional[str] = None,
        analysis_run_id: Optional[str] = None,
    ) -> dict:
        patch = {}
        if planned_case is not None:
            serialized_case = self.serialize_case(planned_case)
            patch.update(build_session_meta_patch(serialized_case))
            figure_semantics = derive_figure_semantics(
                planned_case,
                experiment_type=experiment_type,
                figure_run_id=figure_run_id,
                figure_batch_id=figure_batch_id,
                figure_batch_group=figure_batch_group,
                chapter_target=chapter_target,
                law_validation_scope=law_validation_scope,
            )
            patch.update(
                {
                    'plan_case_id': planned_case.case_id,
                    'repeat_index': planned_case.repeat_index,
                    'task_profile_id': planned_case.task_profile_id,
                    'architecture_id': planned_case.architecture_id,
                    'architecture_name': planned_case.architecture_name,
                    'mapping_profile': planned_case.mapping_profile,
                    'canonical_profile_id': planned_case.canonical_profile_id,
                    'adaptation_mode': planned_case.adaptation_mode,
                    'planned_case': serialized_case,
                    'architecture_profiles': self.list_architecture_profiles(),
                    **figure_semantics,
                }
            )
        else:
            patch.update(
                derive_figure_semantics(
                    None,
                    case_id=case_id,
                    experiment_type=experiment_type,
                    figure_run_id=figure_run_id,
                    figure_batch_id=figure_batch_id,
                    figure_batch_group=figure_batch_group,
                    chapter_target=chapter_target,
                    law_validation_scope=law_validation_scope,
                )
            )
            if case_id:
                patch['plan_case_id'] = str(case_id).strip().upper()
            if repeat_index is not None:
                patch['repeat_index'] = int(repeat_index)
        if scenario_id:
            patch.update(build_session_meta_patch({'scenario_id': scenario_id}))
        if notes:
            patch['notes'] = notes
            patch['operator_note'] = notes
        if analysis_run_id:
            patch['analysis_run_id'] = analysis_run_id
        return patch