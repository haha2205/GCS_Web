from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .architecture_config_loader import LEGACY_PROFILE_ALIAS_MAP
from .apollo_scenario_context import RuntimeScenarioContext, ScenarioResolver
from .apollo_task_context import FlightTaskTracker, TaskSnapshot, get_task_definition


def resolve_canonical_profile_id(*candidates: Optional[str]) -> str:
    for value in candidates:
        lookup = str(value or '').strip()
        if not lookup:
            continue
        alias = LEGACY_PROFILE_ALIAS_MAP.get(lookup.lower())
        return alias or lookup
    return ''


def _extract_numeric_suffix(value: Optional[str]) -> Optional[int]:
    match = re.search(r'(\d+)$', str(value or '').strip())
    if not match:
        return None
    return int(match.group(1))


def _build_batch_id(prefix: str, ordinal: int, batch_size: int, max_ordinal: int) -> str:
    batch_start = ((ordinal - 1) // batch_size) * batch_size + 1
    batch_end = min(batch_start + batch_size - 1, max_ordinal)
    return f'{prefix}{batch_start:02d}-{prefix}{batch_end:02d}'


def derive_figure_semantics(
    planned_case: Optional['OnlineExperimentCase'] = None,
    *,
    case_id: Optional[str] = None,
    experiment_type: Optional[str] = None,
    figure_run_id: Optional[str] = None,
    figure_batch_id: Optional[str] = None,
    figure_batch_group: Optional[str] = None,
    chapter_target: Optional[str] = None,
    law_validation_scope: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_experiment_type = str(experiment_type or '').strip().lower()
    if normalized_experiment_type not in {'simulation', 'realflight'}:
        normalized_experiment_type = 'simulation' if planned_case is not None else 'realflight'

    if planned_case is not None:
        default_ordinal = _extract_numeric_suffix(planned_case.case_id)
    else:
        default_ordinal = _extract_numeric_suffix(case_id)

    prefix = 'S' if normalized_experiment_type == 'simulation' else 'E'
    max_ordinal = 60 if prefix == 'S' else 40
    batch_size = 5 if prefix == 'S' else 6
    figure_ordinal = _extract_numeric_suffix(figure_run_id) or default_ordinal
    if figure_ordinal is not None:
        figure_ordinal = max(1, min(max_ordinal, figure_ordinal))

    computed_run_id = figure_run_id or (f'{prefix}{figure_ordinal:02d}' if figure_ordinal is not None else '')
    computed_batch_id = figure_batch_id or (
        _build_batch_id(prefix, figure_ordinal, batch_size, max_ordinal)
        if figure_ordinal is not None else ''
    )

    figure_ledger_range = ''
    computed_group = figure_batch_group or ''
    computed_chapter = chapter_target or ''
    computed_scope = law_validation_scope or ''

    if prefix == 'S' and figure_ordinal is not None:
        if figure_ordinal <= 20:
            figure_ledger_range = 'S01-S20'
            computed_chapter = computed_chapter or 'chapter3'
            computed_group = computed_group or 'law1_response_curves'
            computed_scope = computed_scope or 'law1'
        elif figure_ordinal <= 40:
            figure_ledger_range = 'S21-S40'
            computed_chapter = computed_chapter or 'chapter3'
            computed_group = computed_group or 'law2_architecture_tradeoffs'
            computed_scope = computed_scope or 'law2'
        else:
            figure_ledger_range = 'S41-S60'
            computed_chapter = computed_chapter or 'chapter4'
            computed_group = computed_group or 'law3_simulation_rescoring'
            computed_scope = computed_scope or 'law3'
    elif prefix == 'E' and figure_ordinal is not None:
        if figure_ordinal <= 16:
            figure_ledger_range = 'E01-E16'
            computed_chapter = computed_chapter or 'chapter3'
            computed_group = computed_group or 'realflight_validation_curves'
            computed_scope = computed_scope or 'chapter3_experiment'
        else:
            figure_ledger_range = 'E17-E40'
            computed_chapter = computed_chapter or 'chapter4'
            computed_group = computed_group or 'law3_realflight_rescoring'
            computed_scope = computed_scope or 'law3'

    return {
        'figure_run_id': computed_run_id,
        'figure_batch_id': computed_batch_id,
        'figure_batch_group': computed_group,
        'figure_ledger_range': figure_ledger_range,
        'experiment_type': normalized_experiment_type,
        'chapter_target': computed_chapter,
        'law_validation_scope': computed_scope,
    }


@dataclass(frozen=True)
class ArchitectureCandidate:
    architecture_id: str
    display_name: str
    mapping_profile: str
    canonical_profile_id: str
    adaptation_mode: str
    focus: str
    description: str


ARCHITECTURE_CANDIDATES: Dict[str, ArchitectureCandidate] = {
    'ARCH_BASELINE_BALANCED': ArchitectureCandidate('ARCH_BASELINE_BALANCED', 'Baseline Balanced', 'baseline_map_v1', 'native', 'observe_only', 'reference', 'Keep the thesis native mapping as the control group.'),
    'ARCH_PLANNING_PRIORITY': ArchitectureCandidate('ARCH_PLANNING_PRIORITY', 'Planning Priority', 'planner_priority_map_v2', 'native_fc_gp1', 'recommend_then_confirm', 'planning_latency', 'Map to the thesis GP1 flight-control split profile for planning-priority comparison.'),
    'ARCH_COMM_REDUCED': ArchitectureCandidate('ARCH_COMM_REDUCED', 'Communication Reduced', 'comm_guard_map_v2', 'all_npu', 'recommend_then_confirm', 'link_resilience', 'Map to the thesis shared SoC profile with the lowest cross-domain interaction count.'),
}


@dataclass(frozen=True)
class OnlineExperimentCase:
    case_id: str
    repeat_index: int
    task_profile_id: str
    cmd_idx: int
    mission_id: int
    task_name: str
    task_group: str
    scenario_id: str
    scenario_name: str
    environment_class: str
    obstacle_density: str
    wind_level: str
    link_quality: str
    sensor_quality: str
    disturbance_profile: str
    architecture_id: str
    architecture_name: str
    mapping_profile: str
    canonical_profile_id: str
    adaptation_mode: str
    expected_focus: str
    trigger_policy: str
    duration_sec: int
    preheat_sec: int
    evaluation_window_sec: int
    requires_manual_annotation: str
    notes: str

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            'case_id': self.case_id,
            'repeat_index': self.repeat_index,
            'task_profile_id': self.task_profile_id,
            'cmd_idx': self.cmd_idx,
            'mission_id': self.mission_id,
            'task_name': self.task_name,
            'task_group': self.task_group,
            'scenario_id': self.scenario_id,
            'scenario_name': self.scenario_name,
            'environment_class': self.environment_class,
            'obstacle_density': self.obstacle_density,
            'wind_level': self.wind_level,
            'link_quality': self.link_quality,
            'sensor_quality': self.sensor_quality,
            'disturbance_profile': self.disturbance_profile,
            'architecture_id': self.architecture_id,
            'architecture_name': self.architecture_name,
            'mapping_profile': self.mapping_profile,
            'canonical_profile_id': self.canonical_profile_id,
            'adaptation_mode': self.adaptation_mode,
            'expected_focus': self.expected_focus,
            'trigger_policy': self.trigger_policy,
            'duration_sec': self.duration_sec,
            'preheat_sec': self.preheat_sec,
            'evaluation_window_sec': self.evaluation_window_sec,
            'requires_manual_annotation': self.requires_manual_annotation,
            'notes': self.notes,
        }
        payload.update(derive_figure_semantics(self))
        return payload


def load_experiment_plan(csv_path: str | Path) -> List[OnlineExperimentCase]:
    plan_path = Path(csv_path)
    rows: List[OnlineExperimentCase] = []
    with plan_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                OnlineExperimentCase(
                    case_id=row['case_id'],
                    repeat_index=int(row['repeat_index']),
                    task_profile_id=row['task_profile_id'],
                    cmd_idx=int(row['cmd_idx']),
                    mission_id=int(row['mission_id']),
                    task_name=row['task_name'],
                    task_group=row['task_group'],
                    scenario_id=row['scenario_id'],
                    scenario_name=row['scenario_name'],
                    environment_class=row.get('environment_class', ''),
                    obstacle_density=row.get('obstacle_density', ''),
                    wind_level=row.get('wind_level', ''),
                    link_quality=row.get('link_quality', ''),
                    sensor_quality=row.get('sensor_quality', ''),
                    disturbance_profile=row.get('disturbance_profile', ''),
                    architecture_id=row['architecture_id'],
                    architecture_name=row['architecture_name'],
                    mapping_profile=row['mapping_profile'],
                    canonical_profile_id=resolve_canonical_profile_id(row.get('mapping_profile'), row.get('architecture_id')),
                    adaptation_mode=row['adaptation_mode'],
                    expected_focus=row.get('expected_focus', ''),
                    trigger_policy=row['trigger_policy'],
                    duration_sec=int(row['duration_sec']),
                    preheat_sec=int(row.get('preheat_sec', 0)),
                    evaluation_window_sec=int(row['evaluation_window_sec']),
                    requires_manual_annotation=row.get('requires_manual_annotation', ''),
                    notes=row.get('notes', ''),
                )
            )
    return rows


