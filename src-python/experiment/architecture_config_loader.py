from __future__ import annotations

import csv
import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional


DEFAULT_THESIS_WS_PATH = Path(os.getenv('THESIS_WS_PATH') or 'E:/DataAnalysis/thesis_ws')
LEGACY_PROFILE_ALIAS_MAP = {
    'baseline_map_v1': 'native',
    'arch_baseline_balanced': 'native',
    'arch_baseline_balanced_control': 'native',
    'arch_baseline_balanced_reference': 'native',
    'arch_baseline_balanced_runtime': 'native',
    'arch_baseline_balanced_profile': 'native',
    'arch_baseline_balanced_candidate': 'native',
    'arch_baseline_balanced_eval': 'native',
    'arch_baseline_balanced_opt': 'native',
    'arch_baseline_balanced_ws': 'native',
    'arch_baseline_balanced_ui': 'native',
    'arch_baseline_balanced': 'native',
    'arch_baseline_balanced_control_group': 'native',
    'arch_baseline_balanced_case': 'native',
    'planner_priority_map_v2': 'native_fc_gp1',
    'arch_planning_priority': 'native_fc_gp1',
    'comm_guard_map_v2': 'all_npu',
    'arch_comm_reduced': 'all_npu',
}


@dataclass(frozen=True)
class LogicalFunctionDefinition:
    logical_function_id: str
    logical_function_name: str
    domain: str
    data_source_type: str
    default_filter_id: str
    compute_native_type: str
    dal_level: str
    min_mips: int
    description: str


@dataclass(frozen=True)
class HardwareResourceDefinition:
    hardware_id: str
    type: str
    compute_type: str
    mips: int
    bandwidth_mbps: float
    safety_level: str
    power_idle_w: float
    power_full_w: float
    description: str


@dataclass(frozen=True)
class ConstraintDefinition:
    logical_function_id: str
    constraint_type: str
    allowed_hardware: tuple[str, ...]
    required_safety_level: str
    notes: str


@dataclass(frozen=True)
class AllocationAssignment:
    profile_id: str
    profile_name: str
    profile_group: str
    logical_function_id: str
    assigned_hardware: str
    research_only: bool
    description: str


@dataclass(frozen=True)
class AllocationProfile:
    profile_id: str
    profile_name: str
    profile_group: str
    research_only: bool
    description: str
    assignments: Dict[str, str]


@dataclass(frozen=True)
class ArchitectureConfigBundle:
    config_dir: Path
    logical_functions: Dict[str, LogicalFunctionDefinition]
    hardware_resources: Dict[str, HardwareResourceDefinition]
    constraints: List[ConstraintDefinition]
    allocation_profiles: Dict[str, AllocationProfile]

    def get_allocation_profile(self, profile_id: str) -> Optional[AllocationProfile]:
        return self.allocation_profiles.get(profile_id)

    def resolve_allocation_profile(self, requested_profile_id: Optional[str]) -> Optional[AllocationProfile]:
        lookup = str(requested_profile_id or '').strip()
        if not lookup:
            return None
        if lookup in self.allocation_profiles:
            return self.get_allocation_profile(lookup)

        alias = LEGACY_PROFILE_ALIAS_MAP.get(lookup.lower())
        if alias and alias in self.allocation_profiles:
            return self.get_allocation_profile(alias)

        lowered = lookup.lower()
        for profile in self.allocation_profiles.values():
            if profile.profile_id.lower() == lowered or profile.profile_name.lower() == lowered:
                return profile
        return None

    def find_profile_by_assignments(self, assignments: Mapping[str, str]) -> Optional[AllocationProfile]:
        normalized = {str(key): str(value) for key, value in dict(assignments or {}).items() if key}
        if not normalized:
            return None
        for profile in self.allocation_profiles.values():
            if profile.assignments == normalized:
                return profile
        return None

    def list_profiles(self, *, include_research: bool = True) -> List[AllocationProfile]:
        profiles = list(self.allocation_profiles.values())
        if not include_research:
            profiles = [profile for profile in profiles if not profile.research_only]
        return sorted(profiles, key=lambda profile: (profile.profile_group, profile.profile_id))


