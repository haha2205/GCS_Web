from __future__ import annotations

import csv
from pathlib import Path


TASK_PROFILES = [
    {
        'task_profile_id': 'T01_AUTO_TAKEOFF',
        'cmd_idx': 14,
        'mission_id': 4,
        'task_name': 'Auto Takeoff',
        'task_group': 'takeoff',
        'trigger_policy': 'control_jitter_or_attitude_peak',
        'duration_sec': 150,
    },
    {
        'task_profile_id': 'T02_HOVER_HOLD',
        'cmd_idx': 16,
        'mission_id': 16,
        'task_name': 'Hover Hold',
        'task_group': 'nominal_mission',
        'trigger_policy': 'control_jitter_or_tracking_rmse',
        'duration_sec': 180,
    },
    {
        'task_profile_id': 'T03_CRUISE_FORWARD',
        'cmd_idx': 5,
        'mission_id': 5,
        'task_name': 'Cruise Forward',
        'task_group': 'nominal_mission',
        'trigger_policy': 'tracking_rmse_or_downlink_loss',
        'duration_sec': 240,
    },
    {
        'task_profile_id': 'T04_PLAN_AVOID',
        'cmd_idx': 24,
        'mission_id': 24,
        'task_name': 'Planning Avoidance',
        'task_group': 'planning_mission',
        'trigger_policy': 'planning_time_or_avoid_trigger',
        'duration_sec': 240,
    },
    {
        'task_profile_id': 'T05_RETURN_HOME',
        'cmd_idx': 17,
        'mission_id': 17,
        'task_name': 'Return Home',
        'task_group': 'recovery',
        'trigger_policy': 'mission_reliability_or_gcs_fail',
        'duration_sec': 180,
    },
    {
        'task_profile_id': 'T06_AUTO_LAND',
        'cmd_idx': 15,
        'mission_id': 15,
        'task_name': 'Auto Land',
        'task_group': 'landing',
        'trigger_policy': 'descent_rate_or_tracking_rmse',
        'duration_sec': 150,
    },
]


SCENARIOS = [
    {
        'scenario_id': 'S01_OPEN_NOMINAL',
        'scenario_name': 'Open Nominal',
        'environment_class': 'open_field',
        'obstacle_density': 'low',
        'wind_level': 'low',
        'link_quality': 'nominal',
        'sensor_quality': 'nominal',
        'disturbance_profile': 'nominal',
    },
    {
        'scenario_id': 'S02_OPEN_WIND_GUST',
        'scenario_name': 'Open Wind Gust',
        'environment_class': 'open_field',
        'obstacle_density': 'low',
        'wind_level': 'high',
        'link_quality': 'nominal',
        'sensor_quality': 'nominal',
        'disturbance_profile': 'wind_gust',
    },
    {
        'scenario_id': 'S03_DENSE_OBSTACLE',
        'scenario_name': 'Dense Obstacle',
        'environment_class': 'corridor_obstacle_zone',
        'obstacle_density': 'high',
        'wind_level': 'medium',
        'link_quality': 'nominal',
        'sensor_quality': 'nominal',
        'disturbance_profile': 'planner_stress',
    },
    {
        'scenario_id': 'S04_LINK_DEGRADED',
        'scenario_name': 'Link Degraded',
        'environment_class': 'semi_urban',
        'obstacle_density': 'medium',
        'wind_level': 'medium',
        'link_quality': 'degraded',
        'sensor_quality': 'nominal',
        'disturbance_profile': 'downlink_loss',
    },
    {
        'scenario_id': 'S05_COMPOSITE_STRESS',
        'scenario_name': 'Composite Stress',
        'environment_class': 'urban_canyon',
        'obstacle_density': 'high',
        'wind_level': 'high',
        'link_quality': 'degraded',
        'sensor_quality': 'degraded',
        'disturbance_profile': 'planner_stress+downlink_loss+sensor_drop',
    },
]


ARCHITECTURES = [
    {
        'architecture_id': 'ARCH_BASELINE_BALANCED',
        'architecture_name': 'Baseline Balanced',
        'mapping_profile': 'baseline_map_v1',
        'adaptation_mode': 'observe_only',
        'expected_focus': 'reference',
    },
    {
        'architecture_id': 'ARCH_PLANNING_PRIORITY',
        'architecture_name': 'Planning Priority',
        'mapping_profile': 'planner_priority_map_v2',
        'adaptation_mode': 'recommend_then_confirm',
        'expected_focus': 'planning_latency',
    },
    {
        'architecture_id': 'ARCH_COMM_REDUCED',
        'architecture_name': 'Communication Reduced',
        'mapping_profile': 'comm_guard_map_v2',
        'adaptation_mode': 'recommend_then_confirm',
        'expected_focus': 'link_resilience',
    },
]


CSV_HEADERS = [
    'case_id',
    'repeat_index',
    'task_profile_id',
    'cmd_idx',
    'mission_id',
    'task_name',
    'task_group',
    'scenario_id',
    'scenario_name',
    'environment_class',
    'obstacle_density',
    'wind_level',
    'link_quality',
    'sensor_quality',
    'disturbance_profile',
    'architecture_id',
    'architecture_name',
    'mapping_profile',
    'adaptation_mode',
    'expected_focus',
    'trigger_policy',
    'duration_sec',
    'preheat_sec',
    'evaluation_window_sec',
    'requires_manual_annotation',
    'notes',
]


def main() -> None:
    output_path = Path(__file__).with_name('generated_research_logic_plan_20260323.csv')
    rows = []
    case_number = 1

    for repeat_index in range(1, 4):
        for task in TASK_PROFILES:
            for scenario in SCENARIOS:
                for architecture in ARCHITECTURES:
                    rows.append(
                        {
                            'case_id': f'CASE_{case_number:03d}',
                            'repeat_index': repeat_index,
                            'task_profile_id': task['task_profile_id'],
                            'cmd_idx': task['cmd_idx'],
                            'mission_id': task['mission_id'],
                            'task_name': task['task_name'],
                            'task_group': task['task_group'],
                            'scenario_id': scenario['scenario_id'],
                            'scenario_name': scenario['scenario_name'],
                            'environment_class': scenario['environment_class'],
                            'obstacle_density': scenario['obstacle_density'],
                            'wind_level': scenario['wind_level'],
                            'link_quality': scenario['link_quality'],
                            'sensor_quality': scenario['sensor_quality'],
                            'disturbance_profile': scenario['disturbance_profile'],
                            'architecture_id': architecture['architecture_id'],
                            'architecture_name': architecture['architecture_name'],
                            'mapping_profile': architecture['mapping_profile'],
                            'adaptation_mode': architecture['adaptation_mode'],
                            'expected_focus': architecture['expected_focus'],
                            'trigger_policy': task['trigger_policy'],
                            'duration_sec': task['duration_sec'],
                            'preheat_sec': 20,
                            'evaluation_window_sec': 5,
                            'requires_manual_annotation': 'yes',
                            'notes': f"repeat={repeat_index};scenario={scenario['scenario_id']};architecture={architecture['architecture_id']}",
                        }
                    )
                    case_number += 1

    with output_path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f'Wrote {len(rows)} thesis-primary cases to {output_path}')


if __name__ == '__main__':
    main()