def choose_candidate(
    task_snapshot: TaskSnapshot,
    scenario_context: RuntimeScenarioContext,
    planned_case: Optional[OnlineExperimentCase] = None,
) -> ArchitectureCandidate:
    if planned_case is not None and planned_case.architecture_id in ARCHITECTURE_CANDIDATES:
        return ARCHITECTURE_CANDIDATES[planned_case.architecture_id]

    if scenario_context.link_quality == 'degraded':
        return ARCHITECTURE_CANDIDATES['ARCH_COMM_REDUCED']
    if task_snapshot.planning_related or scenario_context.obstacle_density == 'high':
        return ARCHITECTURE_CANDIDATES['ARCH_PLANNING_PRIORITY']
    return ARCHITECTURE_CANDIDATES['ARCH_BASELINE_BALANCED']


def build_runtime_panel_payload(
    planned_case: OnlineExperimentCase,
    task_snapshot: TaskSnapshot,
    scenario_context: RuntimeScenarioContext,
) -> Dict[str, Any]:
    candidate = choose_candidate(task_snapshot, scenario_context, planned_case)
    figure_semantics = derive_figure_semantics(planned_case)
    return {
        'case': {
            'case_id': planned_case.case_id,
            'repeat_index': planned_case.repeat_index,
            'task_profile_id': planned_case.task_profile_id,
            'duration_sec': planned_case.duration_sec,
            'preheat_sec': planned_case.preheat_sec,
            'evaluation_window_sec': planned_case.evaluation_window_sec,
            'requires_manual_annotation': planned_case.requires_manual_annotation,
            'notes': planned_case.notes,
            **figure_semantics,
        },
        'task': {
            'planned_cmd_idx': planned_case.cmd_idx,
            'effective_cmd_idx': task_snapshot.effective_cmd_id,
            'mission_id': task_snapshot.mission_id,
            'task_name': task_snapshot.display_name,
            'task_group': task_snapshot.task_group,
            'phase': task_snapshot.mission_phase,
            'source': task_snapshot.source,
        },
        'scenario': {
            'scenario_id': scenario_context.scenario_id,
            'display_name': planned_case.scenario_name or scenario_context.display_name,
            'source': scenario_context.source,
            'confidence': scenario_context.confidence,
            'environment_class': planned_case.environment_class or scenario_context.environment_class,
            'obstacle_density': planned_case.obstacle_density or scenario_context.obstacle_density,
            'wind_level': planned_case.wind_level or scenario_context.wind_level,
            'link_quality': planned_case.link_quality or scenario_context.link_quality,
            'sensor_quality': planned_case.sensor_quality or scenario_context.sensor_quality,
            'disturbance_profile': planned_case.disturbance_profile,
            'disturbance_tags': list(scenario_context.disturbance_tags),
            'heuristic_tags': list(scenario_context.heuristic_tags),
        },
        'architecture': {
            'architecture_id': candidate.architecture_id,
            'display_name': candidate.display_name,
            'mapping_profile': candidate.mapping_profile,
            'canonical_profile_id': candidate.canonical_profile_id,
            'profile_id': candidate.canonical_profile_id,
            'adaptation_mode': candidate.adaptation_mode,
            'focus': candidate.focus,
            'expected_focus': planned_case.expected_focus,
        },
        'figure_semantics': figure_semantics,
        'trigger_policy': planned_case.trigger_policy,
    }


def build_case_lookup(cases: Iterable[OnlineExperimentCase]) -> Dict[str, OnlineExperimentCase]:
    return {case.case_id.upper(): case for case in cases}


def build_default_task_snapshot(cmd_idx: int, mission_id: int = 0) -> TaskSnapshot:
    tracker = FlightTaskTracker(confirm_threshold=1)
    snapshot = tracker.update(telemetry_payload={'Tele_GCS_CmdIdx': cmd_idx, 'Tele_GCS_Mission': mission_id})
    task_def = get_task_definition(cmd_idx)
    return TaskSnapshot(
        desired_cmd_id=snapshot.desired_cmd_id,
        confirmed_cmd_id=snapshot.confirmed_cmd_id,
        effective_cmd_id=snapshot.effective_cmd_id,
        mission_id=mission_id,
        task_code=task_def.task_code,
        display_name=task_def.display_name,
        task_group=task_def.task_group,
        mission_phase=task_def.mission_phase,
        planning_related=task_def.planning_related,
        stable_samples=snapshot.stable_samples,
        source=snapshot.source,
    )