def _read_csv_rows(file_path: Path) -> List[dict]:
    with file_path.open('r', encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def _parse_bool(value: str) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y'}


def _load_thesis_settings_module(thesis_workspace: Path):
    settings_path = thesis_workspace / 'src' / 'config' / 'settings.py'
    if not settings_path.exists():
        return None

    spec = importlib.util.spec_from_file_location('apollo_thesis_settings', settings_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _merge_thesis_profiles(
    allocation_profiles: Dict[str, AllocationProfile],
    logical_functions: Dict[str, LogicalFunctionDefinition],
    hardware_resources: Dict[str, HardwareResourceDefinition],
) -> None:
    if not DEFAULT_THESIS_WS_PATH.exists():
        return

    thesis_settings = _load_thesis_settings_module(DEFAULT_THESIS_WS_PATH)
    if thesis_settings is None:
        return

    thesis_profiles = getattr(thesis_settings, 'ARCHITECTURE_CONFIGS', {}) or {}
    thesis_meta = getattr(thesis_settings, 'ARCHITECTURE_CONFIG_META', {}) or {}
    required_function_ids = set(logical_functions)
    known_hardware_ids = set(hardware_resources)

    for profile_id, assignments in thesis_profiles.items():
        assignment_map = {str(key): str(value) for key, value in dict(assignments or {}).items() if key and value}
        if set(assignment_map) != required_function_ids:
            continue
        if any(hardware_id not in known_hardware_ids for hardware_id in assignment_map.values()):
            continue

        existing = allocation_profiles.get(profile_id)
        meta = thesis_meta.get(profile_id, {}) or {}
        allocation_profiles[profile_id] = AllocationProfile(
            profile_id=profile_id,
            profile_name=(existing.profile_name if existing else str(meta.get('display_name') or meta.get('name') or profile_id)),
            profile_group=(existing.profile_group if existing else ('baseline' if profile_id == 'native' else ('research' if profile_id.endswith('_study') else 'study'))),
            research_only=(existing.research_only if existing else bool(meta.get('research_only')) or profile_id.endswith('_study')),
            description=str(meta.get('description') or (existing.description if existing else '')),
            assignments=assignment_map,
        )


def load_architecture_config_bundle(config_dir: str | Path) -> ArchitectureConfigBundle:
    root = Path(config_dir)
    logical_function_rows = _read_csv_rows(root / 'architecture_logical_functions.csv')
    hardware_rows = _read_csv_rows(root / 'architecture_hardware_resources.csv')
    constraint_rows = _read_csv_rows(root / 'architecture_constraints.csv')
    allocation_rows = _read_csv_rows(root / 'architecture_candidate_allocations.csv')

    logical_functions = {
        row['logical_function_id']: LogicalFunctionDefinition(
            logical_function_id=row['logical_function_id'],
            logical_function_name=row['logical_function_name'],
            domain=row['domain'],
            data_source_type=row['data_source_type'],
            default_filter_id=row['default_filter_id'],
            compute_native_type=row['compute_native_type'],
            dal_level=row['dal_level'],
            min_mips=int(row['min_mips']),
            description=row.get('description', ''),
        )
        for row in logical_function_rows
    }
    hardware_resources = {
        row['hardware_id']: HardwareResourceDefinition(
            hardware_id=row['hardware_id'],
            type=row['type'],
            compute_type=row['compute_type'],
            mips=int(row['mips']),
            bandwidth_mbps=float(row['bandwidth_mbps']),
            safety_level=row['safety_level'],
            power_idle_w=float(row['power_idle_w']),
            power_full_w=float(row['power_full_w']),
            description=row.get('description', ''),
        )
        for row in hardware_rows
    }
    constraints = [
        ConstraintDefinition(
            logical_function_id=row['logical_function_id'],
            constraint_type=row['constraint_type'],
            allowed_hardware=tuple(part.strip() for part in str(row['allowed_hardware']).split('|') if part.strip()),
            required_safety_level=row['required_safety_level'],
            notes=row.get('notes', ''),
        )
        for row in constraint_rows
    ]

    validation_errors: List[str] = []
    allocation_assignments: Dict[str, List[AllocationAssignment]] = {}
    for row in allocation_rows:
        assignment = AllocationAssignment(
            profile_id=row['profile_id'],
            profile_name=row['profile_name'],
            profile_group=row['profile_group'],
            logical_function_id=row['logical_function_id'],
            assigned_hardware=row['assigned_hardware'],
            research_only=_parse_bool(row.get('research_only', 'no')),
            description=row.get('description', ''),
        )
        if assignment.logical_function_id not in logical_functions:
            validation_errors.append(
                f"Unknown logical function '{assignment.logical_function_id}' in profile '{assignment.profile_id}'."
            )
        if assignment.assigned_hardware not in hardware_resources:
            validation_errors.append(
                f"Unknown hardware '{assignment.assigned_hardware}' in profile '{assignment.profile_id}'."
            )
        allocation_assignments.setdefault(assignment.profile_id, []).append(assignment)

    for constraint in constraints:
        if constraint.logical_function_id not in logical_functions:
            validation_errors.append(
                f"Unknown logical function '{constraint.logical_function_id}' in constraints."
            )
        for hardware_id in constraint.allowed_hardware:
            if hardware_id not in hardware_resources:
                validation_errors.append(
                    f"Unknown hardware '{hardware_id}' in constraints for '{constraint.logical_function_id}'."
                )

    required_function_ids = set(logical_functions)
    allocation_profiles: Dict[str, AllocationProfile] = {}
    for profile_id, assignments in allocation_assignments.items():
        first = assignments[0]
        assignment_map = {assignment.logical_function_id: assignment.assigned_hardware for assignment in assignments}
        missing_functions = sorted(required_function_ids - set(assignment_map))
        if missing_functions:
            validation_errors.append(
                f"Profile '{profile_id}' is missing assignments for: {', '.join(missing_functions)}."
            )
        allocation_profiles[profile_id] = AllocationProfile(
            profile_id=profile_id,
            profile_name=first.profile_name,
            profile_group=first.profile_group,
            research_only=first.research_only,
            description=first.description,
            assignments=assignment_map,
        )

    _merge_thesis_profiles(allocation_profiles, logical_functions, hardware_resources)

    if validation_errors:
        raise ValueError('Architecture config validation failed: ' + ' | '.join(validation_errors))

    return ArchitectureConfigBundle(
        config_dir=root,
        logical_functions=logical_functions,
        hardware_resources=hardware_resources,
        constraints=constraints,
        allocation_profiles=allocation_profiles,
    )